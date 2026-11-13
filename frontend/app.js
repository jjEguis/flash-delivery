// FlashDelivery — SPA sin dependencias. Habla con /api/v1 a través del proxy local.
const $ = (sel, el = document) => el.querySelector(sel);
const app = $("#app");
const SESSION_KEY = "fd.session";
const TOKENS_KEY = "fd.trackingTokens";
const STATUS = {
  PENDING: "Pendiente", ASSIGNED: "Asignado", PICKED_UP: "Recogido",
  DELIVERED: "Entregado", CANCELLED: "Cancelado", FAILED: "Fallido",
};
const EVENT_LABEL = {
  CREATED: "Pedido creado", ASSIGNED: "Repartidor asignado", PICKED_UP: "Pedido recogido",
  DELIVERED: "Pedido entregado", CANCELLED: "Pedido cancelado", FAILED: "Entrega fallida",
};
const pending = new Map(); // intención → Idempotency-Key (se conserva si hay que reintentar)
let timers = [];
let zonesCache = null;

// ---------- utilidades ----------
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = (n) => "$" + Number(n || 0).toLocaleString("es-CO");
const when = (iso) => (iso ? new Date(iso).toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" }) : "—");
const badge = (s) => `<span class="badge s-${esc(s)}">${esc(STATUS[s] || s)}</span>`;
const short = (id) => esc(String(id || "").slice(-8));
const month = () => new Date().toISOString().slice(0, 7);
const load = (k, d) => { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } };
const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* sin almacenamiento */ } };
const newKey = () => (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random().toString(16).slice(2)).replace(/[^A-Za-z0-9_-]/g, "");
let session = load(SESSION_KEY, null);

function toast(message, bad = false) {
  const t = $("#toast");
  t.textContent = message;
  t.className = "toast" + (bad ? " bad" : "");
  t.hidden = false;
  clearTimeout(t._h);
  t._h = setTimeout(() => { t.hidden = true; }, 4200);
}

function every(ms, fn) { timers.push(setInterval(fn, ms)); }

