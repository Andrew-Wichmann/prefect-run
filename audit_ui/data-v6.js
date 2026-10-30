// Scenario first: see all 700 scenarios at once as one chart (how far each moves the book), drag to pick a range,
// then page through the instruments for just those scenarios.
registerView({
  n: 6, title: "Scenario chart → table",
  blurb: "Top: for each of the 700 scenarios, the mean (line) and the best/worst instrument (band) as a percentage move from input price. Drag across it to choose scenarios; the table below shows them.",
  async mount(el, { meta }) {
    el.append(h("div", { class: "note" }, "Computing scenario statistics…"));
    const { scenarios } = await getJSON("scenarios");
    el.innerHTML = "";
    const N = scenarios.length, W = 1000, H = 190, padL = 44, padB = 20;
    const lo = Math.min(...scenarios.map((s) => s.min)), hi = Math.max(...scenarios.map((s) => s.max));
    const x = (i) => padL + (i + 0.5) / N * (W - padL), y = (v) => 8 + (hi - v) / (hi - lo || 1) * (H - padB - 8);
    const band = `M${scenarios.map((s, i) => `${x(i).toFixed(1)},${y(s.max).toFixed(1)}`).join("L")}L${[...scenarios].reverse().map((s, i) => `${x(N - 1 - i).toFixed(1)},${y(s.min).toFixed(1)}`).join("L")}Z`;
    const mean = `M${scenarios.map((s, i) => `${x(i).toFixed(1)},${y(s.mean).toFixed(1)}`).join("L")}`;
    const ticks = [lo, 0, hi].map((v) => `<text x="${padL - 4}" y="${y(v) + 4}" text-anchor="end" font-size="10" fill="var(--muted)">${pct(v)}</text><line x1="${padL}" x2="${W}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line)" ${v === 0 ? "" : 'stroke-dasharray="3 3"'}/>`).join("");
    const sel = h("rect", { y: 0, height: H - padB, fill: "var(--run)", opacity: ".18" });
    const svg = h("svg", { viewBox: `0 0 ${W} ${H}`, style: "width:100%;height:190px;cursor:crosshair;flex:none", role: "img", "aria-label": "per-scenario price move" });
    svg.innerHTML = `${ticks}<path d="${band}" fill="var(--run)" opacity=".3"/><path d="${mean}" fill="none" stroke="var(--warn)" stroke-width="1.5"/>${[1, 100, 200, 300, 400, 500, 600, 700].filter((n) => n <= N).map((n) => `<text x="${x(n - 1)}" y="${H - 5}" font-size="10" text-anchor="middle" fill="var(--muted)">${n}</text>`).join("")}`;
    svg.append(sel);

    let a = 0, b = Math.min(N - 1, 19), rowSize = 25, row = 0, seq = 0, drag = false;
    const info = h("span", { class: "note" }), rangeInfo = h("span", { class: "note" });
    const wrap = h("div", { class: "scroll" });
    const [prev, next] = [["← Prev", -1], ["Next →", 1]].map(([t, s]) => h("button", { class: "btn", onclick: () => { row = Math.max(0, row + s * rowSize); load(); } }, t));
    const worst = h("button", { class: "btn", onclick: () => { const i = scenarios.reduce((m, s, k) => (s.mean < scenarios[m].mean ? k : m), 0); a = b = i; paint(); } }, "worst scenario");
    const best = h("button", { class: "btn", onclick: () => { const i = scenarios.reduce((m, s, k) => (s.mean > scenarios[m].mean ? k : m), 0); a = b = i; paint(); } }, "best scenario");
    el.append(svg, h("div", { class: "tools" }, rangeInfo, worst, best, h("span", { class: "sp" }), prev, next, info,
      excelButtons(() => ({ row_offset: row, row_limit: rowSize, col_offset: a, col_limit: Math.min(b - a + 1, 50) }))), wrap);

    const at = (e) => { const r = svg.getBoundingClientRect(); return Math.max(0, Math.min(N - 1, Math.floor(((e.clientX - r.left) / r.width * W - padL) / (W - padL) * N))); };
    let anchor = 0;
    svg.addEventListener("pointerdown", (e) => { drag = true; svg.setPointerCapture(e.pointerId); anchor = a = b = at(e); highlight(); });
    svg.addEventListener("pointermove", (e) => { if (drag) { const i = at(e); a = Math.min(anchor, i); b = Math.max(anchor, i); highlight(); } });
    svg.addEventListener("pointerup", () => { if (drag) { drag = false; paint(); } });
    const highlight = () => { sel.setAttribute("x", x(a) - (W - padL) / N / 2); sel.setAttribute("width", (b - a + 1) * (W - padL) / N); rangeInfo.textContent = `scenarios ${a + 1}–${b + 1}${b - a + 1 > 50 ? " (table shows the first 50)" : ""}`; };
    const paint = () => { row = 0; highlight(); load(); };

    async function load() {
      const mine = ++seq, cols = Math.min(b - a + 1, 50);
      const d = await getJSON("matrix", { row_offset: row, row_limit: rowSize, col_offset: a, col_limit: cols });
      if (mine !== seq) return;
      prev.disabled = row <= 0; next.disabled = row + rowSize >= d.total_rows;
      info.textContent = `${n0(row + 1)}–${n0(row + d.keys.length)} of ${n0(d.total_rows)}`;
      wrap.innerHTML = `<table class="dt"><thead><tr><th>instrument</th><th>status</th><th>price</th>${d.scenario_names.map((c) => `<th>${c.replace("pricing_scenario_", "scenario ")}</th>`).join("")}</tr></thead><tbody>${d.keys.map((k, i) => `<tr><td>${esc(k)}</td><td>${statusCell(d.outcomes[i])}</td><td>${fmt(d.price[i])}</td>${d.values[i].map((v) => `<td style="${heat(v, d.price[i])}">${fmt(v)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
    }
    paint();
    return () => { seq++; };
  },
});
