import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { ArrowLeft, FlaskConical, LocateFixed, MapPin, Pause, Play, RotateCcw, Square, Zap } from 'lucide-react';
import { ThemeSwitcher } from '../../app/AppShell';
import { StatusBadge } from '../../components/ui';
import type { OrderStatus } from '../../mocks/data';
import { active, geoApi, GeoError, readSession } from './api';
import type { Latest, Position, RouteResult, Session } from './api';
import { LocationMap } from './LocationMap';
import { useSharing } from './useSharing';

const statuses: Record<string,string> = {PENDING:'Por asignar',ASSIGNED:'Asignada',PICKED_UP:'Recogida',DELIVERED:'Entregada',CANCELLED:'Cancelada',FAILED:'Fallida'};
export function GeoPage({ publicView = false, embedded = false, orderId, activeSession }: { publicView?: boolean; embedded?: boolean; orderId?: string; activeSession?: Session | null }) {
  const { id: routeId = '' } = useParams();
  const id = orderId ?? routeId;
  const [session] = useState(() => publicView ? null : activeSession === undefined ? readSession() : activeSession);
  const [data,setData] = useState<Latest | null>(null);
  const [routing,setRouting]=useState<RouteResult|null>(null);
  const [origin,setOrigin]=useState<Position|null>(null);
  const [speed,setSpeed]=useState(8);
  const [events,setEvents]=useState<{eventType:string;occurredAt:string}[]>([]);
  const inFlight=useRef(false);
  const polling=useRef({terminal:false,failures:0});
  const [transitionPending,setTransitionPending]=useState(false);
  const transitionInFlight=useRef(false);
  const revision=useRef(0);
  const actionKeys=useRef<Record<string,string>>({});
  const [error,setError] = useState('');
  const [fatal,setFatal] = useState(false);
  const [loading,setLoading] = useState(true);
  const [revokeMessage,setRevokeMessage] = useState('');
  const [consent,setConsent] = useState(false);
  const [source,setSource] = useState((import.meta.env.DEV || import.meta.env.VITE_GEO_SIMULATOR==='true') ? 'SIMULATED' : 'BROWSER_GPS');
  const endpoint = publicView ? `/tracking/${encodeURIComponent(id)}` : `/orders/${encodeURIComponent(id)}`;
  const refresh = useCallback(async (signal?: AbortSignal, force=false) => {
    if ((inFlight.current && !force) || signal?.aborted) return;
    inFlight.current=true;const ticket=++revision.current;
    try {
      const result = await geoApi<Latest>(endpoint+'/location',session,'GET',undefined,signal);
      if (signal?.aborted || revision.current!==ticket) return;
      polling.current={terminal:['DELIVERED','CANCELLED','FAILED'].includes(result.status),failures:0};
      setData(result); setError(''); setFatal(false);
      if (active(result.status)) {
        try { const route=await geoApi<RouteResult>(endpoint+'/route',session,'GET',undefined,signal);if (!signal?.aborted && revision.current===ticket) setRouting(route?.points!==undefined?route:null); }
        catch { if (!signal?.aborted && revision.current===ticket) setRouting(null); }
      } else setRouting(null);
    } catch (error) {
      if (signal?.aborted || revision.current!==ticket) return;
      const inaccessible = error instanceof GeoError && [401,403,404].includes(error.status);
      polling.current={terminal:inaccessible,failures:Math.min(4,polling.current.failures+1)};
      setRouting(null);
      setFatal(inaccessible); setError(inaccessible ? 'Este enlace o sesión no permite consultar la ubicación.' : 'La ubicación no está disponible en este momento. Puedes seguir el pedido por sus estados.');
      setData(previous => previous ? {...previous,location:null,freshness:'UNAVAILABLE'} : null);
      if (!inaccessible) {
        try {
          const order = await geoApi<{orderId:string;status:string;updatedAt:string}>(endpoint,session,'GET',undefined,signal);
          if (!signal?.aborted && revision.current===ticket) setData({...order,location:null,freshness:'UNAVAILABLE'});
        } catch { /* La indisponibilidad de estados no crea coordenadas ni permisos. */ }
      }
    } finally {if (revision.current===ticket) {inFlight.current=false; if (!signal?.aborted) setLoading(false);} }
  }, [endpoint,session]);
  const onPoint = useCallback(() => { void refresh(); }, [refresh]);
  const sharing = useSharing(id,session,fatal?'':data?.status || '',onPoint);
  useEffect(() => {
    const controller=new AbortController();let timer:ReturnType<typeof setTimeout>;
    let done=false;
    const poll=async()=>{
      if (document.hidden || controller.signal.aborted || done) return;
      await refresh(controller.signal);
      if (controller.signal.aborted || done) return;
      if (!polling.current.terminal) timer=setTimeout(poll,5000*2**polling.current.failures);
    };
    const visibility=()=>{clearTimeout(timer);if (!document.hidden) void poll();};
    document.addEventListener('visibilitychange',visibility);void poll();
    return ()=>{done=true;controller.abort();clearTimeout(timer);document.removeEventListener('visibilitychange',visibility);};
  }, [refresh]);
  useEffect(()=>{
    const controller=new AbortController();
    if (data?.status && !fatal) void geoApi<{items?:{eventType:string;occurredAt:string}[];events?:{eventType:string;occurredAt:string}[]}>(publicView?endpoint:endpoint+'/events',session,'GET',undefined,controller.signal)
      .then(result=>{if (!controller.signal.aborted) setEvents(result.events || result.items || []);}).catch(()=>{});
    return ()=>controller.abort();
  },[data?.status,fatal,endpoint,session,publicView]);
  const enabled = !publicView && session?.actor.role==='COURIER' && !!data && active(data.status) && !fatal;
  const running = ['simulating','gps'].includes(sharing.mode);
  const point = data?.location || null;
  const hasPoints=!!routing?.points;
  const seed=data?.status==='PICKED_UP' ? point || origin : origin || point;
  const startReason=!routing?'Los puntos del recorrido están pendientes de consulta. Usa «Actualizar recorrido» si no aparecen.':!hasPoints?'Este pedido no tiene puntos de recogida y entrega disponibles. Para probar la ruta, crea un pedido nuevo y selecciona ambos puntos. Puedes continuar por estados o compartir GPS.':!consent?'Marca el consentimiento antes de iniciar.':!(seed || sharing.mode==='paused')?'Selecciona un inicio en el mapa o usa el inicio de demo.':sharing.mode==='finished'?'Confirma la recogida o la entrega con el botón de tu próxima parada.':'';
  useEffect(()=>{setOrigin(null);},[data?.status]);
  // La etiqueta obsoleta se calcula también al mostrar una muestra en el cliente.
  const stale = data?.freshness === 'STALE' || !!point && Date.now()-Date.parse(point.recordedAt)>15000;
  async function revoke() {
    try { await geoApi(endpoint+'/tracking-token',session,'DELETE'); setRevokeMessage('Enlace revocado. El destinatario ya no puede consultarlo.'); }
    catch { setRevokeMessage('No se pudo revocar el enlace. Reintenta.'); }
  }
  async function transition(action:string) {
    if (transitionInFlight.current) return;
    transitionInFlight.current=true;setTransitionPending(true);sharing.prepareTransition();revision.current++;
    actionKeys.current[action] ||= crypto.randomUUID();
    try {
      const result=await geoApi<{status:string}>(`/orders/${encodeURIComponent(id)}/${action}`,session,'POST',{},undefined,actionKeys.current[action]);
      if (!result || !Object.keys(statuses).includes(result.status)) throw new Error('Respuesta incompleta');
      setData(previous=>previous?{...previous,status:result.status}:previous);setRouting(null);
      await refresh(undefined,true);
    } catch {await refresh(undefined,true);setError('La confirmación no llegó. Revisa el estado mostrado; si no cambió, reintenta con el mismo botón.');}
    finally {transitionInFlight.current=false;setTransitionPending(false);}
  }
  const Content = embedded ? 'div' : 'main';
  return <div className={`geo-page ${embedded?'geo-embedded':''}`}>{!embedded && <header className="geo-header"><a href="/" className="design-brand"><Zap size={22} aria-hidden="true" />FlashDelivery</a><ThemeSwitcher /></header>}
    <Content className="geo-main"><a className="geo-back" href={publicView ? '#/seguimiento/'+encodeURIComponent(id) : '#/'+(session?.actor.role==='COURIER'?'repartidor':'comercio')}><ArrowLeft size={16} aria-hidden="true" />Volver al pedido</a>
      <div className="geo-heading"><div><h1>{publicView ? data && active(data.status) ? 'Tu entrega, en camino.' : data && ['DELIVERED','CANCELLED','FAILED'].includes(data.status) ? 'El recorrido terminó.' : 'Sigue tu entrega.' : 'Seguimiento de la entrega'}</h1><p>Consulta la última ubicación compartida durante esta entrega.</p></div><MapPin size={28} aria-hidden="true" /></div>
      {loading && <p role="status">Consultando el estado de tu entrega…</p>}
      {error && <div className="geo-notice" role="alert">{error}<button className="button button-secondary" onClick={() => void refresh()}>Reintentar</button></div>}
      {!publicView && !session && <p>Inicia sesión en <a href="/">la aplicación</a> y abre el seguimiento desde tu pedido.</p>}
      <div className="geo-grid"><section className="geo-card" aria-label="Ubicación de la entrega"><div className="geo-card-heading"><h2>Última ubicación</h2>{data && data.status in statuses ? <StatusBadge status={data.status as OrderStatus}/> : <span>Sin datos</span>}</div>
        {point?.source==='SIMULATED' && <p className="geo-simulation"><FlaskConical size={17} aria-hidden="true" />Modo simulación · Recorrido de demostración</p>}
        {point?.source==='BROWSER_GPS' && <p className="geo-simulation"><LocateFixed size={17} aria-hidden="true" />GPS del navegador</p>}
        {stale && <p className="geo-notice" role="status">Ubicación desactualizada. El marcador muestra la última muestra conocida.</p>}
        <LocationMap point={point} route={routing?.route} points={routing?.points} selection={origin} onPick={enabled && source==='SIMULATED' && !running && hasPoints && !(data?.status==='PICKED_UP' && point) ? setOrigin : undefined}/>
        {routing?.route && <div className="geo-route-summary" aria-live="polite"><div><span>Tiempo estimado</span><strong>{routing.route.etaSeconds!==null && !stale?`${Math.max(1,Math.ceil(routing.route.etaSeconds/60))} min`:'Sin estimación'}</strong></div><div><span>Distancia pendiente</span><strong>{routing.route.remainingMeters>=1000?`${(routing.route.remainingMeters/1000).toFixed(1)} km`:`${Math.round(routing.route.remainingMeters)} m`}</strong></div><p>{routing.route.phase==='ASSIGNED'?'En camino a recogida':'En camino a entrega'} · Perfil automóvil, sin tráfico real.<br/>Calculada {new Date(routing.route.calculatedAt).toLocaleTimeString('es-CO')}. {routing.route.stale?'Ruta desactualizada. ':''}{routing.route.offRoute?'Fuera de ruta; esperando recálculo.':''}</p></div>}

        <div className="geo-map-meta" aria-live="polite"><span>{point?stale?'Señal antigua':'Señal reciente':'Sin señal de ubicación'}</span>{point ? <><strong>Actualizada {new Date(point.recordedAt).toLocaleTimeString('es-CO')}</strong><span>Latitud {point.latitude.toFixed(5)} · Longitud {point.longitude.toFixed(5)}{point.accuracyMeters!==undefined ? ` · Precisión ${point.accuracyMeters.toFixed(0)} m` : ''}</span></> : <span>Sin posición disponible. No se muestran coordenadas de ejemplo.</span>}</div>
      </section>
      <aside className="geo-aside">{enabled && <section className="geo-card geo-next-step"><h2>Tu próxima parada</h2><p>{data?.status==='ASSIGNED'?'Recorre la ruta hasta recogida y confirma cuando tengas el pedido.':'El pedido ya está recogido. Inicia el recorrido a entrega desde la última posición y confirma al entregar.'}</p>{routing?.route?.steps && <p className="geo-muted">{instruction(routing.route)}</p>}<button className="button button-primary" disabled={transitionPending} aria-busy={transitionPending} onClick={()=>void transition(data?.status==='ASSIGNED'?'pickup':'deliver')}>{transitionPending?'Actualizando pedido…':data?.status==='ASSIGNED'?'Marcar recogido':'Marcar entregado'}</button></section>}{enabled ? <section className="geo-card"><h2>Compartir mi ubicación</h2><p className="geo-muted">Solo mientras esta entrega esté activa. Puedes detener el envío cuando quieras.</p>
        <label className="geo-field">Fuente<select value={source} disabled={running} onChange={event=>{setSource(event.target.value);setConsent(false);}}>
          {(import.meta.env.DEV || import.meta.env.VITE_GEO_SIMULATOR==='true') && <option value="SIMULATED">Simulación de desarrollo</option>}<option value="BROWSER_GPS">GPS del navegador</option></select></label>
        <label className="geo-consent"><input type="checkbox" checked={consent} disabled={running} onChange={event=>setConsent(event.target.checked)}/><span>{source==='BROWSER_GPS'?'Autorizo compartir mi GPS durante esta entrega.':'Quiero compartir el recorrido de demostración con los participantes de esta entrega.'}</span></label>
        {source==='SIMULATED' && (import.meta.env.DEV || import.meta.env.VITE_GEO_SIMULATOR==='true') && <div className="geo-demo-controls"><p>{seed?`Inicio del recorrido: ${seed.latitude.toFixed(5)}, ${seed.longitude.toFixed(5)}`:'Selecciona el inicio de la demo en el mapa.'}</p>{data?.status==='PICKED_UP' && point && <p id="demo-origin-help">La salida a entrega usa tu última posición. Para elegir otra salida, primero detén y borra la ubicación.</p>}<button className="button button-secondary" aria-describedby={data?.status==='PICKED_UP' && point?'demo-origin-help':undefined} disabled={running || (data?.status==='PICKED_UP' && !!point)} onClick={()=>setOrigin({latitude:11.244,longitude:-74.211})}>Usar inicio de demo en Santa Marta</button><label className="geo-field">Velocidad de demo (m/s)<input type="range" min="1" max="25" value={speed} onChange={e=>{const value=Number(e.target.value);setSpeed(value);sharing.setSpeed(value);}}/><span>{speed} m/s</span></label><button className="button button-secondary" disabled={!running} onClick={sharing.deviate}>Simular desvío</button></div>}
        {source==='SIMULATED' && startReason && <p className="geo-muted" id="simulation-help">{startReason}</p>}
        {source==='SIMULATED' && <button type="button" className="button button-secondary" disabled={running || transitionPending} onClick={()=>void refresh(undefined,true)}>Actualizar recorrido</button>}
        <div className="geo-actions">{source==='SIMULATED' && (import.meta.env.DEV || import.meta.env.VITE_GEO_SIMULATOR==='true') ? <>
          <button className="button button-primary" disabled={!!startReason || running || transitionPending} aria-describedby={startReason?"simulation-help":undefined} onClick={()=>sharing.simulate(false,seed)}><Play size={17}/>{sharing.mode==='finished'?'Recorrido completado':sharing.mode==='paused'?'Reanudar':'Iniciar simulación'}</button>
          <button className="button button-secondary" disabled={sharing.mode!=='simulating'} onClick={sharing.pause}><Pause size={17}/>Pausar</button>
          <button className="button button-secondary" disabled={!consent || !hasPoints || !seed || transitionPending} onClick={()=>sharing.simulate(true,seed)}><RotateCcw size={17}/>Reiniciar</button>
        </> : <button className="button button-primary" disabled={!consent || running} onClick={sharing.gps}><LocateFixed size={17}/>Activar GPS</button>}
          <button className="button button-secondary" onClick={()=>void sharing.stop()}><Square size={17}/>Detener y borrar ubicación</button>
        </div><p className="geo-muted" role="status">{sharing.message}</p><p className="geo-muted">Mantén esta vista abierta mientras simulas. Salir del mapa detiene el envío; una pausa de más de 120 segundos hace caducar la posición.</p>
      </section> : <section className="geo-card"><h2>Seguimiento por estados</h2><p className="geo-muted">{data && !active(data.status)?'Esta entrega no está en recorrido. No se comparte ubicación.':'El repartidor decide cuándo compartir ubicación durante la entrega.'}</p><p>Sin GPS, el pedido puede avanzar normalmente.</p></section>}
      {!publicView && session?.actor.role==='STORE' && data && !fatal && <section className="geo-card"><h2>Enlace del destinatario</h2><p className="geo-muted">Revocarlo retira el acceso público a los estados y la ubicación.</p><button className="button button-danger" onClick={()=>void revoke()}>Revocar enlace público</button><p role="status">{revokeMessage}</p></section>}

      {events.length>0 && <section className="geo-card"><h2>Recorrido del pedido</h2><ol className="geo-timeline">{events.map((event,index)=><li key={index}><strong>{event.eventType==='CREATED'?'Pedido creado':statuses[event.eventType] || event.eventType}</strong><time dateTime={event.occurredAt}>{new Date(event.occurredAt).toLocaleTimeString('es-CO')}</time></li>)}</ol></section>}
      <p className="geo-privacy">Compartimos solo la última posición. Se elimina al terminar la entrega y vence automáticamente si deja de actualizarse. No almacenamos una trayectoria.</p></aside></div>
    </Content></div>;
}

function instruction(route:NonNullable<RouteResult['route']>) {
  let distance=route.distanceMeters-route.remainingMeters;
  for (const step of route.steps || []) {
    if (distance<step.distanceMeters) {
      const direction:Record<string,string>={left:'izquierda',right:'derecha',straight:'recto','slight left':'ligeramente a la izquierda','slight right':'ligeramente a la derecha','sharp left':'a la izquierda','sharp right':'a la derecha',uturn:'en U'};
      return `${step.type==='arrive'?'Llegada próxima':'Continúa'} ${direction[step.modifier] || 'por la ruta indicada'} durante ${Math.round(step.distanceMeters-distance)} m. Orientación aproximada.`;
    }
    distance-=step.distanceMeters;
  }
  return 'Sigue la ruta indicada hasta tu próxima parada.';
}
