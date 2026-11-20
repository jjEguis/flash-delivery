export type Session = { token: string; actor: { actorId: string; role: string } };
export type Point = { latitude: number; longitude: number; accuracyMeters?: number; recordedAt: string; source: 'SIMULATED' | 'BROWSER_GPS'; sequence?: number; speedMps?: number; headingDegrees?: number };
export type Latest = { orderId: string; status: string; updatedAt: string; location: Point | null; freshness: 'FRESH' | 'STALE' | 'UNAVAILABLE' };
export const active = (status: string) => ['ASSIGNED', 'PICKED_UP'].includes(status);
export function readSession(): Session | null {
  try { const session = JSON.parse(localStorage.getItem('fd.session') || 'null'); return session?.token && session?.actor ? session : null; } catch { return null; }
}
export class GeoError extends Error {
  constructor(message: string, public status: number) { super(message); }
}
export async function geoApi<T>(path: string, session: Session | null, method = 'GET', body?: unknown, signal?: AbortSignal, idempotencyKey?:string): Promise<T> {
  const response = await fetch('/api/v1' + path, { method, signal, cache: 'no-store', referrerPolicy: 'no-referrer',
    headers: { 'Content-Type': 'application/json', ...(idempotencyKey ? {'Idempotency-Key':idempotencyKey} : {}), ...(session ? { Authorization: 'Bearer ' + session.token } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body) });
  if (response.status === 204) return undefined as T;
  const data = await response.json();
  if (!response.ok) throw new GeoError(data.error?.message || 'No se pudo consultar la ubicación', response.status);
  return data;
}
export type Position = {latitude:number;longitude:number};
export type Route = {
  geometry:{type:'LineString';coordinates:[number,number][]}; distanceMeters:number; durationSeconds:number;
  remainingMeters:number;etaSeconds:number|null;progressMeters:number;segmentIndex:number;segmentFraction:number;
  phase:string;routeVersion:string;calculatedAt:string;stale:boolean;offRoute:boolean;
  steps?:{distanceMeters:number;durationSeconds:number;type:string;modifier:string;location:[number,number]}[];
};
export type RouteResult = {orderId:string;status:string;route:Route|null;points:{pickup:Position;dropoff:Position}|null};
