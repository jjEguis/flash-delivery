import {useEffect,useRef,useState} from 'react';
import {geoApi,GeoError} from '../geo/api';
import type {Session} from '../geo/api';
import './approvals.css';
type Kind='stores'|'couriers';
type Status='PENDING'|'ENABLED'|'SUSPENDED';
type Profile={storeId?:string;courierId?:string;name:string;zoneId:string;approvalStatus:Status;version:number;activeOrderId?:string|null};
type Audit={eventId:string;actorId:string;occurredAt:string;fromStatus:Status;toStatus:Status;reason:string;profileVersion:number};
type Page<T>={items:T[];nextCursor:string|null};
const labels:Record<Status,string>={PENDING:'Pendiente',ENABLED:'Habilitado',SUSPENDED:'Suspendido'};
const identity=(p:Profile)=>p.storeId||p.courierId||'';
const message=(e:unknown)=>e instanceof Error?e.message:'No se pudo completar la consulta';
export function Approvals({session}:{session:Session}) {
  const [selected,setSelected]=useState<{kind:Kind;id:string}|null>(null);
  const [revision,setRevision]=useState(0);
  return <div className="approvals"><p className="muted">Revisa nuevos registros y consulta el historial de cada decisión.</p>
    <div className="approvals-grid">{(['stores','couriers'] as Kind[]).map(kind=><ProfileList key={kind} {...{kind,session,revision}} onSelect={id=>setSelected({kind,id})}/>)}</div>
    {selected&&<Review key={selected.kind+selected.id} {...selected} session={session} onClose={()=>setSelected(null)} onChanged={()=>setRevision(n=>n+1)}/>}
  </div>;
}
function ProfileList({kind,session,revision,onSelect}:{kind:Kind;session:Session;revision:number;onSelect:(id:string)=>void}) {
  const [status,setStatus]=useState<Status>('PENDING');
  const [page,setPage]=useState<Page<Profile>>({items:[],nextCursor:null});
  const [cursorState,setCursorState]=useState<{value:string|null;revision:number}>({value:null,revision});
  const cursor=cursorState.revision===revision?cursorState.value:null;
  const setCursor=(value:string|null)=>setCursorState({value,revision});
  const [refresh,setRefresh]=useState(0);
  const [busy,setBusy]=useState(true);const [error,setError]=useState('');
  useEffect(()=>{
    const controller=new AbortController();
    const params=new URLSearchParams({status,limit:'10',...(cursor?{cursor}:{})});
    geoApi<Page<Profile>>(`/admin/${kind}?${params}`,session,'GET',undefined,controller.signal).then(result=>{
      setPage(old=>({items:cursor?[...old.items,...result.items].filter((item,i,all)=>all.findIndex(p=>identity(p)===identity(item))===i):result.items,nextCursor:result.nextCursor}));
      setError('');setBusy(false);
    }).catch(e=>{if(!controller.signal.aborted){setError(message(e));setBusy(false);}});
    return ()=>controller.abort();
  },[kind,status,cursor,refresh,revision,session]);
  function reload(){setBusy(true);setCursor(null);setRefresh(n=>n+1);}
  return <section className="card approval-list" id={`admin-${kind}`} tabIndex={-1}>
    <div className="approval-heading"><h2>{kind==='stores'?'Comercios':'Repartidores'}</h2><button className="btn btn--ghost" onClick={reload} disabled={busy}>Actualizar</button></div>
    <label htmlFor={`approval-status-${kind}`}>Estado de {kind==='stores'?'comercios':'repartidores'}</label>
    <select id={`approval-status-${kind}`} value={status} onChange={e=>{setBusy(true);setPage({items:[],nextCursor:null});setCursor(null);setStatus(e.target.value as Status);}}>{Object.entries(labels).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select>
    {error&&<p role="alert">{error} <button className="btn btn--ghost" onClick={reload}>Reintentar</button></p>}
    <div aria-live="polite">{busy?<p className="muted">Consultando perfiles…</p>:!error&&!page.items.length&&<p className="approval-empty">No hay perfiles en esta página con estado «{labels[status]}».</p>}</div>
    <ul className="approval-rows">{page.items.map(p=><li key={identity(p)}><div><strong>{p.name}</strong><span className="muted">Zona {p.zoneId}</span><span className={`approval-status approval-${p.approvalStatus}`}>{labels[p.approvalStatus]}</span></div><button className="btn btn--ghost" aria-label={`Revisar perfil de ${p.name}`} onClick={()=>onSelect(identity(p))}>Revisar perfil</button></li>)}</ul>
    {page.nextCursor&&<button className="btn btn--block btn--ghost" disabled={busy} onClick={()=>{setBusy(true);setCursor(page.nextCursor);setRefresh(n=>n+1);}}>Cargar más {kind==='stores'?'comercios':'repartidores'}</button>}
  </section>;
}
function Review({kind,id,session,onClose,onChanged}:{kind:Kind;id:string;session:Session;onClose:()=>void;onChanged:()=>void}) {
  const dialog=useRef<HTMLDialogElement>(null);const pending=useRef(false);
  const [profile,setProfile]=useState<Profile|null>(null);const [audit,setAudit]=useState<Page<Audit>>({items:[],nextCursor:null});
  const [reason,setReason]=useState('');const [confirmation,setConfirmation]=useState<boolean|null>(null);
  const [error,setError]=useState('');const [notice,setNotice]=useState('');const [busy,setBusy]=useState(false);const [refresh,setRefresh]=useState(0);
  const base=`/admin/${kind}/${encodeURIComponent(id)}`;
  useEffect(()=>{dialog.current?.showModal();},[]);
  useEffect(()=>{
    const controller=new AbortController();
    Promise.all([geoApi<Profile>(base,session,'GET',undefined,controller.signal),geoApi<Page<Audit>>(base+'/events?limit=10',session,'GET',undefined,controller.signal)]).then(([p,a])=>{setProfile(p);setAudit(a);}).catch(e=>{if(!controller.signal.aborted)setError(message(e));});
    return ()=>controller.abort();
  },[base,session,refresh]);
  async function save(){
    if(!profile||confirmation===null||pending.current)return;
    pending.current=true;setBusy(true);setError('');
    try{
      const result=await geoApi<Profile>(base,session,'PATCH',{enabled:confirmation,expectedVersion:profile.version,reason:reason.trim()});
      setProfile(result);setConfirmation(null);setReason('');setNotice('Estado confirmado.');onChanged();setRefresh(n=>n+1);
    }catch(e){setError(message(e));setConfirmation(null);if(e instanceof GeoError&&e.status===409)setRefresh(n=>n+1);}
    finally{pending.current=false;setBusy(false);}
  }
  async function more(){
    if(!audit.nextCursor||pending.current)return;pending.current=true;setBusy(true);
    try{const result=await geoApi<Page<Audit>>(base+'/events?limit=10&cursor='+encodeURIComponent(audit.nextCursor),session);setAudit(old=>({items:[...old.items,...result.items],nextCursor:result.nextCursor}));}
    catch(e){setError(message(e));}finally{pending.current=false;setBusy(false);}
  }
  return <dialog className="approval-dialog" ref={dialog} aria-labelledby="approval-title" onClose={onClose}>
    <div className="approval-heading"><h2 id="approval-title">Revisar perfil</h2><button className="btn btn--ghost" autoFocus onClick={()=>dialog.current?.close()}>Cerrar</button></div>
    {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
    {!profile?<><p>Consultando perfil…</p>{error&&<button className="btn" onClick={()=>{setError('');setRefresh(n=>n+1);}}>Reintentar</button>}</>:<>
      <h3>{profile.name}</h3><dl><dt>Identificador</dt><dd>{id}</dd><dt>Zona</dt><dd>{profile.zoneId}</dd><dt>Estado</dt><dd>{labels[profile.approvalStatus]}</dd><dt>Versión</dt><dd>{profile.version}</dd></dl>
      {profile.activeOrderId&&<p className="notice">Entrega activa: {profile.activeOrderId}. Finalízala o resuélvela antes de suspender este perfil.</p>}
      {confirmation===null?<form onSubmit={e=>e.preventDefault()}>
        <label htmlFor="approval-reason">Motivo de la decisión</label><textarea id="approval-reason" maxLength={300} required value={reason} onChange={e=>setReason(e.target.value)}/>
        <p className="muted">Se guardará junto con tu usuario y la fecha. Máximo 300 caracteres.</p>
        <div className="approval-actions">{profile.approvalStatus!=='ENABLED'&&<button className="btn" disabled={busy||!reason.trim()} onClick={()=>setConfirmation(true)}>Habilitar perfil</button>}
          {profile.approvalStatus!=='SUSPENDED'&&<button className="btn btn--danger" disabled={busy||!reason.trim()||Boolean(profile.activeOrderId)} onClick={()=>setConfirmation(false)}>Suspender perfil</button>}</div>
      </form>:<div className="notice"><h3>Confirmar {confirmation?'habilitación':'suspensión'}</h3><p>{profile.name} quedará {confirmation?'habilitado para operar':'suspendido'}. Motivo: {reason.trim()}</p><div className="approval-actions"><button className="btn btn--ghost" autoFocus disabled={busy} onClick={()=>setConfirmation(null)}>Cancelar</button><button className={`btn ${confirmation?'':'btn--danger'}`} disabled={busy} onClick={save}>{busy?'Guardando…':'Confirmar decisión'}</button></div></div>}
      <h3>Historial de decisiones</h3>{!audit.items.length?<p className="muted">Sin decisiones registradas. Los cambios anteriores a esta función no tienen auditoría.</p>:<ol className="approval-history">{audit.items.map(event=><li key={event.eventId}><strong>{labels[event.fromStatus]} → {labels[event.toStatus]}</strong><p>{event.reason}</p><small>{event.actorId} · {new Date(event.occurredAt).toLocaleString('es-CO')} · versión {event.profileVersion}</small></li>)}</ol>}
      {audit.nextCursor&&<button className="btn btn--ghost" disabled={busy} onClick={more}>Cargar más decisiones</button>}
    </>}
  </dialog>;
}
