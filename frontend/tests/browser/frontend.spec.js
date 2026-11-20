import { test, expect } from "@playwright/test";

const zone = { zoneId: "centro", name: "Centro" };
const date = "2026-11-15T12:00:00.000000Z";
const order = (id, status = "PENDING") => ({ orderId: id, status, createdAt: date, updatedAt: date,
  pickupAddress: "Recoger " + id, dropoffAddress: "Destino " + id, feeMinor: 8000, zoneId: "centro", version: 1 });
const openCursor = "opaque+/=cursor";

async function mockApi(page, { role = "COURIER", signedIn = true, intercept } = {}) {
  const actor = { role, actorId: role === "STORE" ? "store_demo" : "courier_demo" };
  if (signedIn) await page.addInitScript(({ actor }) => localStorage.setItem("fd.session", JSON.stringify({ token: "test-token", actor })), { actor });
  const state = { calls: [], active: null, storeOrders: [] };
  const history = Array.from({ length: 11 }, (_, i) => order("history_" + (i + 1), "DELIVERED"));
  await page.route("**/api/v1/**", async route => {
    const request = route.request(), url = new URL(request.url()), path = url.pathname.slice(7);
    state.calls.push({ path, method: request.method(), cursor: url.searchParams.get("cursor"),
      key: request.headers()["idempotency-key"], body: request.postDataJSON() });
    if (intercept && await intercept({ route, request, url, path, state })) return;
    let data;
    if (path === "/auth/dev-login") data = { token: "test-token", actor };
    else if (path === "/zones") data = { items: [zone] };
    else if (path === "/stores/me") data = { storeId: "store_demo", name: "Tienda Demo", enabled: true, zoneId: "centro" };
    else if (path === "/stores/me/orders") data = { items: state.storeOrders, nextCursor: null };
    else if (path === "/stores/me/stats") data = { deliveredCount: 0, totalFeeMinor: 0, source: "dynamodb" };
    else if (path === "/zones/centro/couriers") data = { items: [], nextCursor: null };
    else if (path === "/couriers/me") data = { courierId: "courier_demo", name: "Repartidor Demo", enabled: true, available: true, zoneId: "centro" };
    else if (path === "/couriers/me/heartbeat") data = { expiresInSeconds: 60 };
    else if (path === "/couriers/me/active") data = { order: state.active };
    else if (path === "/orders/available") data = url.searchParams.has("cursor")
      ? { items: [order("open_20"), order("open_21")], nextCursor: null }
      : { items: Array.from({ length: 20 }, (_, i) => order("open_" + (i + 1))), nextCursor: openCursor };
    else if (path === "/couriers/me/orders") {
      const all = state.active ? [state.active, ...history] : history;
      data = { items: all.slice(url.searchParams.has("cursor") ? 10 : 0, url.searchParams.has("cursor") ? 20 : 10),
        nextCursor: url.searchParams.has("cursor") ? null : "history-next" };
    } else if (path.endsWith("/accept")) {
      state.active = order(path.split("/")[2], "ASSIGNED");
      data = state.active;
    } else if (path === "/orders/o_created/events") data = { items: [{ eventType: "CREATED", occurredAt: date }], nextCursor: null };
    else if (path === "/orders/o_created") data = state.storeOrders[0];
    else throw new Error("Ruta no simulada: " + request.method() + " " + path);
    await route.fulfill({ json: data });
  });
  return state;
}