async function api(method, path, { body, intent } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (session?.token) headers.Authorization = "Bearer " + session.token;
  if (intent) {
    if (!pending.has(intent)) pending.set(intent, newKey());
    headers["Idempotency-Key"] = pending.get(intent);
  }
  let res;
  try {
    res = await fetch("/api/v1" + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  } catch {
    throw Object.assign(new Error("No hay conexión con la API. Puedes reintentar."), { code: "NETWORK" });
  }
  const data = res.status === 204 ? null : await res.json().catch(() => null);
  if (res.ok) { if (intent) pending.delete(intent); return data; }
  if (intent && res.status < 500 && data?.error?.code !== "CONCURRENT_UPDATE") pending.delete(intent);
  if (res.status === 401 && session && !path.startsWith("/tracking")) { logout(true); }
  const err = data?.error || {};
  throw Object.assign(new Error(err.message || "Error " + res.status), { status: res.status, code: err.code });
}

async function zones() {
  if (!zonesCache) zonesCache = (await api("GET", "/zones")).items;
  return zonesCache;
}
const zoneName = (id) => (zonesCache || []).find((z) => z.zoneId === id)?.name || id;

function logout(expired) {
  session = null;
  save(SESSION_KEY, null);
  if (expired) toast("Tu sesión expiró; vuelve a iniciar sesión", true);
  location.hash = "#/";
  render();
}

function nav() {
  const el = $("#nav");
  if (!session) { el.innerHTML = `<a href="#/seguimiento">Seguir un pedido</a>`; return; }
  const role = { STORE: "Comercio", COURIER: "Repartidor", ADMIN: "Administración" }[session.actor.role];
  el.innerHTML = `<span class="who">${esc(role)} · ${esc(session.actor.actorId)}</span>
    <a href="#/seguimiento">Seguimiento</a><button type="button" data-act="logout">Salir</button>`;
}

function guard(fn) {
  return async (event) => {
    const button = event?.submitter || event?.currentTarget;
    if (button?.disabled) return;
    if (button && "disabled" in button) button.disabled = true;
    try { await fn(event); } catch (error) { toast(error.message, true); } finally {
      if (button && "disabled" in button) button.disabled = false;
    }
  };
}

// ---------- inicio ----------
function home() {
  app.innerHTML = `
    <section class="hero">
      <h1>Entregas de última milla, sin dobles asignaciones</h1>
      <p>Los comercios publican pedidos, los repartidores de la zona compiten por aceptarlos y solo uno gana.
        El destinatario sigue su pedido con un enlace seguro.</p>
      <div class="chips"><span class="chip">DynamoDB tabla única</span><span class="chip">Transacciones atómicas</span>
        <span class="chip">Presencia en Redis</span><span class="chip">Caché de estadísticas</span></div>
    </section>
    <div class="layout">
      <section class="card">
        <div class="card__head"><h2>¿Cómo quieres entrar?</h2></div>
        <div class="grid grid--roles" role="group" aria-label="Rol">
          ${[["STORE", "Comercio", "Publica pedidos y sigue tus entregas"],
             ["COURIER", "Repartidor", "Conéctate y acepta pedidos de tu zona"],
             ["ADMIN", "Administración", "Habilita comercios y repartidores"]]
            .map(([role, title, text], i) => `<button type="button" class="option" data-role="${role}" aria-pressed="${i === 0}">
              <b>${title}</b><span class="muted">${text}</span></button>`).join("")}
        </div>
        <form id="login">
          <label for="userId">Usuario</label>
          <input id="userId" name="userId" required maxlength="64" pattern="[A-Za-z0-9_\\-]+" autocomplete="username"
            placeholder="por ejemplo tienda_centro" value="${esc(load("fd.lastUser", ""))}">
          <div id="adminCode" hidden>
            <label for="code">Código de administrador</label>
            <input id="code" name="code" type="password" autocomplete="off" placeholder="DEV_ADMIN_CODE">
          </div>
          <button class="btn btn--block" type="submit">Entrar</button>
          <p class="muted" style="margin-top:10px">Acceso de desarrollo local: el servidor firma un token para el usuario y rol elegidos.</p>
        </form>
      </section>
      <aside class="card sticky">
        <h2>Seguir un pedido</h2>
        <p class="muted" style="margin-top:6px">Pega el enlace o el código que te compartió el comercio.</p>
        <form id="trackForm"><label for="token">Código de seguimiento</label>
          <input id="token" required placeholder="o_….xxxx"><button class="btn btn--block btn--ghost">Ver estado</button></form>
      </aside>
    </div>`;
  let role = "STORE";
  app.querySelectorAll("[data-role]").forEach((b) => b.addEventListener("click", () => {
    role = b.dataset.role;
    app.querySelectorAll("[data-role]").forEach((o) => o.setAttribute("aria-pressed", String(o === b)));
    $("#adminCode").hidden = role !== "ADMIN";
  }));
  $("#login").addEventListener("submit", guard(async (e) => {
    e.preventDefault();
    const userId = $("#userId").value.trim();
    const body = { userId, role };
    if (role === "ADMIN") body.adminCode = $("#code").value;
    const result = await api("POST", "/auth/dev-login", { body });
    session = { token: result.token, actor: result.actor };
    save(SESSION_KEY, session);
    save("fd.lastUser", userId);
    location.hash = { STORE: "#/comercio", COURIER: "#/repartidor", ADMIN: "#/admin" }[role];
  }));
  $("#trackForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const raw = $("#token").value.trim();
    location.hash = "#/seguimiento/" + encodeURIComponent(raw.split("/seguimiento/").pop());
  });
}

