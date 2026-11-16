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
