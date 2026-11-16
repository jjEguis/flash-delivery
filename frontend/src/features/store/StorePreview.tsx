import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ArrowRight, ArrowUpRight, CheckCheck, Clock3, Package, Plus, Route, Truck } from 'lucide-react';
import type { DemoOrder, OrderStatus } from '../../mocks/data';
import { money } from '../../mocks/data';
import { useDemo } from '../../app/DemoProvider';
import { Button, DeliveryTimeline, Modal, OrderTable, ScenarioContent, StatusBadge } from '../../components/ui';

function NewDelivery({ onClose }: { onClose: () => void }) {
  const { orders, setOrders, notify } = useDemo();
  const [fields, setFields] = useState({ pickup: 'Calle 17 # 3-42', dropoff: '', fee: '8500' });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [step, setStep] = useState<'form' | 'confirm' | 'loading'>('form');
  function review(event: FormEvent) {
    event.preventDefault();
    const next: Record<string, string> = {};
    if (!fields.pickup.trim()) next.pickup = 'Indica dónde debe recogerse el pedido.';
    if (!fields.dropoff.trim()) next.dropoff = 'Indica la dirección de entrega.';
    if (!Number.isInteger(Number(fields.fee)) || Number(fields.fee) <= 0) next.fee = 'Escribe una tarifa entera mayor que cero.';
    setErrors(next);
    if (!Object.keys(next).length) setStep('confirm');
  }
  async function publish() {
    setStep('loading');
    await new Promise(resolve => setTimeout(resolve, 250));
    setOrders([{ id: `FD-DEMO-${orders.length + 1}`, pickupAddress: fields.pickup.trim(), dropoffAddress: fields.dropoff.trim(),
      zone: 'Centro', fee: Number(fields.fee), status: 'PENDING', time: 'Ahora' }, ...orders]);
    notify('Entrega de demostración creada. No se envió a la API.');
    onClose();
  }
  return <Modal title="Nueva entrega" open onClose={onClose}>
    <p className="modal-description">Prueba el formulario con datos de ejemplo. Ninguna solicitud se enviará al servicio real.</p>
    {step === 'form' ? <form onSubmit={review} noValidate>
      {([['pickup', 'Dirección de recogida'], ['dropoff', 'Dirección de entrega'], ['fee', 'Tarifa (COP)']] as const).map(([key, label]) =>
        <div className="form-field" key={key}><label htmlFor={`demo-${key}`}>{label}</label>
          <input id={`demo-${key}`} type={key === 'fee' ? 'number' : 'text'} value={fields[key]} aria-invalid={!!errors[key]}
            aria-describedby={errors[key] ? `error-${key}` : undefined} maxLength={300}
            onChange={event => setFields({ ...fields, [key]: event.target.value })} />
          {errors[key] && <p id={`error-${key}`} className="field-error" role="alert">{errors[key]}</p>}</div>)}
      <div className="form-field"><span className="field-label">Zona del comercio</span><p className="read-only-field">Centro</p></div>
      <div className="modal-actions"><Button variant="secondary" onClick={onClose}>Cancelar</Button><Button type="submit">Revisar entrega <ArrowRight size={16} /></Button></div>
    </form> : <><div className="review-summary"><p><span>Recogida</span><strong>{fields.pickup}</strong></p><p><span>Destino</span><strong>{fields.dropoff}</strong></p>
      <p><span>Tarifa</span><strong>{money(Number(fields.fee))}</strong></p></div>
      <div className="modal-actions"><Button variant="secondary" disabled={step === 'loading'} onClick={() => setStep('form')}>Volver</Button>
        <Button disabled={step === 'loading'} onClick={publish}>{step === 'loading' ? 'Creando ejemplo…' : 'Confirmar entrega de ejemplo'}</Button></div></>}
  </Modal>;
}

