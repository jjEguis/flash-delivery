import { useEffect, useRef } from 'react';
import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { AlertCircle, ArrowUpRight, Check, CheckCheck, Circle, Clock3, PackageCheck, Truck, X, XCircle } from 'lucide-react';
import type { DemoOrder, OrderStatus } from '../mocks/data';
import { money } from '../mocks/data';
import { useDemo } from '../app/DemoProvider';

export function Button({ children, variant = 'primary', className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost' | 'danger' }) {
  return <button type="button" {...props} className={`button button-${variant} ${className}`}>{children}</button>;
}

const states = {
  PENDING: { label: 'Por asignar', icon: Clock3, style: 'pending' },
  ASSIGNED: { label: 'Asignada', icon: Truck, style: 'assigned' },
  PICKED_UP: { label: 'Recogida', icon: PackageCheck, style: 'picked' },
  DELIVERED: { label: 'Entregada', icon: CheckCheck, style: 'delivered' },
  CANCELLED: { label: 'Cancelada', icon: XCircle, style: 'cancelled' },
  FAILED: { label: 'Fallida', icon: AlertCircle, style: 'cancelled' },
};
export function StatusBadge({ status }: { status: OrderStatus }) {
  const state = states[status], Icon = state.icon;
  return <span className={`status-badge status-${state.style}`}><Icon size={13} aria-hidden="true" />{state.label}</span>;
}

export function Modal({ title, open, onClose, children }: { title: string; open: boolean; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (open && !dialog?.open) dialog?.showModal();
    if (!open && dialog?.open) dialog.close();
  }, [open]);
  return <dialog ref={ref} className="modal-preview" aria-label={title} onClose={onClose} onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
    <header className="modal-heading"><div><span className="quiet-label">Demostración</span><h2>{title}</h2></div>
      <button className="icon-button" type="button" aria-label="Cerrar diálogo" onClick={onClose}><X size={20} /></button></header>
    {children}
  </dialog>;
}

export function Feedback({ children, onRetry }: { children: ReactNode; onRetry?: () => void }) {
  return <div className="feedback"><span className="feedback-icon"><AlertCircle size={24} aria-hidden="true" /></span>
    <h3>{children}</h3>{onRetry && <Button variant="secondary" onClick={onRetry}>Volver a intentar</Button>}</div>;
}

export function ScenarioContent({ children }: { children: ReactNode }) {
  const { scenario, setScenario } = useDemo();
  if (scenario === 'loading') return <div className="skeleton-block" role="status" aria-label="Cargando entregas de demostración">
    {[1, 2, 3, 4].map(value => <div className="skeleton-row" key={value}><i /><i /><i /></div>)}<span className="sr-only">Cargando entregas…</span></div>;
  if (scenario === 'empty') return <div className="feedback"><span className="feedback-icon"><PackageCheck size={28} aria-hidden="true" /></span>
    <h3>Todo por empezar</h3><p>No hay entregas en este estado de ejemplo.</p><Button variant="secondary" onClick={() => setScenario('ready')}>Ver entregas de ejemplo</Button></div>;
  if (scenario === 'error') return <Feedback onRetry={() => setScenario('ready')}>No pudimos cargar las entregas. Puedes volver a intentarlo.</Feedback>;
  if (scenario === 'conflict') return <Feedback onRetry={() => setScenario('ready')}>Esta entrega ya fue aceptada. Consulta las demás disponibles.</Feedback>;
  return children;
}

export function DeliveryTimeline({ status }: { status: OrderStatus }) {
  const sequence = [
    { id: 'PENDING', title: 'Solicitud publicada', description: 'El comercio registró la entrega.' },
    { id: 'ASSIGNED', title: 'Repartidor asignado', description: 'La entrega ya tiene quién la lleve.' },
    { id: 'PICKED_UP', title: 'Pedido recogido', description: 'El repartidor confirmó la recogida.' },
    { id: 'DELIVERED', title: 'Entrega finalizada', description: 'El pedido llegó a su destino.' },
  ];
  const reached = sequence.findIndex(step => step.id === status);
  return <ol className="delivery-timeline">{sequence.map((step, i) => <li key={step.id} className={i <= reached ? 'reached' : ''}>
    <span className="timeline-mark">{i <= reached ? <Check size={14} aria-hidden="true" /> : <Circle size={9} aria-hidden="true" />}</span>
    <div><strong>{step.title}</strong><p>{step.description}</p>{i <= reached && <time>15 nov., {['10:30', '10:35', '10:45', '11:00'][i]}</time>}</div>
  </li>)}</ol>;
}

export function OrderTable({ orders, onSelect }: { orders: DemoOrder[]; onSelect: (order: DemoOrder) => void }) {
  return <div className="order-table-wrap" role="region" tabIndex={0} aria-label="Entregas; desplázate horizontalmente para ver todas las columnas"><table className="order-table"><caption className="sr-only">Entregas de demostración de Café del Mar</caption>
    <thead><tr><th>Entrega</th><th>Destino</th><th>Estado</th><th className="align-right">Tarifa</th><th><span className="sr-only">Detalle</span></th></tr></thead>
    <tbody>{orders.map(order => <tr key={order.id}><td><strong>{order.id}</strong><span>Hoy, {order.time}</span></td>
      <td><span className="destination">{order.dropoffAddress}</span><span>{order.zone}</span></td><td><StatusBadge status={order.status} /></td>
      <td className="align-right fee-cell">{money(order.fee)}</td><td><button className="icon-button detail-button" type="button" aria-label={`Ver entrega ${order.id}`} onClick={() => onSelect(order)}><ArrowUpRight size={18} /></button></td></tr>)}</tbody>
  </table></div>;
}
