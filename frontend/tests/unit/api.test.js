import test from "node:test";
import assert from "node:assert/strict";
import { webcrypto } from "node:crypto";
import { createApiClient, PENDING_KEY, validCreatedOrder } from "../../api.js";

function fixture() {
  const saved = new Map(), calls = [], responses = [];
  const storage = { getItem: key => saved.get(key) ?? null, setItem: (key, value) => saved.set(key, value) };
  let session = { token: "token-alice", actor: { role: "STORE", actorId: "alice" } }, logouts = 0;
  const options = { storage, cryptoImpl: webcrypto, getSession: () => session, onUnauthorized: () => { logouts++; },
    fetchImpl: async (url, request) => {
      calls.push({ url, ...request });
      const next = responses.shift();
      if (next instanceof Error) throw next;
      if (typeof next === "function") return next();
      const { status = 200, data = { orderId: "o1" }, broken = false } = next || {};
      return { status, ok: status >= 200 && status < 300, json: async () => {
        if (broken) throw new SyntaxError("truncated JSON");
        return data;
      } };
    } };
  return { calls, responses, saved, storage, options, client: createApiClient(options),
    login: (value) => { session = value; }, logouts: () => logouts };
}
const mutation = { body: { pickupAddress: "Private address", feeMinor: 8000 }, intent: "create" };
const requestKey = call => call.headers["Idempotency-Key"];

test("201 con JSON perdido conserva la clave y no confirma un resultado vacío", async () => {
  const f = fixture();
  f.responses.push({ status: 201, broken: true }, { status: 201, data: { orderId: "o1" } });
  await assert.rejects(f.client("POST", "/orders", mutation), { code: "INVALID_RESPONSE" });
  assert.deepEqual(await f.client("POST", "/orders", mutation), { orderId: "o1" });
  assert.equal(requestKey(f.calls[0]), requestKey(f.calls[1]));
  assert.deepEqual(JSON.parse(f.saved.get(PENDING_KEY)), {});
  await f.client("POST", "/orders", mutation);
  assert.notEqual(requestKey(f.calls[1]), requestKey(f.calls[2]));
});

for (const data of [null, [], "wrong", {}]) {
  test(`respuesta de creación incompleta ${JSON.stringify(data)} permite reintentar la misma intención`, async () => {
    const f = fixture();
    const options = { ...mutation, validate: validCreatedOrder };
    f.responses.push({ status: 201, data }, { status: 201, data: { orderId: "o1", trackingToken: "o1.secret" } });
    await assert.rejects(f.client("POST", "/orders", options), { code: "INVALID_RESPONSE" });
    await f.client("POST", "/orders", options);
    assert.equal(requestKey(f.calls[0]), requestKey(f.calls[1]));
  });
}

for (const status of [408, 429, 500, 503]) {
  test(`HTTP ${status} mantiene clave hasta una confirmación`, async () => {
    const f = fixture();
    f.responses.push({ status, data: { error: { code: "TEMPORARY", message: "retry" } } }, {});
    await assert.rejects(f.client("POST", "/orders", mutation), { status });
    await f.client("POST", "/orders", mutation);
    assert.equal(requestKey(f.calls[0]), requestKey(f.calls[1]));
  });
}

test("CONCURRENT_UPDATE conserva clave; un conflicto definitivo la libera", async () => {
  const f = fixture();
  f.responses.push({ status: 409, data: { error: { code: "CONCURRENT_UPDATE" } } },
    { status: 409, data: { error: { code: "IDEMPOTENCY_CONFLICT" } } }, {});
  await assert.rejects(f.client("POST", "/orders", mutation), { code: "CONCURRENT_UPDATE" });
  await assert.rejects(f.client("POST", "/orders", mutation), { code: "IDEMPOTENCY_CONFLICT" });
  await f.client("POST", "/orders", mutation);
  assert.equal(requestKey(f.calls[0]), requestKey(f.calls[1]));
  assert.notEqual(requestKey(f.calls[1]), requestKey(f.calls[2]));
});

