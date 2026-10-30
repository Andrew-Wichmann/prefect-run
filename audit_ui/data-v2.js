// Classic server-side pagination in both directions: a page of instruments, a window of scenario columns.
registerView({
  n: 2, title: "Pages × column windows",
  blurb: "Pages of instruments (rows) and a window of scenario columns, each fetched on demand. Jump to any scenario; look up an instrument by key.",
  mount(el, { meta }) {
    let rowSize = 50, colSize = 20, row = 0, col = 0, key = "", seq = 0;
    const rowSel = h("select", { onchange: () => { rowSize = +rowSel.value; row = 0; load(); } }, [25, 50, 100, 250].map((n) => h("option", { value: n, selected: n === rowSize }, `${n} rows`)));
    const colSel = h("select", { onchange: () => { colSize = +colSel.value; load(); } }, [10, 20, 50, 100].map((n) => h("option", { value: n, selected: n === colSize }, `${n} scenarios`)));
    const jump = h("input", { type: "number", min: 1, max: meta.total_cols, placeholder: "scenario #", style: "width:90px", onchange: () => { col = Math.max(0, Math.min(meta.total_cols - 1, +jump.value - 1)); load(); } });
    const find = h("input", { placeholder: "instrument key (exact)", onchange: () => { key = find.value.trim(); row = 0; load(); } });
    const [rp, rn, cp, cn] = [["← rows", () => { row = Math.max(0, row - rowSize); load(); }], ["rows →", () => { row += rowSize; load(); }],
      ["← scenarios", () => { col = Math.max(0, col - colSize); load(); }], ["scenarios →", () => { col += colSize; load(); }]].map(([t, f]) => h("button", { class: "btn", onclick: f }, t));
    const info = h("span", { class: "note" });
    const wrap = h("div", { class: "scroll" });
    el.append(h("div", { class: "tools" }, rp, rn, rowSel, h("span", { class: "note" }, "|"), cp, cn, colSel, jump, find, h("span", { class: "sp" }), info,
      excelButtons(() => ({ row_offset: row, row_limit: rowSize, col_offset: col, col_limit: colSize }))), wrap);

    async function load() {
      const mine = ++seq;
      const d = await getJSON("matrix", { row_offset: row, row_limit: rowSize, col_offset: col, col_limit: colSize, ...(key ? { key } : {}) });
      if (mine !== seq) return;
      const lastRow = d.total_rows, firstScen = col + 1;
      rp.disabled = row <= 0; rn.disabled = row + rowSize >= lastRow;
      cp.disabled = col <= 0; cn.disabled = col + colSize >= d.total_cols;
      info.textContent = d.keys.length ? `rows ${n0(d.row_offset + 1)}–${n0(d.row_offset + d.keys.length)} of ${n0(lastRow)} · scenarios ${firstScen}–${firstScen + d.scenario_names.length - 1} of ${d.total_cols}` : "no rows";
      wrap.innerHTML = `<table class="dt"><thead><tr><th>instrument</th><th>status</th><th>price</th>${d.scenario_names.map((c) => `<th>${c.replace("pricing_scenario_", "scenario ")}</th>`).join("")}</tr></thead><tbody>${
        d.keys.map((k, i) => `<tr><td>${esc(k)}</td><td>${statusCell(d.outcomes[i])}</td><td>${fmt(d.price[i])}</td>${d.values[i].map((v) => `<td style="${heat(v, d.price[i])}">${fmt(v)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
    }
    load();
    return () => { seq++; };
  },
});
