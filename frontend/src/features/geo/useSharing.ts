import { useCallback, useEffect, useRef, useState } from 'react';
import { active, DEMO_ROUTE, geoApi, GeoError, readSession } from './api';
import type { Point, Session } from './api';

type Mode = 'idle' | 'simulating' | 'paused' | 'gps' | 'finished';
export function useSharing(orderId: string, session: Session | null, status: string, onPoint: () => void) {
  const [mode, setMode] = useState<Mode>('idle');
  const [message, setMessage] = useState('Ubicación desactivada. Tú decides cuándo compartir.');
  const modeRef = useRef<Mode>('idle');
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const watch = useRef<number | undefined>(undefined);
  const index = useRef(0);
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
    halt(); changeMode('idle');
    setMessage('Ubicación desactivada.');
    try { if (session) await geoApi(endpoint, session, 'DELETE'); onPoint(); }
    catch { setMessage('Se detuvo el envío. No se pudo borrar la última ubicación; vencerá en un máximo de 120 segundos.'); }
  }, [halt, session, endpoint, onPoint]);
  const send = useCallback(async (point: Point, current: number) => {
    if (sending.current || generation.current !== current || !session) return false;
    if (readSession()?.token !== session.token) { halt(); changeMode('idle'); return false; }
    sending.current = true;
    const controller = new AbortController(); request.current = controller;
    try {
      const result = await geoApi<{accepted: boolean}>(endpoint, session, 'POST', point, controller.signal);
      if (generation.current !== current) return false;
      if (!result.accepted) { setMessage('Muestra anterior ignorada. Esperando la siguiente ubicación.'); return false; }
      setMessage('Ubicación enviada.'); onPoint(); return true;
    } catch (error) {
      if (generation.current !== current) return false;
      if (error instanceof GeoError && [401,403,404,409].includes(error.status)) {
        halt(); changeMode('idle'); setMessage('Se detuvo el envío: revisa la sesión o el estado de la entrega.');
      } else setMessage('No se pudo enviar la ubicación. El estado de la entrega sigue disponible.');
      return false;
    } finally { if (generation.current === current) sending.current = false; }
  }, [session, endpoint, halt, onPoint]);
  const simulate = useCallback((restart = false) => {
    if (!session || !active(status)) return;
    halt(); if (restart || index.current >= DEMO_ROUTE.length) index.current = 0;
    changeMode('simulating');
    const current = generation.current;
    const tick = async () => {
      if (generation.current !== current || modeRef.current !== 'simulating') return;
      const coordinate = DEMO_ROUTE[index.current];
      const accepted = await send({ latitude:coordinate[0], longitude:coordinate[1], accuracyMeters:10,
        recordedAt:new Date().toISOString(), source:'SIMULATED' }, current);
      if (generation.current !== current) return;
      if (accepted) index.current++;
      if (index.current >= DEMO_ROUTE.length) { changeMode('finished'); setMessage('Recorrido finalizado. Esto no marca el pedido como entregado.'); return; }
      timer.current = setTimeout(tick, Math.max(3000, Number(import.meta.env.VITE_GEO_INTERVAL_MS) || 4000));
    };
    // También al reanudar se respeta el intervalo mínimo del servidor.
    timer.current = setTimeout(tick, 4000);
  }, [session, status, halt, send]);
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
        recordedAt:new Date(position.timestamp).toISOString(), source:'BROWSER_GPS'},current);
    }, () => {
      halt(); changeMode('idle'); setMessage('No se pudo usar el GPS. Revisa el permiso del navegador; puedes continuar por estados.');
    }, { enableHighAccuracy:false, maximumAge:0, timeout:15000 }); }
    catch { halt(); changeMode('idle'); setMessage('No se pudo usar el GPS. Puedes continuar por estados.'); }
  };
  useEffect(() => {
    if (!active(status)) { halt(); modeRef.current='idle'; }
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
  return {mode,message,simulate,pause,stop,gps};
}
