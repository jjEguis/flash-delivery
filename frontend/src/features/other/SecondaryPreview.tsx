import { Link } from 'react-router-dom';
import { ArrowRight, CheckCheck, LockKeyhole, ShieldCheck } from 'lucide-react';
import { useDemo } from '../../app/DemoProvider';
import { Button, DeliveryTimeline, ScenarioContent, StatusBadge } from '../../components/ui';

export function TrackingPreview() {
  const { orders } = useDemo();
  const order = orders.find(item => item.id === 'FD-2047')!;
  return <div className="public-tracking"><div className="tracking-store"><span className="store-monogram">CM</span><span>Una entrega de<strong>Café del Mar</strong></span></div>
    <section className="panel tracking-panel"><div className="tracking-symbol"><CheckCheck size={30} aria-hidden="true" /></div>
      <p className="quiet-label">Referencia de ejemplo FD-2047</p><h1>{order.status === 'DELIVERED' ? 'Tu entrega llegó.' : 'Tu entrega va avanzando.'}</h1>
      <p className="tracking-intro">Cada paso, con claridad. Aquí puedes consultar cómo va tu pedido.</p><StatusBadge status={order.status} />
      <ScenarioContent><DeliveryTimeline status={order.status} /></ScenarioContent>
      <p className="tracking-privacy"><LockKeyhole size={15} aria-hidden="true" />Este ejemplo solo muestra estado e hitos. No revela direcciones ni datos personales.</p>
    </section><p className="tracking-demo-note">Esta página es una vista de diseño con datos simulados; no consulta un token real.</p></div>;
}

export function AdminPreview() {
  return <><section className="page-heading"><div><p className="page-context">Administración <span /> Vista de estructura</p><h1>Un espacio para cuidar la operación.</h1><p>Habilitación de perfiles y excepciones, separadas del despacho diario.</p></div></section>
    <section className="panel admin-placeholder"><span className="feedback-icon"><ShieldCheck size={30} aria-hidden="true" /></span><h2>Lo esencial, en su lugar.</h2><p>Esta primera entrega permite revisar el marco visual y la apariencia. Las pantallas administrativas se abordarán en FE-05.</p>
      <div className="admin-demo-actions"><Button variant="secondary" disabled aria-describedby="admin-future">Habilitar perfiles</Button><Button variant="secondary" disabled aria-describedby="admin-future">Gestionar incidencias</Button></div>
      <p id="admin-future" className="quiet-label">Acciones no disponibles en este prototipo. No se modifican perfiles ni entregas reales.</p></section></>;
}

export function NotFoundPreview() {
  return <section className="panel feedback"><h1>No encontramos esta vista.</h1><p>Puedes volver al inicio de la demostración.</p><Link className="text-link" to="/app/store">Volver al inicio <ArrowRight size={16} aria-hidden="true" /></Link></section>;
}