// ---------- perfil (comercio / repartidor) ----------
async function registration(kind) {
  const list = await zones();
  app.innerHTML = `<section class="card" style="max-width:560px;margin:0 auto">
    <h2>${kind === "store" ? "Registra tu comercio" : "Registra tu perfil de repartidor"}</h2>
    <p class="muted" style="margin-top:6px">Un administrador debe habilitarlo antes de ${kind === "store" ? "publicar pedidos" : "aceptar pedidos"}.</p>
    <form id="reg"><label for="name">Nombre</label><input id="name" required maxlength="120">
      <label for="zone">Zona</label><select id="zone">${list.map((z) => `<option value="${esc(z.zoneId)}">${esc(z.name)}</option>`).join("")}</select>
      <button class="btn btn--block">Registrar</button></form></section>`;
  $("#reg").addEventListener("submit", guard(async (e) => {
    e.preventDefault();
    await api("POST", kind === "store" ? "/stores" : "/couriers", { body: { name: $("#name").value, zoneId: $("#zone").value } });
    toast("Registro enviado; queda pendiente de habilitación");
    render();
  }));
}

function waiting(kind, id) {
  app.innerHTML = `<section class="card" style="max-width:560px;margin:0 auto">
    <div class="notice">Tu ${kind} está pendiente de habilitación.</div>
    <p>Comparte este identificador con un administrador:</p>
    <p class="mono" style="margin:10px 0 4px;font-size:1.1rem">${esc(id)}</p>
    <button class="btn btn--block btn--ghost" data-act="reload">Ya me habilitaron, actualizar</button></section>`;
}

async function profile(path, kind) {
  try { return await api("GET", path); } catch (error) {
    if (error.status === 404) { await registration(kind); return null; }
    throw error;
  }
}

