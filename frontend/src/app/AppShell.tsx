import { useEffect, useId, useRef, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { ArrowLeft, ArrowUpRight, BarChart3, ChevronDown, Compass, FlaskConical, History, LayoutDashboard, Menu, Monitor, Moon, Package, RotateCcw, Settings2, ShieldCheck, Sun, Truck, UserRound, Waypoints, X, Zap } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useTheme } from './ThemeProvider';
import type { ThemePreference } from './ThemeProvider';
import { useDemo } from './DemoProvider';
import type { Scenario } from './DemoProvider';

type Role = 'store' | 'courier' | 'tracking' | 'admin';
const paths: Record<Role, string> = { store: '/app/store', courier: '/app/courier', tracking: '/track/demo', admin: '/app/admin' };
const roleNames = { store: 'Comercio', courier: 'Repartidor', tracking: 'Destinatario', admin: 'Administración' };
type Item = { label: string; to?: string; icon: LucideIcon };
const menus: Record<Role, Item[]> = {
  store: [{ label: 'Inicio', to: '/app/store', icon: LayoutDashboard }, { label: 'Mis entregas', to: '/app/store/orders', icon: Package },
    { label: 'Estadísticas', icon: BarChart3 }, { label: 'Mi comercio', icon: Settings2 }],
  courier: [{ label: 'Mi jornada', to: '/app/courier', icon: LayoutDashboard }, { label: 'Disponibles', to: '/app/courier/available', icon: Compass },
    { label: 'Historial', to: '/app/courier/history', icon: History }, { label: 'Mi perfil', icon: UserRound }],
  admin: [{ label: 'Inicio', to: '/app/admin', icon: LayoutDashboard }, { label: 'Comercios', icon: Package }, { label: 'Repartidores', icon: Truck }, { label: 'Incidencias', icon: ShieldCheck }],
  tracking: [],
};

export function ThemeSwitcher() {
  const { preference, setPreference } = useTheme();
  const Icon = preference === 'system' ? Monitor : preference === 'dark' ? Moon : Sun;
  return <label className="theme-switcher"><span className="theme-label">Apariencia</span><span className="select-control"><Icon size={16} aria-hidden="true" />
    <select aria-label="Apariencia" value={preference} onChange={event => setPreference(event.target.value as ThemePreference)}>
      <option value="system">Sistema</option><option value="light">Claro</option><option value="dark">Oscuro</option>
    </select><ChevronDown size={13} aria-hidden="true" /></span></label>;
}

function Brand() { return <Link className="design-brand" to="/app/store" aria-label="FlashDelivery, inicio de demostración"><span className="brand-mark"><Zap size={21} fill="currentColor" strokeWidth={1.8} aria-hidden="true" /></span><span>Flash<span className="brand-accent">Delivery</span></span></Link>; }

function Navigation({ role, close }: { role: Role; close?: () => void }) {
  const prefix = useId();
  return <nav className="side-navigation" aria-label={`Navegación de ${roleNames[role]}`}>{menus[role].map(({ label, to, icon: Icon }) => to ?
    <NavLink key={label} to={to} end onClick={close} className={({ isActive }) => isActive ? 'nav-item is-active' : 'nav-item'}><Icon size={19} aria-hidden="true" /><span>{label}</span></NavLink>
    : <div key={label} className="nav-unavailable"><button type="button" className="nav-item" disabled aria-describedby={`${prefix}-${label.replaceAll(' ', '')}`}><Icon size={19} aria-hidden="true" /><span>{label}</span></button>
      <span id={`${prefix}-${label.replaceAll(' ', '')}`} className="nav-future">Próxima etapa</span></div>)}</nav>;
}

