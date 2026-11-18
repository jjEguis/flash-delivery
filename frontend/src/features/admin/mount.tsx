import {createRoot} from 'react-dom/client';
import {ThemeProvider} from '../../app/ThemeProvider';
import {Approvals} from './Approvals';
import type {Session} from '../geo/api';
export function mountApprovals(node:HTMLElement, session:Session) {
  const root=createRoot(node);root.render(<ThemeProvider><Approvals session={session}/></ThemeProvider>);
  return ()=>root.unmount();
}