// ---------- comercio ----------
async function storeView() {
  await zones();
  const store = await profile("/stores/me", "store");
  if (!store) return;
  if (!store.enabled) return waiting("comercio", store.storeId);
  const ui = { filter: "", cursor: null, items: [] };
  app.innerHTML = `
    <div class="card__head"><div><h1 style="font-size:2rem">${esc(store.name)}</h1>
      <p class="muted">Zona ${esc(zoneName(store.zoneId))} · <span class="mono">${esc(store.storeId)}</span></p></div></div>
    <div class="layout">
      <div>
        <section class="card">
          <div class="card__head"><h2>Tus pedidos</h2>
            <div class="chips filters" role="group" aria-label="Filtrar por estado">
              ${["", ...Object.keys(STATUS)].map((s) => `<button type="button" class="chip" data-filter="${s}" aria-pressed="${s === ""}">${s ? STATUS[s] : "Todos"}</button>`).join("")}
            </div></div>
          <div class="list" id="orders"></div>
          <button class="btn btn--block btn--ghost" id="more" hidden>Cargar más</button>
        </section>
        <section class="card"><div class="card__head"><h2>Repartidores conectados en tu zona</h2>
          <button class="btn btn--sm btn--ghost" id="refreshPresence">Actualizar</button></div>
          <div class="list" id="presence"></div>
          <p class="muted" style="margin-top:10px">Presencia efímera en Redis (heartbeat con TTL). No decide asignaciones.</p></section>
      </div>
      <aside class="sticky">
        <section class="card"><h2>Nuevo pedido</h2>
          <form id="newOrder">
            <label for="pickup">Recoger en</label><input id="pickup" required maxlength="300" placeholder="Dirección del comercio">
            <label for="dropoff">Entregar en</label><input id="dropoff" required maxlength="300" placeholder="Dirección del cliente">
            <label for="fee">Tarifa (COP)</label><input id="fee" required type="number" min="100" max="100000000" step="100" value="8000">
            <div class="highlight"><span>Total a pagar al repartidor</span><strong id="feeView">$8.000</strong></div>
            <button class="btn btn--block btn--accent">Publicar pedido</button>
          </form></section>
        <section class="card"><div class="card__head"><h2>Este mes</h2><span id="src" class="badge"></span></div>
          <div class="stats"><div class="stat"><span class="muted">Entregados</span><strong id="delivered">—</strong></div>
            <div class="stat"><span class="muted">Facturado</span><strong id="billed">—</strong></div></div>
          <button class="btn btn--block btn--ghost btn--sm" id="refreshStats">Consultar de nuevo</button>
          <p class="muted" style="margin-top:10px">La primera consulta lee DynamoDB y guarda una copia en Redis; las siguientes salen de caché hasta que una entrega la invalida.</p></section>
      </aside>
    </div>`;

  const row = (o) => `<button type="button" class="item" data-order="${esc(o.orderId)}">
      <span><b>${esc(o.pickupAddress || "Pedido")}</b><br><span class="id">${esc(o.orderId)}</span></span>${badge(o.status)}
      <span class="meta"><span>${when(o.createdAt)}</span>${o.feeMinor ? `<span>${money(o.feeMinor)}</span>` : ""}${o.courierId ? `<span>Repartidor ${esc(o.courierId)}</span>` : ""}</span></button>`;

  async function loadOrders(reset) {
    if (reset) { ui.cursor = null; ui.items = []; }
    const q = new URLSearchParams({ limit: "10" });
    if (ui.filter) q.set("status", ui.filter);
    if (ui.cursor) q.set("cursor", ui.cursor);
    const page = await api("GET", "/stores/me/orders?" + q);
    ui.items = reset ? page.items : ui.items.concat(page.items);
    ui.cursor = page.nextCursor;
    $("#orders").innerHTML = ui.items.length ? ui.items.map(row).join("") : `<div class="empty">Aún no hay pedidos${ui.filter ? " en este estado" : ""}.</div>`;
    $("#more").hidden = !ui.cursor;
  }

  async function loadStats() {
    const s = await api("GET", "/stores/me/stats?month=" + month());
    $("#delivered").textContent = s.deliveredCount;
    $("#billed").textContent = money(s.totalFeeMinor);
    $("#src").className = "badge src-" + s.source;
    $("#src").textContent = s.source === "cache" ? "Desde Redis" : "Desde DynamoDB";
  }

  async function loadPresence() {
    try {
      const page = await api("GET", `/zones/${encodeURIComponent(store.zoneId)}/couriers?limit=20`);
      $("#presence").innerHTML = page.items.length ? page.items.map((p) => `<div class="item" style="cursor:default">
        <span><span class="pulse"></span> <b>${esc(p.courierId)}</b></span><span class="muted">vence en ${p.expiresInSeconds}s</span></div>`).join("")
        : `<div class="empty">No hay repartidores conectados ahora.</div>`;
    } catch (error) { $("#presence").innerHTML = `<div class="empty">${esc(error.message)}</div>`; }
  }

  app.querySelectorAll("[data-filter]").forEach((b) => b.addEventListener("click", guard(async () => {
    ui.filter = b.dataset.filter;
    app.querySelectorAll("[data-filter]").forEach((o) => o.setAttribute("aria-pressed", String(o === b)));
    await loadOrders(true);
  })));
  $("#more").addEventListener("click", guard(() => loadOrders(false)));
  $("#orders").addEventListener("click", (e) => { const b = e.target.closest("[data-order]"); if (b) orderDialog(b.dataset.order, () => loadOrders(true)); });
  $("#fee").addEventListener("input", () => { $("#feeView").textContent = money($("#fee").value); });
  $("#refreshStats").addEventListener("click", guard(loadStats));
  $("#refreshPresence").addEventListener("click", guard(loadPresence));
  $("#newOrder").addEventListener("submit", guard(async (e) => {
    e.preventDefault();
    const body = { pickupAddress: $("#pickup").value, dropoffAddress: $("#dropoff").value, feeMinor: Number($("#fee").value) };
    const created = await api("POST", "/orders", { body, intent: "create:" + JSON.stringify(body) });
    const tokens = load(TOKENS_KEY, {});
    tokens[created.orderId] = created.trackingToken;
    save(TOKENS_KEY, tokens);
    $("#dropoff").value = "";
    toast("Pedido publicado; ya lo ven los repartidores de la zona");
    await loadOrders(true);
    orderDialog(created.orderId, () => loadOrders(true));
  }));
  await Promise.all([loadOrders(true), loadStats(), loadPresence()]);
  every(8000, () => { if (!ui.cursor || ui.items.length <= 10) loadOrders(true).catch(() => {}); });
  every(15000, () => loadPresence());
}

