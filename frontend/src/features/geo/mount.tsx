import { OrderPoints } from './OrderPoints';
import { createRoot } from 'react-dom/client';
import { HashRouter } from 'react-router-dom';
import { ThemeProvider } from '../../app/ThemeProvider';
import { GeoPage } from './GeoPage';
import type { Session } from './api';

export function mountGeo(node:HTMLElement,orderId:string,publicView:boolean, session:Session|null) {
  const root=createRoot(node);
  root.render(<ThemeProvider><HashRouter><GeoPage embedded orderId={orderId} publicView={publicView} activeSession={session}/></HashRouter></ThemeProvider>);
  return ()=>root.unmount();
}

export function mountOrderPoints(node:HTMLElement,onChange:Parameters<typeof OrderPoints>[0]['onChange']) {
  const root=createRoot(node);root.render(<ThemeProvider><OrderPoints onChange={onChange}/></ThemeProvider>);return ()=>root.unmount();
}
