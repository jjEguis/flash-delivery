import { createContext, useContext, useState } from 'react';
import type { ReactNode } from 'react';
import { sampleOrders } from '../mocks/data';
import type { DemoOrder } from '../mocks/data';

export type Scenario = 'ready' | 'loading' | 'empty' | 'error' | 'conflict';
type DemoContextValue = {
  orders: DemoOrder[]; setOrders: (orders: DemoOrder[]) => void;
  scenario: Scenario; setScenario: (value: Scenario) => void;
  available: boolean; setAvailable: (value: boolean) => void;
  active: DemoOrder | null; setActive: (order: DemoOrder | null) => void;
  completed: DemoOrder[]; setCompleted: (orders: DemoOrder[]) => void;
  notify: (message: string) => void; reset: () => void;
};
const DemoContext = createContext<DemoContextValue | null>(null);

export function DemoProvider({ children }: { children: ReactNode }) {
  const [orders, setOrders] = useState(sampleOrders);
  const [scenario, setScenario] = useState<Scenario>('ready');
  const [available, setAvailable] = useState(true);
  const [active, setActive] = useState<DemoOrder | null>(sampleOrders[1]);
  const [completed, setCompleted] = useState<DemoOrder[]>([sampleOrders[3]]);
  const [notice, setNotice] = useState('');
  const notify = (message: string) => setNotice(message);
  function reset() { setOrders(sampleOrders); setScenario('ready'); setAvailable(true); setActive(sampleOrders[1]); setCompleted([sampleOrders[3]]); setNotice('Demostración restablecida'); }
  return <DemoContext.Provider value={{ orders, setOrders, scenario, setScenario, available, setAvailable, active, setActive, completed, setCompleted, notify, reset }}>
    {children}
    <div className={`toast-preview ${notice ? 'is-visible' : ''}`} role="status" aria-live="polite">
      {notice && <><span>{notice}</span><button type="button" aria-label="Cerrar aviso" onClick={() => setNotice('')}>×</button></>}
    </div>
  </DemoContext.Provider>;
}

export function useDemo() {
  const context = useContext(DemoContext);
  if (!context) throw new Error('DemoProvider no está disponible');
  return context;
}