async function orderDialog(orderId, onChange) {
  const dialog = document.createElement("dialog");
  document.body.appendChild(dialog);
  dialog.addEventListener("close", () => dialog.remove());
  async function paint() {
    const [order, events] = await Promise.all([api("GET", "/orders/" + encodeURIComponent(orderId)),
      api("GET", `/orders/${encodeURIComponent(orderId)}/events?limit=50`)]);
    const token = load(TOKENS_KEY, {})[orderId];
    const link = token ? `${location.origin}/#/seguimiento/${encodeURIComponent(token)}` : null;
    const canCancel = session.actor.role === "STORE" && ["PENDING", "ASSIGNED"].includes(order.status);
    dialog.innerHTML = `<div class="dialog__body">
      <div class="card__head"><h2>Pedido ${short(order.orderId)}</h2>${badge(order.status)}</div>
      <p class="muted"><span class="mono">${esc(order.orderId)}</span></p>
      <div class="grid grid--2" style="margin-top:14px">
        <div class="stat"><span class="muted">Recoger en</span><b style="display:block">${esc(order.pickupAddress)}</b></div>
        <div class="stat"><span class="muted">Entregar en</span><b style="display:block">${esc(order.dropoffAddress)}</b></div>
      </div>
      <div class="highlight"><span>Tarifa</span><strong>${money(order.feeMinor)}</strong></div>
      <p class="muted" style="margin-top:12px">Zona ${esc(zoneName(order.zoneId))}${order.courierId ? ` · Repartidor <b>${esc(order.courierId)}</b>` : ""} · versión ${order.version}</p>
      <h3 style="margin:18px 0 10px">Historial</h3>
      <ol class="timeline">${events.items.map((ev) => `<li><b>${esc(EVENT_LABEL[ev.eventType] || ev.eventType)}</b><time>${when(ev.occurredAt)}</time></li>`).join("")}</ol>
      ${link ? `<label for="share">Enlace de seguimiento para el cliente</label>
        <div class="row"><input id="share" readonly value="${esc(link)}"><button class="btn btn--ghost" data-copy>Copiar enlace</button></div>` : ""}
      <div class="row" style="margin-top:16px">
        ${canCancel ? `<button class="btn btn--danger" data-cancel>Cancelar pedido</button>` : "<span></span>"}
        <button class="btn" data-close>Cerrar</button></div></div>`;
    dialog.querySelector("[data-close]").addEventListener("click", () => dialog.close());
    dialog.querySelector("[data-copy]")?.addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(link); toast("Enlace copiado"); } catch { $("#share", dialog).select(); }
    });
    dialog.querySelector("[data-cancel]")?.addEventListener("click", guard(async () => {
      if (!confirm("¿Cancelar este pedido? Si ya tenía repartidor, quedará liberado.")) return;
      await api("POST", `/orders/${encodeURIComponent(orderId)}/cancel`, { intent: "cancel:" + orderId });
      toast("Pedido cancelado");
      onChange?.();
      await paint();
    }));
  }
  try { await paint(); dialog.showModal(); } catch (error) { dialog.remove(); toast(error.message, true); }
}

