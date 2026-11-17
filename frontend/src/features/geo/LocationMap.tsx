import { useEffect, useRef, useState } from 'react';
import { Map as MapLibre, Marker, NavigationControl, LngLatBounds, setWorkerUrl } from 'maplibre-gl';
import type { GeoJSONSource, StyleSpecification } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
setWorkerUrl(workerUrl);
import type { Point, Position, Route } from './api';
import { along } from './geometry';
import { useTheme } from '../../app/ThemeProvider';
import { MapPin } from 'lucide-react';

export function LocationMap({ point, route=null, points=null, onPick, selection=null }: {
  point:Point|null;route?:Route|null;points?:{pickup:Position;dropoff:Position}|null;
  onPick?:(point:Position)=>void;selection?:Position|null;
}) {
  const node=useRef<HTMLDivElement>(null), instance=useRef<MapLibre|null>(null);
  const markers=useRef<Marker[]>([]), courier=useRef<Marker|null>(null);
  const previous=useRef<{position:[number,number];progress:number;version?:string}|null>(null);
  const frame=useRef(0), follow=useRef(true);
  const pick=useRef(onPick); pick.current=onPick;
  const [mapError,setMapError]=useState(false), [ready,setReady]=useState(false), [following,setFollowing]=useState(true);
  const {theme}=useTheme();
  const visible=!!(point || points || onPick);
  useEffect(()=>{
    if (!visible || !node.current) return;
    let map:MapLibre;
    try {
      const style:StyleSpecification={version:8,sources:{osm:{type:'raster',tiles:[import.meta.env.VITE_MAP_TILE_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'],tileSize:256,maxzoom:19,
        attribution:import.meta.env.VITE_MAP_ATTRIBUTION || '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}},layers:[{id:'base',type:'raster',source:'osm'}]};
      map=new MapLibre({container:node.current,style:import.meta.env.VITE_MAP_STYLE_URL || style,center:[-74.207,11.241],zoom:13,attributionControl:{compact:false}});
      instance.current=map;
      map.addControl(new NavigationControl({showCompass:false}),'top-right');
      map.on('load',()=>{
        map.addSource('delivery-route',{type:'geojson',data:{type:'FeatureCollection',features:[]}});
        for (const [id,color] of [['travelled','#788e8a'],['pending','#087d62']]) map.addLayer({id,type:'line',source:'delivery-route',filter:['==',['get','phase'],id],layout:{'line-cap':'round','line-join':'round'},paint:{'line-color':color,'line-width':id==='pending'?6:4,'line-opacity':.9}});
        setReady(true);
      });
      map.on('error',()=>setMapError(true));
      map.on('dragstart',()=>{follow.current=false;setFollowing(false);});
      map.on('click',event=>pick.current?.({latitude:event.lngLat.lat,longitude:event.lngLat.lng}));
    } catch {setMapError(true);return;}
    const resize=new ResizeObserver(()=>map.resize());resize.observe(node.current);
    return ()=>{resize.disconnect();cancelAnimationFrame(frame.current);map.remove();instance.current=null;courier.current=null;markers.current=[];setReady(false);previous.current=null;};
  },[visible]);
  useEffect(()=>{
    const map=instance.current;
    if (!ready || !map) return;
    if (map.getLayer('base')) map.setPaintProperty('base','raster-brightness-max',theme==='dark'?.6:1);
    if (map.getLayer('pending')) map.setPaintProperty('pending','line-color',theme==='dark'?'#39d6ab':'#087d62');
  },[ready,theme]);
  useEffect(()=>{
    const map=instance.current;
    if (!ready || !map) return;
    markers.current.forEach(m=>m.remove());markers.current=[];
    for (const [label,p,color] of [['Recogida',points?.pickup,'#2a5fa5'],['Entrega',points?.dropoff,'#aa3947'],['Inicio de demo seleccionado',selection,'#72519b']] as const) {
      if (!p) continue;
      const element=document.createElement('span'); element.className='geo-pin';element.style.background=color;element.textContent=label==='Recogida'?'R':label==='Entrega'?'E':'D';element.setAttribute('aria-label',label);
      markers.current.push(new Marker({element}).setLngLat([p.longitude,p.latitude]).addTo(map));
    }
    const geometry=route?.geometry.coordinates;
    const split=geometry && route ? along(geometry,route.progressMeters) : null;
    const features=geometry && split ? [
      {type:'Feature' as const,properties:{phase:'travelled'},geometry:{type:'LineString' as const,coordinates:[...geometry.slice(0,split.index+1),split.coordinate]}},
      {type:'Feature' as const,properties:{phase:'pending'},geometry:{type:'LineString' as const,coordinates:[split.coordinate,...geometry.slice(split.index+1)]}},
    ] : [];
    (map.getSource('delivery-route') as GeoJSONSource)?.setData({type:'FeatureCollection',features});
  },[ready,points,selection,route]);
  useEffect(()=>{
    const map=instance.current;
    if (!ready || !map) return;
    cancelAnimationFrame(frame.current);
    if (!point) {courier.current?.remove();courier.current=null;previous.current=null;return;}
    const target:[number,number]=[point.longitude,point.latitude];
    if (!courier.current) {
      const element=document.createElement('span');element.className='geo-courier';element.textContent='▲';element.setAttribute('aria-label','Última posición del repartidor');
      courier.current=new Marker({element,rotationAlignment:'map'}).setLngLat(target).addTo(map);
    }
    const from=previous.current;
    const start=performance.now(), duration=window.matchMedia('(prefers-reduced-motion: reduce)').matches?0:1000;
    const animate=(now:number)=>{
      const fraction=duration?Math.min(1,(now-start)/duration):1;
      // Interpolar sobre la geometría vial cuando las muestras pertenecen a la misma ruta.
      const position=from && route && from.version===route.routeVersion && !route.offRoute ? along(route.geometry.coordinates,from.progress+(route.progressMeters-from.progress)*fraction).coordinate : target;
      courier.current?.setLngLat(position).setRotation(point.headingDegrees || 0);
      if (follow.current) map.jumpTo({center:position});
      if (fraction<1) frame.current=requestAnimationFrame(animate);
    };
    frame.current=requestAnimationFrame(animate);
    previous.current={position:target,progress:route?.progressMeters || 0,version:route?.routeVersion};
    return ()=>cancelAnimationFrame(frame.current);
  },[ready,point,route]);
  function fit() {
    const bounds=new LngLatBounds();
    for (const p of route?.geometry.coordinates || []) bounds.extend(p);
    for (const p of [points?.pickup,points?.dropoff,point,selection]) if (p) bounds.extend([p.longitude,p.latitude]);
    if (!bounds.isEmpty()) instance.current?.fitBounds(bounds,{padding:55,maxZoom:16,duration:0});
    follow.current=false;setFollowing(false);
  }
  return <div className="geo-map-section">
    {visible ? <><div className="geo-map" ref={node} role="region" aria-label="Mapa de la última ubicación" />
      <div className="geo-map-tools"><button type="button" className="button button-secondary" onClick={()=>{follow.current=!follow.current;setFollowing(follow.current);}} aria-pressed={following}>{following?'Centrado automático':'Seguir repartidor'}</button><button type="button" className="button button-secondary" onClick={fit}>Ver ruta completa</button></div>
      {!ready && !mapError && <p role="status">Cargando mapa…</p>}
      {onPick && <p>Selecciona un punto en el mapa o usa las coordenadas de los controles.</p>}
      {mapError && <p role="status">No se pudo cargar el fondo del mapa. La ubicación y los estados siguen disponibles.</p>}
    </> : <div className="geo-map-empty"><MapPin size={34} aria-hidden="true"/><strong>Aún no hay ubicación compartida</strong><p>El seguimiento por estados continúa disponible.</p></div>}
  </div>;
}
