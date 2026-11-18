import { useState } from 'react';
import type { Position } from './api';
import { LocationMap } from './LocationMap';
export function OrderPoints({onChange}:{onChange:(points:{pickupLocation:Position;dropoffLocation:Position}|null)=>void}) {
  const [pickup,setPickup]=useState<Position|null>(null), [dropoff,setDropoff]=useState<Position|null>(null);
  const [target,setTarget]=useState('pickup');
  function update(p:Position) {
    const nextPickup=target==='pickup'?p:pickup, nextDropoff=target==='dropoff'?p:dropoff;
    setPickup(nextPickup);setDropoff(nextDropoff);
    if (target==='pickup') setTarget('dropoff');
    onChange(nextPickup && nextDropoff ? {pickupLocation:nextPickup,dropoffLocation:nextDropoff} : null);
  }
  return <div className="geo-order-points"><details><summary>Seleccionar puntos en el mapa (opcional)</summary><p>Las direcciones no se convierten automáticamente en coordenadas. Selecciona ambos puntos en Santa Marta para habilitar rutas.</p>
    <label>Punto a seleccionar<select value={target} onChange={e=>setTarget(e.target.value)}><option value="pickup">Recogida</option><option value="dropoff">Entrega</option></select></label>
    <LocationMap point={null} points={pickup && dropoff ? {pickup,dropoff} : null} selection={pickup && !dropoff ? pickup : null} onPick={update}/>
    <p aria-live="polite">{pickup?`Recogida: ${pickup.latitude.toFixed(5)}, ${pickup.longitude.toFixed(5)}`:'Recogida sin seleccionar'}<br/>{dropoff?`Entrega: ${dropoff.latitude.toFixed(5)}, ${dropoff.longitude.toFixed(5)}`:'Entrega sin seleccionar'}</p>
    <button type="button" className="button button-secondary" onClick={()=>{const p={latitude:11.237,longitude:-74.201},d={latitude:11.235,longitude:-74.19};setPickup(p);setDropoff(d);onChange({pickupLocation:p,dropoffLocation:d});}}>Usar puntos de demo de Santa Marta</button>
    <button type="button" className="button button-secondary" onClick={()=>{setPickup(null);setDropoff(null);onChange(null);}}>Quitar puntos</button>
  </details></div>;
}