// ---------- repartidor ----------
async function courierView() {
  await zones();
  let courier = await profile("/couriers/me", "courier");
  if (!courier) return;
  if (!courier.enabled) return waiting("perfil de repartidor", courier.courierId);
  let presence = null;
  app.innerHTML = `
    <div class="card__head"><div><h1 style="font-size:2rem">${esc(courier.name)}</h1>
      <p class="muted">Zona ${esc(zoneName(courier.zoneId))} · <span class="mono">${esc(courier.courierId)}</span></p></div></div>
    <div class="layout">
      <div>
        <section class="card"><div class="card__head"><h2>Pedidos disponibles en tu zona</h2><span class="muted" id="openCount"></span></div>
          <div class="list" id="open"></div>
          <p class="muted" style="margin-top:10px">Lista con consistencia eventual: al aceptar, DynamoDB confirma de forma atómica que nadie más lo tomó.</p></section>
        <section class="card"><h2 style="margin-bottom:14px">Tu historial</h2><div class="list" id="history"></div></section>
      </div>
      <aside class="sticky">
        <section class="card">
          <div class="switch"><span><b>Disponible</b><br><span class="muted" id="presenceText">Desconectado</span></span>
            <input type="checkbox" id="available" aria-label="Disponible" ${courier.available ? "checked" : ""}></div>
        </section>
        <section class="card" id="active"></section>
      </aside>
    </div>`;

  async function beat() {
    if (!courier.available) { $("#presenceText").textContent = "Desconectado"; return; }
    try {
      presence = await api("POST", "/couriers/me/heartbeat");
      $("#presenceText").innerHTML = `<span class="pulse"></span> Conectado · se renueva cada 20 s`;
    } catch (error) { $("#presenceText").textContent = error.message; }
  }

  async function loadActive() {
    const { order } = await api("GET", "/couriers/me/active");
    const box = $("#active");
    if (!order) { box.innerHTML = `<h2>Sin pedido activo</h2><p class="muted" style="margin-top:6px">Acepta un pedido de la lista para empezar.</p>`; return null; }
    const next = order.status === "ASSIGNED" ? ["pickup", "Marcar recogido"] : ["deliver", "Marcar entregado"];
    box.innerHTML = `<div class="card__head"><h2>Pedido activo</h2>${badge(order.status)}</div>
      <div class="stat"><span class="muted">Recoger en</span><b style="display:block">${esc(order.pickupAddress)}</b></div>
      <div class="stat" style="margin-top:10px"><span class="muted">Entregar en</span><b style="display:block">${esc(order.dropoffAddress)}</b></div>
      <div class="highlight"><span>Ganas</span><strong>${money(order.feeMinor)}</strong></div>
      <button class="btn btn--block btn--accent" data-step="${next[0]}">${next[1]}</button>`;
    box.querySelector("[data-step]").addEventListener("click", guard(async () => {
      await api("POST", `/orders/${encodeURIComponent(order.orderId)}/${next[0]}`, { intent: next[0] + ":" + order.orderId });
      toast(next[0] === "pickup" ? "Pedido recogido" : "¡Entregado! Buen trabajo");
      await Promise.all([loadActive(), loadHistory()]);
    }));
    return order;
  }

  async function loadOpen() {
    const active = !!$("#active [data-step]");
    const page = await api("GET", `/orders/available?zoneId=${encodeURIComponent(courier.zoneId)}&limit=20`);
    $("#openCount").textContent = page.items.length ? `${page.items.length} disponibles` : "";
    $("#open").innerHTML = page.items.length ? page.items.map((o) => `<div class="item" style="cursor:default">
        <span><b>${esc(o.pickupAddress)}</b><br><span class="id">${esc(o.orderId)}</span></span><strong>${money(o.feeMinor)}</strong>
        <span class="meta"><span>Publicado ${when(o.createdAt)}</span>
          <button class="btn btn--sm" data-accept="${esc(o.orderId)}" ${active || !courier.available ? "disabled" : ""}>Aceptar</button></span></div>`).join("")
      : `<div class="empty">No hay pedidos abiertos en tu zona.</div>`;
  }

  async function loadHistory() {
    const page = await api("GET", "/couriers/me/orders?limit=10");
    $("#history").innerHTML = page.items.length ? page.items.map((o) => `<div class="item" style="cursor:default">
      <span class="id">${esc(o.orderId)}</span>${badge(o.status)}<span class="meta"><span>${when(o.updatedAt)}</span></span></div>`).join("")
      : `<div class="empty">Todavía no has hecho entregas.</div>`;
  }

  $("#open").addEventListener("click", guard(async (e) => {
    const b = e.target.closest("[data-accept]");
    if (!b) return;
    try {
      await api("POST", `/orders/${encodeURIComponent(b.dataset.accept)}/accept`, { intent: "accept:" + b.dataset.accept });
      toast("¡Pedido tuyo! Ve a recogerlo");
    } catch (error) {
      toast(error.code === "ORDER_ALREADY_ASSIGNED" ? "Otro repartidor lo aceptó primero" : error.message, true);
    }
    await loadActive();
    await Promise.all([loadOpen(), loadHistory()]);
  }));
  $("#available").addEventListener("change", guard(async (e) => {
    courier = await api("PATCH", "/couriers/me/availability", { body: { available: e.target.checked } });
    e.target.checked = courier.available;
    toast(courier.available ? "Estás disponible" : "Te desconectaste; tu pedido activo sigue a tu cargo");
    await beat();
    await loadOpen();
  }));
  await loadActive();
  await Promise.all([loadOpen(), loadHistory(), beat()]);
  every(20000, beat);
  every(6000, () => { loadActive().then(loadOpen).catch(() => {}); });
}

