import { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { flushSync } from 'react-dom';
import { ArrowUpRight, Compass, History, LayoutDashboard, LogOut, MapPin, Menu, Package, ShieldCheck, Truck, Waypoints, X, Zap } from 'lucide-react';
import { ThemeProvider } from '../app/ThemeProvider';
import { ThemeSwitcher } from '../app/AppShell';
import type { LucideIcon } from 'lucide-react';
import type { Session } from '../features/geo/api';

type ShellState = { session: Session | null; route: string; profile?: { name:string; description:string } };
type Item = { label:string; href:string; icon:LucideIcon; section?:string };
const homes:Record<string,string>={STORE:'comercio',COURIER:'repartidor',ADMIN:'admin'};
const roles:Record<string,string>={STORE:'Comercio',COURIER:'Repartidor',ADMIN:'Administración'};
const items:Record<string,Item[]>={
  STORE:[{label:'Inicio',href:'#/comercio',icon:LayoutDashboard},{label:'Mis entregas',href:'#/comercio',section:'store-orders',icon:Package},{label:'Nueva entrega',href:'#/comercio',section:'new-delivery',icon:Truck},{label:'Mi zona',href:'#/comercio',section:'store-presence',icon:MapPin}],
  COURIER:[{label:'Mi jornada',href:'#/repartidor',icon:LayoutDashboard},{label:'Disponibles',href:'#/repartidor',section:'courier-open',icon:Compass},{label:'Historial',href:'#/repartidor',section:'courier-history',icon:History}],
  ADMIN:[{label:'Inicio',href:'#/admin',icon:LayoutDashboard},{label:'Comercios',href:'#/admin',section:'admin-stores',icon:Package},{label:'Repartidores',href:'#/admin',section:'admin-couriers',icon:Truck},{label:'Pedidos',href:'#/admin',section:'admin-orders',icon:ShieldCheck}],
};

function LiveShell({session,route,profile}:ShellState) {
  const publicView=!session || ['seguimiento','mapa'].includes(route);
  const [open,setOpen]=useState(false);
  const [section,setSection]=useState('');
  const drawer=useRef<HTMLDialogElement>(null);
  const role=session?.actor.role || 'STORE';
  const menu=items[role] || [];
  const home='#/'+homes[role];
  const roleName=roles[role] || '';
  const title=route==='ubicacion'?'Seguimiento de la entrega':publicView?route==='seguimiento'||route==='mapa'?'Seguimiento':'Bienvenido':menu.find(item=>item.section===section)?.label || menu[0]?.label;
  const name=profile?.name || session?.actor.actorId || '';
  const initials=name.slice(0,2).toUpperCase();
  useEffect(()=>{setSection('');setOpen(false);},[route,roleName]);
  useEffect(()=>{document.title=`${title || roleName} · FlashDelivery`;},[title,roleName]);
  useEffect(()=>{
    if(open&&!drawer.current?.open) drawer.current?.showModal();
    if(!open&&drawer.current?.open) drawer.current.close();
  },[open]);
  function select(event:React.MouseEvent<HTMLAnchorElement>, item:Item) {
    setOpen(false);setSection(item.section || '');
    if(location.hash===item.href) {
      event.preventDefault();
      const target=item.section?document.getElementById(item.section):document.getElementById('app');
      target?.scrollIntoView({block:'start'});target?.focus({preventScroll:true});
    } else if(item.section) {
      const wait=setInterval(()=>{const target=document.getElementById(item.section!);if(target){clearInterval(wait);target.scrollIntoView();target.focus({preventScroll:true});}},100);
      setTimeout(()=>clearInterval(wait),3000);
    }
  }
  const brand=<a className="design-brand" href={publicView?'#/':home}><Zap size={22} fill="currentColor" strokeWidth={1.8} aria-hidden="true"/><span>Flash<span className="brand-accent">Delivery</span></span></a>;
  const links=(mobile=false)=><nav className={mobile?'live-bottom-links':'side-navigation'} aria-label={mobile?'Navegación móvil':`Navegación de ${roleName}`}>
    {menu.map(item=><a key={item.label} href={item.href} className={!mobile?`nav-item ${section===(item.section||'')&&route!== 'ubicacion'?'is-active':''}`:section===(item.section||'')?'is-active':''} aria-current={section===(item.section||'')&&route!=='ubicacion'?'page':undefined} onClick={event=>select(event,item)}><item.icon size={mobile?20:19} aria-hidden="true"/><span>{item.label}</span></a>)}
  </nav>;
  const side=<><div className="side-top">{brand}<span className="workspace-name">Tu espacio de entregas</span></div><div className="side-menu-label">{roleName}</div>{links()}
    <aside className="side-help"><Waypoints size={26} aria-hidden="true"/><strong>Cada paso cuenta.</strong><p>El estado de tus entregas, siempre a mano.</p><a href="#/seguimiento" onClick={()=>setOpen(false)}>Seguir un pedido <ArrowUpRight size={15} aria-hidden="true"/></a></aside>
    <div className="side-profile"><span className="avatar">{initials}</span><div><strong>{name}</strong><span>{profile?.description || roleName}</span></div><button className="icon-button live-logout" aria-label="Cerrar sesión" onClick={()=>document.dispatchEvent(new Event('flashdelivery:logout'))}><LogOut size={18} aria-hidden="true"/></button></div></>;
  return <div className={`design-app live-app ${publicView?'public-layout':''}`}>
    <a className="skip-link" href="#app" onClick={event=>{event.preventDefault();document.getElementById('app')?.focus();}}>Saltar al contenido</a>
    {!publicView&&<aside className="desktop-sidebar">{side}</aside>}
    {!publicView&&<dialog ref={drawer} className="navigation-drawer" aria-label="Menú de navegación" onClose={()=>setOpen(false)} onClick={event=>{if(event.target===event.currentTarget)setOpen(false);}}><button className="drawer-close icon-button" aria-label="Cerrar menú" onClick={()=>setOpen(false)}><X size={20} aria-hidden="true"/></button>{side}</dialog>}
    <div className="design-workspace"><header className="design-topbar"><div className="topbar-start">{publicView?brand:<><button className="icon-button menu-toggle" aria-label="Abrir menú" aria-expanded={open} onClick={()=>setOpen(true)}><Menu size={22} aria-hidden="true"/></button><div className="breadcrumb"><span>Tu espacio</span><i>/</i><strong>{title}</strong></div></>}</div>
      <div className="topbar-end"><ThemeSwitcher/>{!publicView&&<><span className="topbar-divider"/><span className="avatar topbar-avatar" aria-label={name}>{initials}</span></>}</div></header>
      <main id="app" className="design-content live-content" tabIndex={-1}/>
      <footer className="design-footer"><span>FlashDelivery · Cada paso cuenta.</span><a href="#/seguimiento"><MapPin size={14} aria-hidden="true"/>Seguir un pedido</a></footer>
    </div>
    <div id="toast" className="toast" role="status" hidden/>
    {!publicView&&<div className="bottom-navigation">{links(true)}</div>}
  </div>;
}

let root:ReturnType<typeof createRoot>;
let state:ShellState={session:null,route:''};
function paint(){flushSync(()=>root.render(<ThemeProvider><LiveShell {...state}/></ThemeProvider>));}
export function installShell(){root=createRoot(document.getElementById('live-root')!);paint();return document.getElementById('app')!;}
export function updateShell(session:Session|null,route:string){state={session,route,profile:state.session?.actor.actorId===session?.actor.actorId?state.profile:undefined};paint();}
export function updateProfile(name:string,description:string){state={...state,profile:{name,description}};paint();}
