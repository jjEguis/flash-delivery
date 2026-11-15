// Cliente HTTP de la SPA. Solo persiste huellas y claves de intenciones pendientes.
export const PENDING_KEY = "fd.pendingRequests.v1";

function readPending(storage) {
  try {
    const value = JSON.parse(storage?.getItem(PENDING_KEY) || "{}");
    return new Map(Object.entries(value).filter(([hash, key]) =>
      /^[a-f0-9]{64}$/.test(hash) && typeof key === "string" && /^[A-Za-z0-9_-]{1,128}$/.test(key)));
  } catch { return new Map(); }
}

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])]));
  }
  return value;
}

function invalidResponse() {
  return Object.assign(new Error("No pudimos confirmar la respuesta. Reintenta la misma acción."), { code: "INVALID_RESPONSE" });
}

export function createApiClient({ getSession, storage, onUnauthorized = () => {},
  fetchImpl = (...args) => fetch(...args), cryptoImpl = globalThis.crypto } = {}) {
  const pending = readPending(storage);
  function persist() {
    try { storage?.setItem(PENDING_KEY, JSON.stringify(Object.fromEntries(pending))); } catch { /* respaldo en memoria */ }
  }
  async function fingerprint(method, path, body, intent, actor) {
    const input = JSON.stringify(canonical([actor?.role, actor?.actorId, method, path, body ?? null, intent]));
    const bytes = await cryptoImpl.subtle.digest("SHA-256", new TextEncoder().encode(input));
    return Array.from(new Uint8Array(bytes), byte => byte.toString(16).padStart(2, "0")).join("");
  }
  return async function api(method, path, { body, intent, validate } = {}) {
    const session = getSession?.();
    const headers = { "Content-Type": "application/json" };
    if (session?.token) headers.Authorization = "Bearer " + session.token;
    const hash = intent ? await fingerprint(method, path, body, intent, session?.actor) : null;
    if (hash) {
      if (!pending.has(hash)) { pending.set(hash, cryptoImpl.randomUUID()); persist(); }
      headers["Idempotency-Key"] = pending.get(hash);
    }
    function confirmed() {
      if (hash) { pending.delete(hash); persist(); }
    }
    let response;
    try {
      response = await fetchImpl("/api/v1" + path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
    } catch {
      throw Object.assign(new Error("No hay conexión con la API. Puedes reintentar."), { code: "NETWORK" });
    }
    if (response.status === 204) { confirmed(); return null; }
    let data;
    try { data = await response.json(); } catch { throw invalidResponse(); }
    if (!data || typeof data !== "object" || Array.isArray(data)) throw invalidResponse();
    if (response.ok) {
      if (validate && !validate(data)) throw invalidResponse();
      confirmed();
      return data;
    }
    const error = data.error;
    if (!error || typeof error.code !== "string") throw invalidResponse();
    // Reautenticar o recuperar permisos no demuestra que un intento previo no se confirmó.
    if (response.status < 500 && ![401, 403, 408, 429].includes(response.status) && error.code !== "CONCURRENT_UPDATE") confirmed();
    // Una respuesta tardía de otra sesión no debe cerrar la sesión vigente.
    if (response.status === 401 && session?.token && session.token === getSession?.()?.token && !path.startsWith("/tracking")) onUnauthorized();
    throw Object.assign(new Error(error.message || "Error " + response.status), { status: response.status, code: error.code });
  };
}

export function validPage(data) {
  return Array.isArray(data.items) && data.items.every(item => item && typeof item.orderId === "string") &&
    (data.nextCursor === null || typeof data.nextCursor === "string");
}

export function validCreatedOrder(data) {
  return typeof data.orderId === "string" && !!data.orderId && typeof data.trackingToken === "string" && !!data.trackingToken;
}