// ---------- administración ----------
function adminView() {
  app.innerHTML = `<h1 style="font-size:2rem;margin-bottom:16px">Administración</h1>
    <div class="grid grid--2">
      ${["store", "courier"].map((k) => `<section class="card"><h2>${k === "store" ? "Comercios" : "Repartidores"}</h2>
        <form data-enable="${k}"><label for="${k}Id">Identificador</label><input id="${k}Id" required pattern="[A-Za-z0-9_\\-]+">
          <div class="row"><button class="btn btn--block" value="true">Habilitar</button><button class="btn btn--block btn--danger" value="false">Deshabilitar</button></div>
          <p class="muted" data-out style="margin-top:10px"></p></form></section>`).join("")}
      <section class="card"><h2>Consultar pedido</h2>
        <form id="lookup"><label for="orderId">ID del pedido</label><input id="orderId" required>
          <div class="row"><button class="btn btn--block btn--ghost" value="view">Ver detalle</button><button class="btn btn--block btn--danger" value="fail">Marcar fallido</button></div></form>
        <p class="muted" style="margin-top:10px">Marcar fallido es un procedimiento excepcional: solo desde «Recogido».</p></section>
      <section class="card"><h2>Presencia por zona</h2><form id="zoneForm"><label for="zoneSel">Zona</label><select id="zoneSel"></select>
        <button class="btn btn--block btn--ghost">Ver conectados</button></form><div class="list" id="zoneOut" style="margin-top:12px"></div></section>
    </div>`;
  zones().then((list) => { $("#zoneSel").innerHTML = list.map((z) => `<option value="${esc(z.zoneId)}">${esc(z.name)}</option>`).join(""); });
  app.querySelectorAll("[data-enable]").forEach((form) => form.addEventListener("submit", guard(async (e) => {
    e.preventDefault();
    const kind = form.dataset.enable;
    const id = $(`#${kind}Id`).value.trim();
    const enabled = e.submitter?.value !== "false";
    const result = await api("PATCH", `/admin/${kind === "store" ? "stores" : "couriers"}/${encodeURIComponent(id)}`, { body: { enabled } });
    $("[data-out]", form).textContent = `${result.name}: ${result.enabled ? "habilitado" : "deshabilitado"} (versión ${result.version})`;
    toast("Cambio guardado");
  })));
  $("#lookup").addEventListener("submit", guard(async (e) => {
    e.preventDefault();
    const id = $("#orderId").value.trim();
    if (e.submitter?.value === "fail") {
      if (!confirm("¿Marcar este pedido como fallido?")) return;
      await api("POST", `/orders/${encodeURIComponent(id)}/fail`, { intent: "fail:" + id });
      toast("Pedido marcado como fallido");
    }
    orderDialog(id);
  }));
  $("#zoneForm").addEventListener("submit", guard(async (e) => {
    e.preventDefault();
    const page = await api("GET", `/zones/${encodeURIComponent($("#zoneSel").value)}/couriers?limit=50`);
    $("#zoneOut").innerHTML = page.items.length ? page.items.map((p) => `<div class="item" style="cursor:default"><span><span class="pulse"></span> ${esc(p.courierId)}</span><span class="muted">${p.expiresInSeconds}s</span></div>`).join("")
      : `<div class="empty">Nadie conectado en esta zona.</div>`;
  }));
}

