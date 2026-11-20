import { useEffect, useId, useRef, useState } from 'react';
import type { Position } from './api';
import { LocationMap } from './LocationMap';

type Fields = {pickupLatitude:string;pickupLongitude:string;dropoffLatitude:string;dropoffLongitude:string};
const empty:Fields = {pickupLatitude:'',pickupLongitude:'',dropoffLatitude:'',dropoffLongitude:''};
export function OrderPoints({onChange}:{onChange:(points:{pickupLocation:Position;dropoffLocation:Position}|null,problem:string)=>void}) {
  const [fields,setFields]=useState<Fields>(empty);
  const [target,setTarget]=useState<'pickup'|'dropoff'>('pickup');
  const id=useId();
  const root=useRef<HTMLDivElement>(null);
  useEffect(()=>{
    root.current?.querySelectorAll<HTMLInputElement>('input').forEach(input=>input.setAttribute('aria-invalid',String(input.matches(':user-invalid'))));
  },[fields]);
  function position(kind:'pickup'|'dropoff',values=fields):Position|null {
    const latitude=values[`${kind}Latitude`],longitude=values[`${kind}Longitude`];
    const lat=Number(latitude),lon=Number(longitude);
    return latitude!=='' && longitude!=='' && lat>=11.12 && lat<=11.36 && lon>=-74.28 && lon<=-74.05 ? {latitude:lat,longitude:lon} : null;
  }
  const pickup=position('pickup'),dropoff=position('dropoff');
  const complete=Object.values(fields).every(value=>value!=='');
  function update(next:Fields) {
    setFields(next);
    const p=position('pickup',next),d=position('dropoff',next);
    const any=Object.values(next).some(value=>value!=='');
    const valid=p && d && [p,d].every(point=>Number.isFinite(point.latitude) && Number.isFinite(point.longitude) && point.latitude>=11.12 && point.latitude<=11.36 && point.longitude>=-74.28 && point.longitude<=-74.05);
    onChange(valid?{pickupLocation:p,dropoffLocation:d}:null,any && !valid?'Completa las coordenadas de recogida y entrega dentro de Santa Marta, o pulsa «Quitar puntos» para continuar por estados.':'');
  }
  function pick(point:Position) {
    update({...fields,[`${target}Latitude`]:point.latitude.toFixed(6),[`${target}Longitude`]:point.longitude.toFixed(6)});
    if (target==='pickup') setTarget('dropoff');
  }
  return <div className="geo-order-points" ref={root}><p className="muted">{complete?'Recogida y entrega seleccionadas para el recorrido.':'Para probar el recorrido, selecciona ambos puntos. Sin puntos el pedido se sigue por estados.'}</p>
    <details><summary>Seleccionar puntos en el mapa (opcional)</summary><p>Las direcciones no se convierten automáticamente en coordenadas. Usa el mapa, las coordenadas o los puntos de demo.</p>
      <label htmlFor={id}>Punto a seleccionar</label><select name="pointTarget" id={id} value={target} onChange={e=>setTarget(e.target.value as 'pickup'|'dropoff')}><option value="pickup">Recogida</option><option value="dropoff">Entrega</option></select>
      <LocationMap point={null} points={pickup || dropoff ? {pickup:pickup || undefined,dropoff:dropoff || undefined} : null} onPick={pick}/>
      <fieldset className="geo-coordinate-fields"><legend>Coordenadas de la entrega</legend>{(['pickup','dropoff'] as const).map(kind=><div key={kind}><strong>{kind==='pickup'?'Recogida':'Entrega'}</strong>{(['Latitude','Longitude'] as const).map(axis=><label key={axis} htmlFor={`${id}-${kind}-${axis}`}>{axis==='Latitude'?'Latitud':'Longitud'} de {kind==='pickup'?'recogida':'entrega'}<input id={`${id}-${kind}-${axis}`} name={`${kind}${axis}`} type="number" step="any" min={axis==='Latitude'?11.12:-74.28} max={axis==='Latitude'?11.36:-74.05} aria-invalid="false" onBlur={e=>e.currentTarget.setAttribute('aria-invalid',String(e.currentTarget.matches(':user-invalid')))} onInvalid={e=>e.currentTarget.setAttribute('aria-invalid','true')} value={fields[`${kind}${axis}`]} onChange={e=>{e.currentTarget.setAttribute('aria-invalid',String(e.currentTarget.matches(':user-invalid')));update({...fields,[`${kind}${axis}`]:e.target.value});}}/></label>)}</div>)}</fieldset>
      <p aria-live="polite">{pickup?`Recogida: ${pickup.latitude.toFixed(5)}, ${pickup.longitude.toFixed(5)}`:'Recogida sin seleccionar'}<br/>{dropoff?`Entrega: ${dropoff.latitude.toFixed(5)}, ${dropoff.longitude.toFixed(5)}`:'Entrega sin seleccionar'}</p>
      <button type="button" className="button button-secondary" onClick={()=>update({pickupLatitude:'11.237',pickupLongitude:'-74.201',dropoffLatitude:'11.235',dropoffLongitude:'-74.19'})}>Usar puntos de demo de Santa Marta</button>
      <button type="button" className="button button-secondary" onClick={()=>{update(empty);setTarget('pickup');}}>Quitar puntos</button>
    </details></div>;
}
