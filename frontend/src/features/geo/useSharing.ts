import { useCallback, useEffect, useRef, useState } from 'react';
import { active, geoApi, GeoError } from './api';
import { along, totalMeters } from './geometry';
import type { Point, Position, RouteResult, Route, Session } from './api';

type Mode = 'idle' | 'simulating' | 'paused' | 'gps' | 'finished';
export function useSharing(orderId: string, session: Session | null, status: string, onPoint: () => void) {
  const [mode, setMode] = useState<Mode>('idle');
  const [message, setMessage] = useState('Ubicación desactivada. Tú decides cuándo compartir.');
  const modeRef = useRef<Mode>('idle');
  const previousStatus=useRef(status);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const watch = useRef<number | undefined>(undefined);
  const distance = useRef(0);
  const road = useRef<Route | null>(null);
  const speed = useRef(8);
  const deviation = useRef(0);
  const retryDelay = useRef(0);
  const sequence = useRef(Date.now());
  const sending = useRef(false);
  const lastSent = useRef(0);
  const generation = useRef(0);
  const request = useRef<AbortController | null>(null);
  const endpoint = `/orders/${encodeURIComponent(orderId)}/location`;
  const changeMode = (value: Mode) => { modeRef.current = value; setMode(value); };
  const halt = useCallback(() => {
    generation.current++;
    clearTimeout(timer.current);
    if (watch.current !== undefined) navigator.geolocation?.clearWatch(watch.current);
    watch.current = undefined;
    request.current?.abort();
    request.current = null;
    sending.current = false;
  }, []);
  const stop = useCallback(async () => {
    halt(); road.current=null;distance.current=0;changeMode('idle');
    setMessage('Ubicación desactivada.');
    try { if (session) await geoApi(endpoint, session, 'DELETE'); onPoint(); }
    catch { setMessage('Se detuvo el envío. No se pudo borrar la última ubicación; vencerá en un máximo de 120 segundos.'); }
  }, [halt, session, endpoint, onPoint]);
  const send = useCallback(async (point: Point, current: number) => {
    if (sending.current || generation.current !== current || !session) return false;
    sending.current = true;
    const controller = new AbortController(); request.current = controller;
    try {
      const result = await geoApi<{accepted: boolean}>(endpoint, session, 'POST', {...point,sequence:++sequence.current}, controller.signal);
      if (generation.current !== current) return false;
      if (!result.accepted) { setMessage('Muestra anterior ignorada. Esperando la siguiente ubicación.'); return false; }
      setMessage('Ubicación enviada.'); onPoint(); return true;
    } catch (error) {
      if (generation.current !== current) return false;
      if (error instanceof GeoError && [401,403,404,409].includes(error.status)) {
        halt(); changeMode('idle'); setMessage('Se detuvo el envío: revisa la sesión o el estado de la entrega.');
      } else if (error instanceof GeoError && error.status===429) { retryDelay.current=8000;setMessage('Frecuencia limitada. Se reintentará en unos segundos.'); }
      else setMessage('No se pudo enviar la ubicación. El estado de la entrega sigue disponible.');
      return false;
    } finally { if (generation.current === current) sending.current = false; }
  }, [session, endpoint, halt, onPoint]);
  const simulate = useCallback((restart = false, origin?: Position | null) => {
    if (!session || !active(status) || !(import.meta.env.DEV || import.meta.env.VITE_GEO_SIMULATOR==='true')) return;
    halt();
    if (restart) { distance.current=0;road.current=null; }
    if (!road.current && !origin) {setMessage('Selecciona el inicio de la demo en el mapa.');return;}
    changeMode('simulating');
    const current=generation.current;
    let previousTime=performance.now();
    let resetRequired=restart;
    const tick=async()=>{
      if (generation.current!==current || modeRef.current!=='simulating') return;
      try {
        if (!road.current) {
          if (!origin) return;
          if (resetRequired) {
            await geoApi(endpoint,session,'DELETE');
            if (generation.current!==current) return;
            resetRequired=false;
          }
          const accepted=await send({...origin,accuracyMeters:10,recordedAt:new Date().toISOString(),source:'SIMULATED'},current);
          if (generation.current!==current) return;
          if (!accepted) {timer.current=setTimeout(tick,retryDelay.current || 4000);return;}
          const response=await geoApi<RouteResult>(`/orders/${encodeURIComponent(orderId)}/route`,session);
          if (generation.current!==current) return;
          if (!response.route || response.route.phase!==status) {changeMode('idle');setMessage('No hay ruta vial disponible para esta fase. Revisa los puntos del pedido y reintenta en unos segundos.');return;}
          road.current=response.route;distance.current=response.route.progressMeters || 0;previousTime=performance.now();
        } else {
          const now=performance.now();
          const next=Math.min(totalMeters(road.current.geometry.coordinates),distance.current+Math.min(10,(now-previousTime)/1000)*speed.current);
          previousTime=now;
          const position=along(road.current.geometry.coordinates,next);
          const deviating=deviation.current>0;
          const accepted=await send({longitude:position.coordinate[0],latitude:position.coordinate[1]+(deviating?.001:0),
            accuracyMeters:10,speedMps:speed.current,headingDegrees:position.heading,recordedAt:new Date().toISOString(),source:'SIMULATED'},current);
          if (generation.current!==current) return;
          if (accepted) {distance.current=next;if (deviating) deviation.current--;}
          const response=await geoApi<RouteResult>(`/orders/${encodeURIComponent(orderId)}/route`,session);
          if (generation.current!==current) return;
          const changed=!!response.route && response.route.routeVersion!==road.current.routeVersion;
          if (changed && response.route) {road.current=response.route;distance.current=0;}
          if (!changed && accepted && !deviating && next>=totalMeters(road.current.geometry.coordinates)) {changeMode('finished');setMessage(status==='ASSIGNED'?'Llegaste al punto de recogida. Pulsa «Marcar recogido» para preparar el recorrido a entrega.':'Llegaste al punto de entrega. Pulsa «Marcar entregado» para completar el pedido.');return;}
        }
      } catch (error) {
        if (generation.current!==current) return;
        if (error instanceof GeoError && [401,403,404,409].includes(error.status)) {halt();changeMode('idle');setMessage('Se detuvo la demo por la sesión o el estado del pedido.');return;}
        setMessage('Ruta no disponible. Se reintentará sin cambiar el estado del pedido.');
      }
      if (generation.current===current) {
        timer.current=setTimeout(tick,Math.max(3000,Math.min(5000,Number(import.meta.env.VITE_GEO_INTERVAL_MS)||4000),retryDelay.current));retryDelay.current=0;
      }
    };
    timer.current=setTimeout(tick,4000);
  },[session,status,halt,send,orderId,endpoint]);
  const pause = () => { halt(); changeMode('paused'); setMessage('Simulación pausada. La última muestra caducará si no reanudas.'); };
  const gps = () => {
    if (!session || !active(status)) return;
    halt();
    if (!window.isSecureContext || !navigator.geolocation) { changeMode('idle'); setMessage('GPS requiere HTTPS o localhost. Puedes continuar por estados.'); return; }
    changeMode('gps'); setMessage('Solicitando permiso de ubicación al navegador…');
    lastSent.current = 0;
    const current = generation.current;
    try { watch.current = navigator.geolocation.watchPosition(position => {
      if (generation.current !== current || modeRef.current !== 'gps' || Date.now()-lastSent.current<4000) return;
      lastSent.current = Date.now();
      void send({latitude:position.coords.latitude, longitude:position.coords.longitude, accuracyMeters:position.coords.accuracy,
        recordedAt:new Date(position.timestamp).toISOString(), source:'BROWSER_GPS',
        ...(position.coords.speed!==null && Number.isFinite(position.coords.speed) ? {speedMps:position.coords.speed} : {}),
        ...(position.coords.heading!==null && Number.isFinite(position.coords.heading) ? {headingDegrees:position.coords.heading} : {})},current);
    }, () => {
      halt(); changeMode('idle'); setMessage('No se pudo usar el GPS. Revisa el permiso del navegador; puedes continuar por estados.');
    }, { enableHighAccuracy:false, maximumAge:0, timeout:15000 }); }
    catch { halt(); changeMode('idle'); setMessage('No se pudo usar el GPS. Puedes continuar por estados.'); }
  };
  const prepareTransition=()=>{
    if (modeRef.current==='gps') return;
    halt();road.current=null;distance.current=0;changeMode('idle');
    setMessage('Envío pausado. Confirma el estado del pedido antes de iniciar el siguiente recorrido.');
  };
  useEffect(() => {
    const changed=active(previousStatus.current) && active(status) && previousStatus.current!==status;
    previousStatus.current=status;
    if (!active(status)) { halt(); modeRef.current='idle'; setMode('idle'); }
    else if (changed) {
      road.current=null;distance.current=0;
      if (modeRef.current!=='gps') {
        halt();changeMode('idle');
        setMessage('Pedido recogido. Inicia el recorrido a entrega desde tu última posición compartida.');
      }
    }
  }, [status, halt]);
  useEffect(() => {
    const leave = () => {
      const wasSharing = modeRef.current !== 'idle';
      halt(); modeRef.current='idle';
      if (wasSharing && session) void fetch('/api/v1'+endpoint, {method:'DELETE',keepalive:true,
        headers:{Authorization:'Bearer '+session.token}, referrerPolicy:'no-referrer'}).catch(()=>{});
    };
    const sessionChange = (event: StorageEvent) => { if (event.key === 'fd.session' || event.key === null) { leave(); setMode('idle'); setMessage('La sesión cambió. Se detuvo el envío.'); } };
    window.addEventListener('pagehide',leave); window.addEventListener('storage',sessionChange);
    return () => { window.removeEventListener('pagehide',leave); window.removeEventListener('storage',sessionChange); leave(); };
  }, [endpoint, session, halt]);
  return {mode,message,simulate,pause,stop,gps,prepareTransition,setSpeed:(value:number)=>{speed.current=value;},deviate:()=>{deviation.current=3;setMessage("Escenario de desvío: tres muestras a 110 m de la ruta.");}};
}
