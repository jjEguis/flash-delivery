import { useEffect, useRef, useState } from 'react';
import { circleMarker, map, tileLayer } from 'leaflet';
import type { Map as LeafletMap, CircleMarker } from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { Point } from './api';
import { useTheme } from '../../app/ThemeProvider';
import { MapPin } from 'lucide-react';

export function LocationMap({ point }: { point: Point | null }) {
  const node = useRef<HTMLDivElement>(null);
  const instance = useRef<LeafletMap | null>(null);
  const marker = useRef<CircleMarker | null>(null);
  const [tileError, setTileError] = useState(false);
  const { theme } = useTheme();
  const hasPoint = !!point;
  useEffect(() => {
    if (!point || !node.current) return;
    if (!instance.current) {
      instance.current = map(node.current, { scrollWheelZoom: false }).setView([point.latitude, point.longitude], 15);
      marker.current = circleMarker([point.latitude, point.longitude], { radius: 12, weight: 4, fillOpacity: 1 }).addTo(instance.current);
      instance.current.attributionControl.setPrefix(false);
    }
    const color = getComputedStyle(document.documentElement).getPropertyValue('--brand').trim();
    marker.current?.setLatLng([point.latitude, point.longitude]).setStyle({ color, fillColor: color });
    instance.current.panTo([point.latitude, point.longitude], { animate: false });
  }, [point, theme]);
  useEffect(() => {
    if (!instance.current) return;
    const layer = tileLayer(import.meta.env.VITE_MAP_TILE_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      referrerPolicy: 'strict-origin-when-cross-origin',
    });
    layer.on('tileerror', () => setTileError(true)); layer.addTo(instance.current);
    return () => { layer.remove(); };
  }, [hasPoint]);
  useEffect(() => () => { instance.current?.remove(); instance.current = null; }, []);
  // Retira el mapa previo cuando la ubicación deja de estar disponible.
  useEffect(() => {
    if (!point) { instance.current?.remove(); instance.current = null; }
  }, [point]);
  return <div className="geo-map-section">
    {point ? <><div className="geo-map" ref={node} role="region" aria-label="Mapa de la última ubicación" />
      {tileError && <p role="status">No se pudo cargar el fondo del mapa. La ubicación y los estados siguen disponibles.</p>}
    </> : <div className="geo-map-empty"><MapPin size={34} aria-hidden="true" /><strong>Aún no hay ubicación compartida</strong><p>El seguimiento por estados continúa disponible.</p></div>}
  </div>;
}
