export type Session = { token: string; actor: { actorId: string; role: string } };
export type Point = { latitude: number; longitude: number; accuracyMeters?: number; recordedAt: string; source: 'SIMULATED' | 'BROWSER_GPS' };
export type Latest = { orderId: string; status: string; updatedAt: string; location: Point | null; freshness: 'FRESH' | 'STALE' | 'UNAVAILABLE' };
export const active = (status: string) => ['ASSIGNED', 'PICKED_UP'].includes(status);
export function readSession(): Session | null {
  try { const session = JSON.parse(localStorage.getItem('fd.session') || 'null'); return session?.token && session?.actor ? session : null; } catch { return null; }
}
export class GeoError extends Error {
  constructor(message: string, public status: number) { super(message); }
}
export async function geoApi<T>(path: string, session: Session | null, method = 'GET', body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch('/api/v1' + path, { method, signal, cache: 'no-store', referrerPolicy: 'no-referrer',
    headers: { 'Content-Type': 'application/json', ...(session ? { Authorization: 'Bearer ' + session.token } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body) });
  if (response.status === 204) return undefined as T;
  const data = await response.json();
  if (!response.ok) throw new GeoError(data.error?.message || 'No se pudo consultar la ubicación', response.status);
  return data;
}
// Recorrido ficticio; no es una ruta calculada por calles ni parte de una dirección real.
export const DEMO_ROUTE = [
  [11.2408, -74.1990], [11.2410, -74.1986], [11.2413, -74.1982], [11.2417, -74.1979],
  [11.2421, -74.1975], [11.2424, -74.1970], [11.2428, -74.1966], [11.2432, -74.1962],
] as const;
