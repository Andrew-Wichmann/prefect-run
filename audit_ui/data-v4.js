// Summary first: each instrument is one row with the shape of its 700 scenarios (min / percentiles / max / worst and
// best move). Sort, search and page on the server; open an instrument to see its distribution and every scenario.
registerView({
  n: 4, title: "Summary + drill-down",
  blurb: "One row per instrument with percentiles across its 700 scenarios, sorted and paged on the server. Click a row for its distribution and all scenario prices (paged).",
  mount(el, { meta }) {
    let sort = "key", desc = false, offset = 0, limit = 50, q = "", seq = 0, open = null;
    const COLS = [["key", "instrument"], ["status", "status"], ["price", "price"], ["min", "min"], ["p5", "p5"], ["p50", "median"], ["p95", "p95"], ["max", "max"], ["mean", "mean"], ["std", "std dev"], ["worst_pct", "worst move"], ["best_pct", "best move"]];
    const search = h("input", { placeholder: "search instrument key", onchange: () => { q = search.value.trim(); offset = 0; load(); } });
    const [prev, next] = [["← Prev", -1], ["Next →", 1]].map(([t, s]) => h("button", { class: "btn", onclick: () => { offset = Math.max(0, offset + s * limit); load(); } }, t));
    const info = h("span", { class: "note" });
    const wrap = h("div", { class: "scroll" });
    const detail = h("div", { class: "scroll", style: "flex:none;max-height:45%;display:none;padding:10px" });
    el.append(h("div", { class: "tools" }, search, prev, next, info, h("span", { class: "sp" }), excelButtons(null)), wrap, detail);

    async function load() {
      const mine = ++seq;
      info.textContent = "loading…";
      const d = await getJSON("stats", { sort, dir: desc ? "desc" : "asc", offset, limit, q });
      if (mine !== seq) return;
      prev.disabled = offset <= 0; next.disabled = offset + limit >= d.total;
      info.textContent = d.total ? `${n0(offset + 1)}–${n0(offset + d.rows.length)} of ${n0(d.total)}` : "no matches";
      const th = COLS.map(([k, t]) => `<th data-k="${k}" style="cursor:pointer">${t}${sort === k ? (desc ? " ▾" : " ▴") : ""}</th>`).join("");
      wrap.innerHTML = `<table class="dt"><thead><tr>${th}</tr></thead><tbody>${d.rows.map((r) => `<tr class="click${open === r.key ? " sel" : ""}" data-key="${esc(r.key)}"><td>${esc(r.key)}</td><td>${statusCell([r.status])}</td><td>${fmt(r.price)}</td>${["min", "p5", "p50", "p95", "max", "mean", "std"].map((k) => `<td>${fmt(r[k])}</td>`).join("")}<td style="${heat(r.min, r.price)}">${pct(r.worst_pct)}</td><td style="${heat(r.max, r.price)}">${pct(r.best_pct)}</td></tr>`).join("")}</tbody></table>`;
    }
    wrap.addEventListener("click", (e) => {
      const t = e.target.closest("th[data-k]");
      if (t) { desc = sort === t.dataset.k ? !desc : false; sort = t.dataset.k; offset = 0; return load(); }
      const r = e.target.closest("tr[data-key]");
      if (r) { open = r.dataset.key; inspect(open); load(); }
    });

    async function inspect(key) {
      detail.style.display = "block";
      detail.textContent = "loading…";
      const d = await getJSON("matrix", { key, row_limit: 1, col_limit: 0 });
      const vals = d.values[0], price = d.price[0];
      if (!vals) { detail.textContent = "not found"; return; }
      const lo = Math.min(...vals), hi = Math.max(...vals), bins = 40, hist = new Array(bins).fill(0);
      for (const v of vals) hist[Math.min(bins - 1, Math.floor((v - lo) / (hi - lo || 1) * bins))]++;
      const mx = Math.max(...hist), W = 420, Hh = 90, bw = W / bins;
      const priceX = ((price - lo) / (hi - lo || 1)) * W;
      const svg = `<svg width="${W}" height="${Hh + 18}" role="img" aria-label="distribution of ${vals.length} scenario prices">${hist.map((c, i) => `<rect x="${i * bw + 1}" y="${Hh - (c / mx) * Hh}" width="${bw - 2}" height="${(c / mx) * Hh}" fill="var(--run)" opacity=".75"/>`).join("")}<line x1="${priceX}" x2="${priceX}" y1="0" y2="${Hh}" stroke="var(--warn)" stroke-width="2"/><text x="0" y="${Hh + 14}" font-size="11" fill="var(--muted)">${fmt(lo)}</text><text x="${W}" y="${Hh + 14}" font-size="11" text-anchor="end" fill="var(--muted)">${fmt(hi)}</text><text x="${Math.min(priceX + 4, W - 60)}" y="12" font-size="11" fill="var(--warn)">input price ${fmt(price)}</text></svg>`;
      let page = 0; const size = 100;
      const grid = h("div");
      const draw = () => {
        const from = page * size, part = vals.slice(from, from + size);
        grid.innerHTML = `<div class="tools" style="margin:6px 0"><button class="btn" id="dp" ${page ? "" : "disabled"}>←</button><button class="btn" id="dn" ${from + size >= vals.length ? "disabled" : ""}>→</button><span class="note">scenarios ${from + 1}–${from + part.length} of ${vals.length}</span></div><div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:2px;font-size:12px" class="stat">${part.map((v, i) => `<span style="${heat(v, price)};padding:1px 6px">s${from + i + 1}: ${fmt(v)}</span>`).join("")}</div>`;
        grid.querySelector("#dp").onclick = () => { page--; draw(); };
        grid.querySelector("#dn").onclick = () => { page++; draw(); };
      };
      detail.innerHTML = `<b>${esc(key)}</b> ${statusCell(d.outcomes[0])} <span class="note">price ${fmt(price)} · curve_shift ${d.curve_shift?.[0] ?? "–"}</span><div style="display:flex;gap:24px;flex-wrap:wrap;margin-top:6px">${svg}<div style="flex:1;min-width:300px" id="g"></div></div>`;
      detail.querySelector("#g").append(grid);
      draw();
    }
    load();
    return () => { seq++; };
  },
});