// ---------- seguimiento público ----------
async function trackingView(token) {
  if (!token) { home(); $("#token")?.focus(); return; }
  app.innerHTML = `<section class="card" style="max-width:640px;margin:0 auto" id="tracking"><p class="muted">Consultando…</p></section>`;
  async function paint() {
    const box = $("#tracking");
    try {
      const t = await api("GET", "/tracking/" + encodeURIComponent(token) + "?limit=50");
      const reached = new Set(t.events.map((e) => e.eventType));
      const flow = [["CREATED", "Creado"], ["ASSIGNED", "Asignado"], ["PICKED_UP", "Recogido"], ["DELIVERED", "Entregado"]];
      box.innerHTML = `<div class="card__head"><h2>Tu pedido</h2>${badge(t.status)}</div>
        <p class="muted">Actualizado ${when(t.updatedAt)}</p>
        ${["CANCELLED", "FAILED"].includes(t.status) ? `<div class="notice" style="margin-top:14px">${t.status === "CANCELLED" ? "El comercio canceló este pedido." : "La entrega no pudo completarse."}</div>`
          : `<div class="steps">${flow.map(([k, l]) => `<div class="step ${reached.has(k) ? "done" : ""}">${l}</div>`).join("")}</div>`}
        <ol class="timeline">${t.events.map((e) => `<li><b>${esc(EVENT_LABEL[e.eventType] || e.eventType)}</b><time>${when(e.occurredAt)}</time></li>`).join("")}</ol>
        <p class="muted" style="margin-top:14px">Solo mostramos el estado y los hitos: ni direcciones ni datos personales.</p>`;
    } catch (error) {
      box.innerHTML = `<h2>No encontramos ese pedido</h2><p class="muted" style="margin-top:8px">Revisa el enlace que te compartieron.</p>
        <a class="btn btn--block btn--ghost" href="#/seguimiento">Probar con otro código</a>`;
      timers.forEach(clearInterval); timers = [];
    }
  }
  await paint();
  every(10000, paint);
}

// ---------- enrutado ----------
async function render() {
  timers.forEach(clearInterval);
  timers = [];
  nav();
  const [, route, arg] = location.hash.split("/");
  try {
    if (route === "seguimiento") return await trackingView(arg ? decodeURIComponent(arg) : "");
    if (!session) return home();
    const target = { STORE: "comercio", COURIER: "repartidor", ADMIN: "admin" }[session.actor.role];
    if (route !== target) { location.hash = "#/" + target; return; }
    if (target === "comercio") return await storeView();
    if (target === "repartidor") return await courierView();
    return adminView();
  } catch (error) {
    app.innerHTML = `<section class="card" style="max-width:560px;margin:0 auto"><h2>Algo salió mal</h2>
      <p class="muted" style="margin-top:8px">${esc(error.message)}</p><button class="btn btn--block" data-act="reload">Reintentar</button></section>`;
  }
}

document.addEventListener("click", (e) => {
  const act = e.target.closest("[data-act]")?.dataset.act;
  if (act === "logout") logout(false);
  if (act === "reload") render();
});
window.addEventListener("hashchange", render);
render();
