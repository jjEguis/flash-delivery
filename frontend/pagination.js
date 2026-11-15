// Estado de una lista: conserva lo visible si una página falla y evita cargas paralelas.
export function createPagedList({ loadPage, onChange = () => {} }) {
  let items = [], cursor = null, pages = 0, inFlight = null;
  const snapshot = () => ({ items: [...items], nextCursor: cursor, pages });
  function append(current, incoming) {
    const unique = new Map(current.map(item => [item.orderId, item]));
    incoming.forEach(item => unique.set(item.orderId, item));
    return [...unique.values()];
  }
  async function pageAt(position) {
    const page = await loadPage(position);
    if (!Array.isArray(page.items) || (page.nextCursor !== null && typeof page.nextCursor !== "string") ||
        (position && page.nextCursor === position)) throw new Error("La API devolvió una página inválida");
    return page;
  }
  function run(work) {
    if (inFlight) return inFlight;
    inFlight = Promise.resolve().then(work).finally(() => { inFlight = null; });
    return inFlight;
  }
  return {
    snapshot,
    loadMore() {
      return run(async () => {
        if (pages && !cursor) return snapshot();
        const page = await pageAt(cursor);
        items = append(items, page.items);
        cursor = page.nextCursor;
        pages += 1;
        onChange(snapshot());
        return snapshot();
      });
    },
    refresh() {
      return run(async () => {
        let refreshed = [], position = null, loaded = 0;
        do {
          const page = await pageAt(position);
          refreshed = append(refreshed, page.items);
          position = page.nextCursor;
          loaded += 1;
        } while (position && loaded < Math.max(1, pages));
        // Publicar solo cuando se completaron todas las páginas solicitadas.
        items = refreshed;
        cursor = position;
        pages = loaded;
        onChange(snapshot());
        return snapshot();
      });
    },
  };
}
