// Open-source grid library: AG Grid Community with the infinite row model. Rows are fetched in blocks as you scroll;
// the 700 scenario columns are virtualised by the grid, so only the visible ones exist in the DOM.
registerView({
  n: 3, title: "AG Grid (infinite scroll)",
  blurb: "AG Grid Community from a CDN: lazy row blocks from the server, virtualised columns, resizable and pinned columns. Sorting is off because the server returns file order.",
  async mount(el, { meta }) {
    el.append(h("div", { class: "note" }, "Loading AG Grid…"));
    await ensureAgGrid();
    el.innerHTML = "";
    const dark = darkMode();
    const info = h("span", { class: "note" }, "scroll for more; blocks of 100 rows load as needed");
    const box = h("div", { class: `ag-theme-quartz${dark ? "-dark" : ""}`, style: "flex:1;min-height:300px" });
    el.append(h("div", { class: "tools" }, info, h("span", { class: "sp" }), excelButtons(null)), box);

    const money = (p) => (p.value == null ? "" : p.value.toFixed(2));
    const scen = Array.from({ length: meta.total_cols }, (_, i) => ({
      headerName: `scenario ${i + 1}`, colId: `s${i + 1}`, width: 100, type: "rightAligned",
      valueGetter: (p) => p.data?.values[i], valueFormatter: money,
      cellStyle: (p) => {
        if (p.value == null || !p.data.price) return null;
        const m = p.value / p.data.price - 1, a = Math.min(Math.abs(m) / 0.3, 1) * 0.5;
        return { background: m < 0 ? `rgba(220,38,38,${a})` : `rgba(22,163,74,${a})` };
      },
    }));
    const api = agGrid.createGrid(box, {
      columnDefs: [
        { headerName: "instrument", field: "key", pinned: "left", width: 130 },
        { headerName: "status", valueGetter: (p) => p.data?.status, pinned: "left", width: 110 },
        { headerName: "price", field: "price", valueFormatter: money, width: 90, type: "rightAligned" },
        ...scen,
      ],
      defaultColDef: { sortable: false, resizable: true, suppressMovable: true },
      rowModelType: "infinite", cacheBlockSize: 100, maxBlocksInCache: 8, infiniteInitialRowCount: 100,
      datasource: {
        async getRows(p) {
          try {
            const d = await getJSON("matrix", { row_offset: p.startRow, row_limit: p.endRow - p.startRow, col_limit: 0 });
            p.successCallback(d.keys.map((k, i) => ({ key: k, status: d.outcomes[i]?.[0], price: d.price[i], values: d.values[i] })), d.total_rows);
          } catch (e) { p.failCallback(); }
        },
      },
    });
    return () => api.destroy();
  },
});
