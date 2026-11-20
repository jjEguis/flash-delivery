import test from "node:test";
import assert from "node:assert/strict";
import { createPagedList } from "../../pagination.js";

test("página siguiente conserva cursor ante error y permite reintentar sin duplicados", async () => {
  const calls = []; let fail = true;
  const list = createPagedList({ loadPage: async cursor => {
    calls.push(cursor);
    if (!cursor) return { items: [{ orderId: "o1" }], nextCursor: "next" };
    if (fail) { fail = false; throw new Error("offline"); }
    return { items: [{ orderId: "o1", status: "updated" }, { orderId: "o2" }], nextCursor: null };
  } });
  await list.refresh();
  await assert.rejects(list.loadMore());
  assert.equal(list.snapshot().nextCursor, "next");
  assert.equal(list.snapshot().items.length, 1);
  await list.loadMore();
  assert.deepEqual(calls, [null, "next", "next"]);
  assert.deepEqual(list.snapshot().items, [{ orderId: "o1", status: "updated" }, { orderId: "o2" }]);
  await list.loadMore();
  assert.equal(calls.length, 3);
});

test("refresco mantiene las páginas cargadas y reemplaza estados anteriores", async () => {
  let version = 1;
  const list = createPagedList({ loadPage: async cursor => ({
    items: [{ orderId: cursor ? "o2" : "o1", version }], nextCursor: cursor ? null : "page-2",
  }) });
  await list.refresh(); await list.loadMore();
  version = 2;
  await list.refresh();
  assert.deepEqual(list.snapshot().items.map(item => item.version), [2, 2]);
  assert.equal(list.snapshot().pages, 2);
});

test("un refresco parcial fallido no borra ninguna página visible", async () => {
  let fail = false;
  const list = createPagedList({ loadPage: async cursor => {
    if (fail && cursor) throw new Error("second page failed");
    return { items: [{ orderId: cursor ? "o2" : "o1" }], nextCursor: cursor ? null : "next" };
  } });
  await list.refresh(); await list.loadMore();
  const before = list.snapshot(); fail = true;
  await assert.rejects(list.refresh());
  assert.deepEqual(list.snapshot(), before);
});

test("doble clic no solicita dos veces la misma página", async () => {
  let resolve; let calls = 0;
  const list = createPagedList({ loadPage: () => { calls++; return new Promise(done => { resolve = done; }); } });
  const a = list.loadMore(), b = list.loadMore();
  await Promise.resolve();
  assert.equal(calls, 1);
  resolve({ items: [{ orderId: "o1" }], nextCursor: null });
  await Promise.all([a, b]);
  assert.equal(list.snapshot().items.length, 1);
});

test("cursor repetido no deja al usuario cargando una página infinita", async () => {
  const list = createPagedList({ loadPage: async () => ({ items: [{ orderId: "o1" }], nextCursor: "same" }) });
  await list.refresh();
  await assert.rejects(list.loadMore(), /página inválida/);
  assert.equal(list.snapshot().pages, 1);
});