test("login y paginación: pedido 21, historial 11 y refresco sin perder páginas", async ({ page }) => {
  await page.clock.install();
  const state = await mockApi(page, { signedIn: false });
  await page.goto("/");
  await page.locator('[data-role="COURIER"]').click();
  await page.getByLabel("Usuario", { exact: true }).fill("courier_demo");
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
  await expect(page.locator("#open [data-accept]")).toHaveCount(20);
  await page.getByRole("button", { name: "Cargar más pedidos", exact: true }).click();
  await expect(page.locator("#open [data-accept]")).toHaveCount(21);
  await expect(page.locator("#moreOpen")).toBeHidden();
  await page.getByRole("button", { name: "Cargar más historial", exact: true }).click();
  await expect(page.locator("#history .item")).toHaveCount(11);
  await expect(page.locator("#moreHistory")).toBeHidden();
  expect(state.calls.find(call => call.path === "/orders/available" && call.cursor)?.cursor).toBe(openCursor);
  await page.clock.runFor(6100);
  await expect.poll(() => state.calls.filter(call => call.path === "/orders/available" && call.cursor).length).toBeGreaterThan(1);
  await expect(page.locator("#open [data-accept]")).toHaveCount(21);
  await page.locator('[data-accept="open_21"]').click();
  await expect(page.locator("#active")).toContainText("Recoger open_21");
  await expect(page.locator("#active [data-step]")).toHaveText("Marcar recogido");
  await expect(page.locator("#history .item")).toHaveCount(12);
  await expect(page.locator("#open [data-accept]:enabled")).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("fallo en segunda página conserva filas y cursor para reintentar", async ({ page }) => {
  let failed = false;
  const state = await mockApi(page, { intercept: async ({ route, path, url }) => {
    if (path === "/orders/available" && url.searchParams.has("cursor") && !failed) {
      failed = true;
      await route.fulfill({ status: 503, json: { error: { code: "DEPENDENCY_UNAVAILABLE", message: "Intenta de nuevo" } } });
      return true;
    }
  } });
  await page.goto("/#/repartidor");
  await expect(page.locator("#open [data-accept]")).toHaveCount(20);
  await page.locator("#moreOpen").click();
  await expect(page.getByRole("status")).toContainText("Intenta de nuevo");
  await expect(page.locator("#open [data-accept]")).toHaveCount(20);
  await expect(page.locator("#moreOpen")).toBeEnabled();
  await page.locator("#moreOpen").click();
  await expect(page.locator("#open [data-accept]")).toHaveCount(21);
  expect(state.calls.filter(call => call.path === "/orders/available" && call.cursor).map(call => call.cursor)).toEqual([openCursor, openCursor]);
});

for (const failure of ["json", "network", "503"]) {
  test(`crear y reintentar tras ${failure} y recarga confirma un solo pedido`, async ({ page }) => {
    const committed = new Map(), keys = [];
    await mockApi(page, { role: "STORE", intercept: async ({ route, request, path, state }) => {
      if (path !== "/orders" || request.method() !== "POST") return;
      const key = request.headers()["idempotency-key"];
      keys.push(key);
      if (!committed.has(key)) {
        committed.set(key, { ...order("o_created"), trackingToken: "o_created.secret" });
        state.storeOrders.push(order("o_created"));
      }
      if (keys.length === 1) {
        if (failure === "json") await route.fulfill({ status: 201, contentType: "application/json", body: '{"orderId":' });
        else if (failure === "network") await route.abort("failed");
        else await route.fulfill({ status: 503, json: { error: { code: "DEPENDENCY_UNAVAILABLE", message: "Reintenta" } } });
      } else await route.fulfill({ status: 201, json: committed.get(key) });
      return true;
    } });
    await page.goto("/#/comercio");
    const fillOrder = async () => {
      await page.getByLabel("Recoger en", { exact: true }).fill("Origen privado");
      await page.getByLabel("Entregar en", { exact: true }).fill("Destino privado");
      await page.getByRole("button", { name: "Publicar pedido", exact: true }).click();
    };
    await fillOrder();
    await expect(page.getByRole("status")).toBeVisible();
    const saved = await page.evaluate(() => localStorage.getItem("fd.pendingRequests.v1"));
    expect(Object.keys(JSON.parse(saved))).toHaveLength(1);
    expect(saved).not.toContain("privado");
    await page.reload();
    await fillOrder();
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page.getByLabel("Enlace de seguimiento para el cliente")).toHaveValue(/o_created.secret/);
    expect(committed.size).toBe(1);
    expect(keys[0]).toBe(keys[1]);
    expect(await page.evaluate(() => JSON.parse(localStorage.getItem("fd.pendingRequests.v1")))).toEqual({});
  });
}
