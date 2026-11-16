import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { ArrowLeft, FlaskConical, LocateFixed, MapPin, Pause, Play, RotateCcw, Square, Zap } from 'lucide-react';
import { ThemeSwitcher } from '../../app/AppShell';
import { StatusBadge } from '../../components/ui';
import type { OrderStatus } from '../../mocks/data';
import { active, geoApi, GeoError, readSession } from './api';
import type { Latest } from './api';
import { LocationMap } from './LocationMap';
import { useSharing } from './useSharing';

const statuses: Record<string,string> = {PENDING:'Por asignar',ASSIGNED:'Asignada',PICKED_UP:'Recogida',DELIVERED:'Entregada',CANCELLED:'Cancelada',FAILED:'Fallida'};
export function GeoPage({ publicView = false }: { publicView?: boolean }) {
  const { id = '' } = useParams();
  const [session] = useState(() => publicView ? null : readSession());
  const [data,setData] = useState<Latest | null>(null);
  const [error,setError] = useState('');
  const [fatal,setFatal] = useState(false);
  const [loading,setLoading] = useState(true);
  const [revokeMessage,setRevokeMessage] = useState('');
  const [consent,setConsent] = useState(false);
  const [source,setSource] = useState((import.meta.env.DEV || import.meta.env.VITE_GEO_SIMULATOR==='true') ? 'SIMULATED' : 'BROWSER_GPS');
  const endpoint = publicView ? `/tracking/${encodeURIComponent(id)}` : `/orders/${encodeURIComponent(id)}`;
  const refresh = useCallback(async (signal?: AbortSignal) => {
    try {
      const result = await geoApi<Latest>(endpoint+'/location',session,'GET',undefined,signal);
      if (signal?.aborted) return;
      setData(result); setError(''); setFatal(false);
    } catch (error) {
      if (signal?.aborted) return;
      const inaccessible = error instanceof GeoError && [401,403,404].includes(error.status);
      setFatal(inaccessible); setError(inaccessible ? 'Este enlace o sesión no permite consultar la ubicación.' : 'La ubicación no está disponible en este momento. Puedes seguir el pedido por sus estados.');
      setData(previous => previous ? {...previous,location:null,freshness:'UNAVAILABLE'} : null);
      if (!inaccessible) {
        try {
          const order = await geoApi<{orderId:string;status:string;updatedAt:string}>(endpoint,session,'GET',undefined,signal);
          if (!signal?.aborted) setData({...order,location:null,freshness:'UNAVAILABLE'});
        } catch { /* La indisponibilidad de estados no crea coordenadas ni permisos. */ }
      }
    } finally { if (!signal?.aborted) setLoading(false); }
  }, [endpoint,session]);
  const onPoint = useCallback(() => { void refresh(); }, [refresh]);
  const sharing = useSharing(id,session,data?.status || '',onPoint);
  useEffect(() => {
    const controller = new AbortController(); void refresh(controller.signal);
    const timer = setInterval(() => { void refresh(controller.signal); },5000);
    return () => {controller.abort(); clearInterval(timer);};
  }, [refresh]);
  const enabled = !publicView && session?.actor.role==='COURIER' && !!data && active(data.status) && !fatal;
  const running = ['simulating','gps'].includes(sharing.mode);
  const point = data?.location || null;
  // La etiqueta obsoleta se calcula también al mostrar una muestra en el cliente.
  const stale = data?.freshness === 'STALE' || !!point && Date.now()-Date.parse(point.recordedAt)>30000;
  async function revoke() {
    try { await geoApi(endpoint+'/tracking-token',session,'DELETE'); setRevokeMessage('Enlace revocado. El destinatario ya no puede consultarlo.'); }
    catch { setRevokeMessage('No se pudo revocar el enlace. Reintenta.'); }
  }
  return <div className="geo-page"><header className="geo-header"><a href="/" className="design-brand"><Zap size={22} aria-hidden="true" />FlashDelivery</a><ThemeSwitcher /></header>
    <main className="geo-main"><a className="geo-back" href={publicView ? '/#/seguimiento/'+encodeURIComponent(id) : '/#/'+(session?.actor.role==='COURIER'?'repartidor':'comercio')}><ArrowLeft size={16} aria-hidden="true" />Volver al pedido</a>
      <div className="geo-heading"><div><h1>{publicView ? data && active(data.status) ? 'Tu entrega, en camino.' : data && ['DELIVERED','CANCELLED','FAILED'].includes(data.status) ? 'El recorrido terminó.' : 'Sigue tu entrega.' : 'Seguimiento de la entrega'}</h1><p>Consulta la última ubicación compartida durante esta entrega.</p></div><MapPin size={28} aria-hidden="true" /></div>
      {loading && <p role="status">Consultando el estado de tu entrega…</p>}
      {error && <div className="geo-notice" role="alert">{error}<button className="button button-secondary" onClick={() => void refresh()}>Reintentar</button></div>}
      {!publicView && !session && <p>Inicia sesión en <a href="/">la aplicación</a> y abre el seguimiento desde tu pedido.</p>}
      <div className="geo-grid"><section className="geo-card" aria-label="Ubicación de la entrega"><div className="geo-card-heading"><h2>Última ubicación</h2>{data && data.status in statuses ? <StatusBadge status={data.status as OrderStatus}/> : <span>Sin datos</span>}</div>
        {point?.source==='SIMULATED' && <p className="geo-simulation"><FlaskConical size={17} aria-hidden="true" />Modo simulación · Recorrido ficticio</p>}
        {point?.source==='BROWSER_GPS' && <p className="geo-simulation"><LocateFixed size={17} aria-hidden="true" />GPS del navegador</p>}
        {stale && <p className="geo-notice" role="status">Ubicación desactualizada. El marcador muestra la última muestra conocida.</p>}
        <LocationMap point={point}/>
        <div className="geo-map-meta" aria-live="polite">{point ? <><strong>Actualizada {new Date(point.recordedAt).toLocaleTimeString('es-CO')}</strong><span>Latitud {point.latitude.toFixed(5)} · Longitud {point.longitude.toFixed(5)}{point.accuracyMeters!==undefined ? ` · Precisión ${point.accuracyMeters.toFixed(0)} m` : ''}</span></> : <span>Sin posición disponible. No se muestran coordenadas de ejemplo.</span>}</div>
      </section>
      <aside className="geo-aside">{enabled ? <section className="geo-card"><h2>Compartir mi ubicación</h2><p className="geo-muted">Solo mientras esta entrega esté activa. Puedes detener el envío cuando quieras.</p>
        <label className="geo-field">Fuente<select value={source} disabled={running} onChange={event=>{setSource(event.target.value);setConsent(false);}}>
          {(import.meta.env.DEV || import.meta.env.VITE_GEO_SIMULATOR==='true') && <option value="SIMULATED">Simulación de desarrollo</option>}<option value="BROWSER_GPS">GPS del navegador</option></select></label>
        <label className="geo-consent"><input type="checkbox" checked={consent} disabled={running} onChange={event=>setConsent(event.target.checked)}/><span>{source==='BROWSER_GPS'?'Autorizo compartir mi GPS durante esta entrega.':'Quiero compartir el recorrido ficticio con los participantes de esta entrega.'}</span></label>
        <div className="geo-actions">{source==='SIMULATED' && (import.meta.env.DEV || import.meta.env.VITE_GEO_SIMULATOR==='true') ? <>
          <button className="button button-primary" disabled={!consent || running} onClick={()=>sharing.simulate()}><Play size={17}/>{sharing.mode==='paused'?'Reanudar':'Iniciar simulación'}</button>
          <button className="button button-secondary" disabled={sharing.mode!=='simulating'} onClick={sharing.pause}><Pause size={17}/>Pausar</button>
          <button className="button button-secondary" disabled={!consent} onClick={()=>sharing.simulate(true)}><RotateCcw size={17}/>Reiniciar</button>
        </> : <button className="button button-primary" disabled={!consent || running} onClick={sharing.gps}><LocateFixed size={17}/>Activar GPS</button>}
          <button className="button button-secondary" onClick={()=>void sharing.stop()}><Square size={17}/>Detener y borrar ubicación</button>
        </div><p className="geo-muted" role="status">{sharing.message}</p>
      </section> : <section className="geo-card"><h2>Seguimiento por estados</h2><p className="geo-muted">{data && !active(data.status)?'Esta entrega no está en recorrido. No se comparte ubicación.':'El repartidor decide cuándo compartir ubicación durante la entrega.'}</p><p>Sin GPS, el pedido puede avanzar normalmente.</p></section>}
      {!publicView && session?.actor.role==='STORE' && data && !fatal && <section className="geo-card"><h2>Enlace del destinatario</h2><p className="geo-muted">Revocarlo retira el acceso público a los estados y la ubicación.</p><button className="button button-danger" onClick={()=>void revoke()}>Revocar enlace público</button><p role="status">{revokeMessage}</p></section>}
      <p className="geo-privacy">Compartimos solo la última posición. Se elimina al terminar la entrega y vence automáticamente si deja de actualizarse. No almacenamos una trayectoria.</p></aside></div>
    </main></div>;
}