test("fallo de red y recarga recuperan clave sin guardar cuerpo ni token", async () => {
  const f = fixture();
  f.responses.push(new Error("offline"));
  await assert.rejects(f.client("POST", "/orders", mutation), { code: "NETWORK" });
  const stored = f.saved.get(PENDING_KEY);
  assert.ok(!stored.includes("Private address") && !stored.includes("token-alice") && !stored.includes("create"));
  await createApiClient(f.options)("POST", "/orders", mutation);
  assert.equal(requestKey(f.calls[0]), requestKey(f.calls[1]));
});

test("claves separadas por actor, rol, cuerpo y operación; JSON con otro orden conserva intención", async () => {
  const f = fixture();
  f.responses.push(...Array.from({ length: 6 }, () => new Error("offline")));
  const call = (method = "POST", path = "/orders", options = mutation) =>
    assert.rejects(f.client(method, path, options), { code: "NETWORK" });
  await call();
  await call("POST", "/orders", { ...mutation, body: { feeMinor: 8000, pickupAddress: "Private address" } });
  assert.equal(requestKey(f.calls[0]), requestKey(f.calls[1]));
  f.login({ token: "token-bob", actor: { role: "STORE", actorId: "bob" } });
  await call();
  f.login({ token: "courier-bob", actor: { role: "COURIER", actorId: "bob" } });
  await call();
  await call("POST", "/orders", { ...mutation, body: { feeMinor: 9000 } });
  await call("PATCH", "/other");
  assert.equal(new Set(f.calls.map(requestKey)).size, 5);
});

test("204 confirma sin exigir JSON y un 400 definitivo permite corregir la intención", async () => {
  const f = fixture();
  f.responses.push({ status: 400, data: { error: { code: "INVALID_INPUT" } } }, { status: 204 });
  await assert.rejects(f.client("POST", "/orders", mutation), { code: "INVALID_INPUT" });
  assert.equal(await f.client("POST", "/orders", mutation), null);
  assert.notEqual(requestKey(f.calls[0]), requestKey(f.calls[1]));
});

test("almacenamiento bloqueado conserva el respaldo en memoria", async () => {
  const f = fixture();
  const storage = { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); } };
  const client = createApiClient({ ...f.options, storage });
  f.responses.push(new Error("offline"), {});
  await assert.rejects(client("POST", "/orders", mutation));
  await client("POST", "/orders", mutation);
  assert.equal(requestKey(f.calls[0]), requestKey(f.calls[1]));
});

test("401 tardío no cierra una sesión diferente", async () => {
  const f = fixture();
  f.responses.push(async () => {
    f.login({ token: "token-bob", actor: { role: "STORE", actorId: "bob" } });
    return { status: 401, ok: false, json: async () => ({ error: { code: "UNAUTHORIZED" } }) };
  });
  await assert.rejects(f.client("GET", "/stores/me"), { status: 401 });
  assert.equal(f.logouts(), 0);
  f.responses.push({ status: 401, data: { error: { code: "UNAUTHORIZED" } } });
  await assert.rejects(f.client("GET", "/stores/me"));
  assert.equal(f.logouts(), 1);
});

test("un login rechazado sin sesión no dispara el cierre de sesión", async () => {
  const f = fixture(); f.login(null);
  f.responses.push({ status: 401, data: { error: { code: "UNAUTHORIZED" } } });
  await assert.rejects(f.client("POST", "/auth/dev-login", { body: { userId: "admin" } }));
  assert.equal(f.logouts(), 0);
});

test("reautenticar o recuperar permisos no descarta una intención con resultado incierto", async () => {
  for (const status of [401, 403]) {
    const f = fixture();
    f.responses.push({ status: 201, broken: true }, { status, data: { error: { code: "ACCESS_DENIED" } } }, {});
    await assert.rejects(f.client("POST", "/orders", mutation), { code: "INVALID_RESPONSE" });
    await assert.rejects(f.client("POST", "/orders", mutation), { status });
    f.login({ token: "renewed-alice-token", actor: { role: "STORE", actorId: "alice" } });
    await createApiClient(f.options)("POST", "/orders", mutation);
    assert.equal(new Set(f.calls.map(requestKey)).size, 1);
  }
});