export function AppShell() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const role: Role = pathname.startsWith('/track') ? 'tracking' : pathname.includes('/courier') ? 'courier' : pathname.includes('/admin') ? 'admin' : 'store';
  const publicView = role === 'tracking';
  const { scenario, setScenario, reset } = useDemo();
  const drawer = useRef<HTMLDialogElement>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const title = menus[role].find(item => item.to === pathname)?.label || (publicView ? 'Seguimiento' : 'Vista previa');
  const actor = role === 'courier' ? { name: 'Andrés Pérez', initials: 'AP', description: 'Repartidor' } : role === 'admin' ?
    { name: 'Mariana Castro', initials: 'MC', description: 'Administración' } : { name: 'Daniela Rojas', initials: 'DR', description: 'Café del Mar' };
  useEffect(() => {
    document.title = `${title} · FlashDelivery · Vista previa`;
    document.getElementById('design-main')?.focus({ preventScroll: true });
  }, [pathname, title]);
  useEffect(() => {
    if (menuOpen && !drawer.current?.open) drawer.current?.showModal();
    if (!menuOpen && drawer.current?.open) drawer.current.close();
  }, [menuOpen]);
  function changeRole(value: string) { setScenario('ready'); navigate(paths[value as Role]); }
  const side = <><div className="side-top"><Brand /><span className="workspace-name">Tu espacio de entregas</span></div><div className="side-menu-label">{roleNames[role]}</div><Navigation role={role} close={() => setMenuOpen(false)} />
    <aside className="side-help"><Waypoints size={27} aria-hidden="true" /><strong>Cada paso cuenta.</strong><p>Claridad para tu operación. Tranquilidad para quien espera.</p><Link to="/track/demo" onClick={() => setMenuOpen(false)}>Ver seguimiento de ejemplo <ArrowUpRight size={15} aria-hidden="true" /></Link></aside>
    <div className="side-profile"><span className="avatar">{actor.initials}</span><div><strong>{actor.name}</strong><span>{actor.description}</span></div><UserRound size={17} aria-hidden="true" /></div></>;
  return <div className={`design-app ${publicView ? 'public-layout' : ''}`}>
    <a className="skip-link" href="#design-main" onClick={event => { event.preventDefault(); document.getElementById('design-main')?.focus(); }}>Saltar al contenido</a>
    {!publicView && <aside className="desktop-sidebar">{side}</aside>}
    {!publicView && <dialog ref={drawer} className="navigation-drawer" aria-label="Menú de navegación" onClose={() => setMenuOpen(false)} onClick={event => { if (event.target === event.currentTarget) setMenuOpen(false); }}>
      <button className="drawer-close icon-button" type="button" aria-label="Cerrar menú" onClick={() => setMenuOpen(false)}><X size={21} /></button>{side}</dialog>}
    <div className="design-workspace"><header className="design-topbar"><div className="topbar-start">{publicView ? <Brand /> : <>
      <button className="icon-button menu-toggle" type="button" aria-label="Abrir menú" aria-expanded={menuOpen} onClick={() => setMenuOpen(true)}><Menu size={21} /></button>
      <div className="breadcrumb"><span>Tu espacio</span><i>/</i><strong>{title}</strong></div></>}</div>
      <div className="topbar-end"><ThemeSwitcher />{!publicView && <><span className="topbar-divider" /><span className="avatar topbar-avatar" aria-label={`${actor.name}, demostración`}>{actor.initials}</span></>}</div></header>
      <section className="demo-toolbar" aria-label="Controles del prototipo"><p><FlaskConical size={15} aria-hidden="true" /><span>Vista previa <span className="demo-separator">·</span> <strong>Datos simulados</strong></span></p>
        <div className="demo-controls"><label><span>Vista</span><select aria-label="Vista de demostración" value={role} onChange={event => changeRole(event.target.value)}>
          <option value="store">Comercio</option><option value="courier">Repartidor</option><option value="tracking">Destinatario</option><option value="admin">Administrador</option></select></label>
          <label><span>Estado</span><select aria-label="Estado de ejemplo" value={scenario} onChange={event => setScenario(event.target.value as Scenario)}>
            <option value="ready">Con datos</option><option value="loading">Cargando</option><option value="empty">Vacío</option><option value="error">Error</option><option value="conflict">Conflicto</option></select></label>
          <button className="icon-button" type="button" aria-label="Restablecer demostración" title="Restablecer demostración" onClick={reset}><RotateCcw size={16} /></button></div>
      </section>
      <main id="design-main" className="design-content" tabIndex={-1}><Outlet /></main>
      <footer className="design-footer"><span>FlashDelivery <span className="subtle-dot" /> Diseño en revisión</span><a href="http://127.0.0.1:8080/" target="_blank" rel="noreferrer"><ArrowLeft size={13} aria-hidden="true" />Abrir aplicación actual</a></footer>
    </div>
    {!publicView && <nav className="bottom-navigation" aria-label="Navegación móvil">{menus[role].filter(item => item.to).map(({ to, label, icon: Icon }) => <NavLink to={to!} end key={label}><Icon size={20} aria-hidden="true" /><span>{label}</span></NavLink>)}</nav>}
  </div>;
}
