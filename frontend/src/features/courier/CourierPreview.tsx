import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ArrowRight, CheckCheck, ChevronRight, Clock3, MapPin, Package, Store, Truck } from 'lucide-react';
import { useDemo } from '../../app/DemoProvider';
import { money, offers } from '../../mocks/data';
import { Button, DeliveryTimeline, Modal, ScenarioContent, StatusBadge } from '../../components/ui';

export function CourierPreview() {
  const { active, setActive, available, setAvailable, notify, completed, setCompleted, orders, setOrders } = useDemo();
  const { pathname } = useLocation();
  const onlyOffers = pathname.endsWith('/available');
  const history = pathname.endsWith('/history');
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  function toggle() { setAvailable(!available); notify(available ? 'Disponibilidad de ejemplo desactivada.' : 'Disponibilidad de ejemplo activada.'); }
  async function finish() {
    setBusy(true);
    await new Promise(resolve => setTimeout(resolve, 250));
    if (active) {
      setCompleted([{ ...active, status: 'DELIVERED' }, ...completed]);
      setOrders(orders.map(order => order.id === active.id ? { ...order, status: 'DELIVERED' } : order));
    }
    setActive(null); setConfirm(false); setBusy(false);
    notify('Entrega finalizada en la demostración. No se modificó la operación real.');
  }
  return <>
    <section className="page-heading courier-heading"><div><p className="page-context">Andrés Pérez <span /> Zona Centro</p><h1>{onlyOffers ? 'Entregas disponibles' : history ? 'Tu historial' : 'Vamos con la próxima.'}</h1>
      <p>{onlyOffers ? 'Elige una entrega de ejemplo para ver cómo funciona.' : history ? 'Tus entregas finalizadas, en esta demostración.' : 'Tu jornada, una entrega a la vez.'}</p></div>
      <span className="courier-date"><Clock3 size={16} aria-hidden="true" />Jornada de ejemplo</span></section>
    <div className="courier-workspace">
      <div className="courier-main">
        {!onlyOffers && !history && <section className="active-delivery panel"><header className="panel-header"><div className="section-label"><span className="active-dot" /><h2>Tu entrega activa</h2></div>{active && <StatusBadge status={active.status} />}</header>
          <ScenarioContent>{active ? <><div className="active-title"><div><span className="quiet-label">Entrega de demostración</span><h3>{active.id}</h3></div><span className="active-fee">{money(active.fee)}<small>Tarifa de la entrega</small></span></div>
            <div className="route-stops"><div className="route-stop"><span className="stop-icon pickup"><Store size={19} aria-hidden="true" /></span><div><span>Recoger en Café del Mar</span><strong>{active.pickupAddress}</strong></div></div>
              <div className="route-stop"><span className="stop-icon dropoff"><MapPin size={19} aria-hidden="true" /></span><div><span>Entregar en</span><strong>{active.dropoffAddress}</strong></div></div></div>
            <div className="delivery-progress" aria-label="Progreso de la entrega"><span className="complete"><CheckCheck size={15} aria-hidden="true" />Asignada</span><i /><span className={active.status === 'PICKED_UP' ? 'complete' : ''}><Package size={15} aria-hidden="true" />Recogida</span><i /><span><MapPin size={15} aria-hidden="true" />Entregada</span></div>
            <Button className="active-action" onClick={() => { if (active.status === 'ASSIGNED') { setActive({ ...active, status: 'PICKED_UP' }); setOrders(orders.map(order => order.id === active.id ? { ...order, status: 'PICKED_UP' } : order)); notify('Recogida registrada en la demostración.'); } else setConfirm(true); }}>
              {active.status === 'ASSIGNED' ? <Package size={18} aria-hidden="true" /> : <CheckCheck size={18} aria-hidden="true" />}{active.status === 'ASSIGNED' ? 'Marcar como recogido' : 'Finalizar entrega'}</Button>
            <p className="action-hint">Solo confirma cuando hayas completado este paso.</p></> : <div className="feedback"><Package size={32} aria-hidden="true" /><h3>No tienes una entrega activa</h3><p>Explora las solicitudes para continuar tu jornada de ejemplo.</p><Link to="/app/courier/available" className="text-link">Explorar entregas <ArrowRight size={17} aria-hidden="true" /></Link></div>}</ScenarioContent>
        </section>}
        {history ? <section className="panel"><header className="panel-header"><h2>Entregas de ejemplo</h2></header><ScenarioContent>{completed.map(order => <div className="history-entry" key={order.id}><span className="history-check"><CheckCheck size={21} aria-hidden="true" /></span><div><strong>{order.id}</strong><p>15 noviembre, {order.time}</p></div><div><StatusBadge status="DELIVERED" /><p className="align-right">{money(order.fee)}</p></div></div>)}</ScenarioContent></section>
          : <section className="panel offers-panel"><header className="panel-header"><div><h2>En tu zona</h2><p>Solicitudes de demostración</p></div>{!onlyOffers && <Link to="/app/courier/available" className="text-link">Ver todas <ChevronRight size={16} aria-hidden="true" /></Link>}</header>
            {active && <p className="inline-note">Termina tu entrega activa antes de aceptar otra.</p>}
            {!available && <p className="inline-note">Activa tu disponibilidad para aceptar una entrega de ejemplo.</p>}
            <ScenarioContent><div className="offers-grid">{offers.map(offer => <article className="offer-card" key={offer.id}><div className="offer-heading"><span className="offer-store"><Store size={15} aria-hidden="true" />Comercio de ejemplo</span><span>{offer.time}</span></div>
              <h3>{offer.id}</h3><p><MapPin size={15} aria-hidden="true" />{offer.dropoffAddress}</p><span className="quiet-label">Zona {offer.zone}</span><div className="offer-footer"><strong>{money(offer.fee)}</strong>
                <Button variant="secondary" disabled={!!active || !available} aria-label={`Aceptar entrega ${offer.id}`} onClick={() => { setActive({ ...offer, status: 'ASSIGNED', courier: 'Andrés Pérez' }); notify('Entrega asignada en la demostración.'); }}>Aceptar entrega <ArrowRight size={15} aria-hidden="true" /></Button></div></article>)}</div></ScenarioContent>
          </section>}
      </div>
      <aside className="courier-aside"><section className="panel availability-card"><div className="availability-icon"><Truck size={24} aria-hidden="true" /></div><h2>Tú marcas el ritmo</h2><p>Activa tu disponibilidad cuando estés listo para una nueva entrega.</p>
        <label className="availability-control"><span><strong>{available ? 'Disponible' : 'No disponible'}</strong><small>Estado de demostración</small></span><input type="checkbox" role="switch" checked={available} onChange={toggle} aria-label="Disponibilidad de demostración" /></label>
        <p className="zone-caption"><MapPin size={14} aria-hidden="true" />Zona Centro</p></section>
        <section className="courier-summary"><h2>Un buen comienzo.</h2><p>Tus entregas completadas en esta jornada de ejemplo.</p><span><CheckCheck size={17} aria-hidden="true" /><strong>{completed.length} {completed.length === 1 ? 'entrega' : 'entregas'}</strong><i />{money(completed.reduce((sum, order) => sum + order.fee, 0))}</span></section></aside>
    </div>
    {confirm && <Modal title="¿Finalizar esta entrega de ejemplo?" open onClose={() => setConfirm(false)}><p className="modal-description">Confirma que el pedido llegó a su destino. Esta acción solo cambia la demostración.</p>
      {active && <DeliveryTimeline status={active.status} />}<div className="modal-actions"><Button variant="secondary" disabled={busy} onClick={() => setConfirm(false)}>Volver</Button><Button disabled={busy} onClick={finish}>{busy ? 'Finalizando…' : 'Confirmar entrega finalizada'}</Button></div></Modal>}
  </>;
}
