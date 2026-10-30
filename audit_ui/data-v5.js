// Hand-built virtual grid on a canvas: the scroll bars cover the whole 10,000 × 700 table, but only the cells in view
// are drawn, and each block of 100 rows × 50 scenarios is fetched the first time you scroll near it. Nothing to page.
registerView({
  n: 5, title: "Virtual canvas grid",
  blurb: "Scroll the whole table in both directions like a spreadsheet. Blocks of 100 × 50 cells are fetched as they come into view and the oldest are dropped. No dependencies.",
  mount(el, { meta }) {
    const ROW_H = 24, COL_W = 84, HEAD_H = 26, KEY_W = 110, PRICE_W = 70, FROZEN = KEY_W + PRICE_W, BR = 100, BC = 50, MAX_BLOCKS = 60;
    const blocks = new Map(), rowInfo = new Map(), pending = new Set();
    const info = h("span", { class: "note" });
    const canvas = h("canvas", { style: "position:sticky;top:0;left:0;display:block" });
    const space = h("div", { style: `position:relative;width:${FROZEN + meta.total_cols * COL_W}px;height:${HEAD_H + meta.total_rows * ROW_H}px` }, canvas);
    const box = h("div", { class: "scroll", tabindex: 0 }, space);
    let view = { r0: 0, r1: 0, c0: 0, c1: 0 }, raf = 0, dead = false;
    el.append(h("div", { class: "tools" }, info, h("span", { class: "sp" }),
      excelButtons(() => ({ row_offset: view.r0, row_limit: view.r1 - view.r0 + 1, col_offset: view.c0, col_limit: view.c1 - view.c0 + 1 }))), box);

    const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
    function request(rb, cb) {
      const id = `${rb},${cb}`;
      if (blocks.has(id) || pending.has(id)) return;
      pending.add(id);
      getJSON("matrix", { row_offset: rb * BR, row_limit: BR, col_offset: cb * BC, col_limit: BC }).then((d) => {
        pending.delete(id);
        blocks.set(id, d.values);
        rowInfo.set(rb, { keys: d.keys, price: d.price, outcomes: d.outcomes });
        while (blocks.size > MAX_BLOCKS) blocks.delete(blocks.keys().next().value);
        schedule();
      }).catch(() => pending.delete(id));
    }
    const schedule = () => { if (!raf && !dead) raf = requestAnimationFrame(() => { raf = 0; draw(); }); };

    function draw() {
      const dpr = devicePixelRatio || 1, W = box.clientWidth, H = box.clientHeight;
      if (canvas.width !== Math.round(W * dpr) || canvas.height !== Math.round(H * dpr)) {
        canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
        canvas.style.width = `${W}px`; canvas.style.height = `${H}px`;
      }
      const g = canvas.getContext("2d");
      g.setTransform(dpr, 0, 0, dpr, 0, 0);
      const bg = css("--bg"), fg = css("--fg"), muted = css("--muted"), line = css("--line");
      g.clearRect(0, 0, W, H);
      g.fillStyle = bg; g.fillRect(0, 0, W, H);
      g.font = "12px system-ui, sans-serif"; g.textBaseline = "middle";
      const sx = box.scrollLeft, sy = box.scrollTop;
      const r0 = Math.floor(sy / ROW_H), r1 = Math.min(meta.total_rows - 1, Math.ceil((sy + H - HEAD_H) / ROW_H));
      const c0 = Math.floor(sx / COL_W), c1 = Math.min(meta.total_cols - 1, Math.ceil((sx + W - FROZEN) / COL_W));
      view = { r0, r1, c0, c1 };
      info.textContent = `rows ${n0(r0 + 1)}–${n0(r1 + 1)} of ${n0(meta.total_rows)} · scenarios ${c0 + 1}–${c1 + 1} of ${meta.total_cols}${pending.size ? " · loading…" : ""}`;
      // scenario cells
      g.save(); g.beginPath(); g.rect(FROZEN, HEAD_H, W - FROZEN, H - HEAD_H); g.clip();
      g.textAlign = "right";
      for (let r = r0; r <= r1; r++) {
        const y = HEAD_H + r * ROW_H - sy, ri = rowInfo.get(Math.floor(r / BR));
        const price = ri?.price[r % BR];
        for (let c = c0; c <= c1; c++) {
          const x = FROZEN + c * COL_W - sx, id = `${Math.floor(r / BR)},${Math.floor(c / BC)}`, b = blocks.get(id);
          if (!b) { request(Math.floor(r / BR), Math.floor(c / BC)); g.fillStyle = line; g.fillRect(x + 6, y + 9, COL_W - 14, 6); continue; }
          const v = b[r % BR]?.[c % BC];
          if (v == null) continue;
          if (price) {
            const m = v / price - 1, a = Math.min(Math.abs(m) / 0.3, 1) * 0.5;
            g.fillStyle = m < 0 ? `rgba(220,38,38,${a})` : `rgba(22,163,74,${a})`; g.fillRect(x, y, COL_W, ROW_H);
          }
          g.fillStyle = fg; g.fillText(v.toFixed(2), x + COL_W - 8, y + ROW_H / 2);
        }
        g.fillStyle = line; g.fillRect(FROZEN, y + ROW_H - 1, W - FROZEN, 1);
      }
      g.restore();
      // frozen key + price columns
      g.fillStyle = bg; g.fillRect(0, HEAD_H, FROZEN, H - HEAD_H);
      for (let r = r0; r <= r1; r++) {
        const y = HEAD_H + r * ROW_H - sy, ri = rowInfo.get(Math.floor(r / BR)), i = r % BR;
        g.fillStyle = fg; g.textAlign = "left";
        g.fillText(ri ? ri.keys[i] ?? "" : "…", 8, y + ROW_H / 2);
        g.textAlign = "right"; g.fillText(ri?.price[i] != null ? ri.price[i].toFixed(2) : "", FROZEN - 8, y + ROW_H / 2);
        g.fillStyle = line; g.fillRect(0, y + ROW_H - 1, FROZEN, 1);
      }
      g.fillStyle = line; g.fillRect(FROZEN - 1, HEAD_H, 1, H - HEAD_H);
      // header
      g.fillStyle = bg; g.fillRect(0, 0, W, HEAD_H);
      g.fillStyle = muted; g.textAlign = "left"; g.fillText("instrument", 8, HEAD_H / 2);
      g.textAlign = "right"; g.fillText("price", FROZEN - 8, HEAD_H / 2);
      g.save(); g.beginPath(); g.rect(FROZEN, 0, W - FROZEN, HEAD_H); g.clip();
      for (let c = c0; c <= c1; c++) g.fillText(`scenario ${c + 1}`, FROZEN + c * COL_W - sx + COL_W - 8, HEAD_H / 2);
      g.restore();
      g.fillStyle = line; g.fillRect(0, HEAD_H - 1, W, 1);
    }
    box.addEventListener("scroll", schedule, { passive: true });
    const ro = new ResizeObserver(schedule); ro.observe(box);
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", schedule);
    schedule();
    return () => { dead = true; ro.disconnect(); };
  },
});