export function StorePreview() {
  const { orders } = useDemo();
  const { pathname } = useLocation();
  const listView = pathname.endsWith('/orders');
  const [newDelivery, setNewDelivery] = useState(false);
  const [selected, setSelected] = useState<DemoOrder | null>(null);
  const [filter, setFilter] = useState<OrderStatus | 'ALL'>('ALL');
  const completed = orders.filter(order => order.status === 'DELIVERED');
  const inProgress = orders.filter(order => ['ASSIGNED', 'PICKED_UP'].includes(order.status));
  const rows = filter === 'ALL' ? orders : orders.filter(order => order.status === filter);
  const metrics = [
    { label: 'Entregas de la jornada', value: String(orders.length).padStart(2, '0'), icon: Package, detail: 'Solicitudes registradas' },
    { label: 'En curso', value: String(inProgress.length).padStart(2, '0'), icon: Truck, detail: 'Ya tienen repartidor' },
    { label: 'Completadas', value: String(completed.length).padStart(2, '0'), icon: CheckCheck, detail: 'Llegaron a su destino' },
    { label: 'Tarifas completadas', value: money(completed.reduce((sum, order) => sum + order.fee, 0)), icon: Route, detail: 'Entregas finalizadas' },
  ];
  return <>
    <section className="page-heading"><div><p className="page-context">Café del Mar <span /> Jornada de ejemplo</p>
      <h1>{listView ? 'Mis entregas' : 'Tu operación, al día.'}</h1><p>{listView ? 'Cada solicitud y su estado, en un solo lugar.' : 'Un vistazo a tus entregas. Tú decides el siguiente paso.'}</p></div>
      <Button onClick={() => setNewDelivery(true)}><Plus size={18} aria-hidden="true" /> Nueva entrega</Button></section>
    {!listView && <section className="metrics-strip" aria-label="Resumen de demostración">{metrics.map(({ label, value, icon: Icon, detail }) =>
      <div className="metric" key={label}><div className="metric-label"><span>{label}</span><Icon size={18} aria-hidden="true" /></div>
        <strong>{value}</strong><span className="metric-detail">{detail}</span></div>)}</section>}
    <div className={listView ? '' : 'store-workspace'}>
      <section className="panel deliveries-panel"><header className="panel-header"><div><h2>{listView ? 'Todas tus entregas' : 'Entregas recientes'}</h2>
        <p>{orders.filter(order => order.status === 'PENDING').length} pendientes de asignación en esta demo</p></div>
        {!listView && <Link className="text-link" to="/app/store/orders">Ver todas <ArrowUpRight size={16} aria-hidden="true" /></Link>}</header>
        {listView && <div className="filter-bar" role="group" aria-label="Filtrar entregas de demostración">{([
          ['ALL', 'Todas'], ['PENDING', 'Por asignar'], ['ASSIGNED', 'Asignadas'], ['PICKED_UP', 'Recogidas'], ['DELIVERED', 'Entregadas'], ['CANCELLED', 'Canceladas'],
        ] as const).map(([value, label]) => <button key={value} type="button" aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}</button>)}</div>}
        <ScenarioContent>{rows.length ? <OrderTable orders={listView ? rows : rows.slice(0, 5)} onSelect={setSelected} /> : <div className="feedback"><h3>No hay entregas en este filtro.</h3></div>}</ScenarioContent>
        {!listView && <footer className="panel-footer"><span>Mostrando {Math.min(5, orders.length)} de {orders.length} entregas de ejemplo</span><span className="subtle-dot" />Datos simulados</footer>}
      </section>
      {!listView && <section className="panel activity-panel"><header className="panel-header"><div><h2>Así va tu jornada</h2><p>Actividad de demostración</p></div><span className="date-chip">15 nov.</span></header>
        <ol className="activity-list">{[
          { icon: Plus, title: 'Una nueva entrega', detail: 'FD-2048 está esperando repartidor', time: '10:42', style: 'brand' },
          { icon: Truck, title: 'Andrés aceptó una entrega', detail: 'FD-2047 ya tiene quién la lleve', time: '10:35', style: 'info' },
          { icon: Package, title: 'Pedido recogido', detail: 'Laura está llevando FD-2046', time: '10:20', style: 'warning' },
          { icon: CheckCheck, title: 'Otra entrega completada', detail: 'FD-2045 llegó a su destino', time: '10:10', style: 'brand' },
        ].map(({ icon: Icon, title, detail, time, style }) => <li key={title}><span className={`activity-symbol tone-${style}`}><Icon size={16} aria-hidden="true" /></span>
          <div><strong>{title}</strong><p>{detail}</p><time>{time}</time></div></li>)}</ol>
        <div className="activity-note"><Clock3 size={15} aria-hidden="true" /><span>Esta actividad es un ejemplo, no una actualización de la operación real.</span></div>
      </section>}
    </div>
    {!listView && <aside className="tracking-callout"><div className="callout-icon"><Route size={26} aria-hidden="true" /></div><div><h2>Cerca de cada entrega, de principio a fin.</h2>
      <p>Un enlace sencillo para que quien espera sepa cómo va su pedido.</p></div><Link to="/track/demo" className="callout-link">Ver seguimiento de ejemplo <ArrowUpRight size={17} aria-hidden="true" /></Link></aside>}
    {newDelivery && <NewDelivery onClose={() => setNewDelivery(false)} />}
    {selected && <Modal title={`Entrega ${selected.id}`} open onClose={() => setSelected(null)}><div className="detail-status"><StatusBadge status={selected.status} /><span>{money(selected.fee)}</span></div>
      <dl className="detail-fields"><div><dt>Recogida</dt><dd>{selected.pickupAddress}</dd></div><div><dt>Destino</dt><dd>{selected.dropoffAddress}</dd></div><div><dt>Zona</dt><dd>{selected.zone}</dd></div>
        <div><dt>Repartidor</dt><dd>{selected.courier || 'Aún por asignar'}</dd></div></dl>
      {['CANCELLED', 'FAILED'].includes(selected.status) ? <p className="inline-note">Esta solicitud de ejemplo ya no está activa.</p> : <DeliveryTimeline status={selected.status} />}
      <div className="modal-actions"><Button variant="secondary" onClick={() => setSelected(null)}>Cerrar</Button></div></Modal>}
  </>;
}
