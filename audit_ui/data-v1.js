// Baseline: what a plain HTML table does with the whole stage output. Nothing is paged, windowed or virtualised.
registerView({
  n: 1, title: "Baseline (load everything)",
  blurb: "One <table>, every instrument and every scenario at once. Here to show how bad it is. It waits for you to press the button, because the tab can stop responding.",
  mount(el, { meta }) {
    const cells = meta.total_rows * meta.total_cols;
    const log = h("pre", { class: "note", style: "margin:0" });
    const wrap = h("div", { class: "scroll" });
    let dead = false;
    const go = h("button", { class: "btn primary", onclick: run }, `Load all ${n0(cells)} cells`);
    el.append(h("div", { class: "tools" }, go, h("span", { class: "note" }, `${n0(meta.total_rows)} rows × ${n0(meta.total_cols)} scenarios. Expect a very large download, a long parse, and a table of millions of DOM nodes.`), h("span", { class: "sp" }), excelButtons(null)), log, wrap);

    async function run() {
      go.disabled = true;
      const t0 = performance.now(), lines = [];
      const say = (s) => { lines.push(s); log.textContent = lines.join("\n"); };
      say("downloading…");
      const text = await (await fetch(apiUrl("matrix", { row_limit: 0, col_limit: 0 }))).text();
      const t1 = performance.now();
      say(`downloaded ${(text.length / 1e6).toFixed(0)} MB in ${((t1 - t0) / 1000).toFixed(1)} s · parsing…`);
      await new Promise((r) => setTimeout(r));
      const d = JSON.parse(text);
      const t2 = performance.now();
      say(`parsed in ${((t2 - t1) / 1000).toFixed(1)} s · building the table…`);
      await new Promise((r) => setTimeout(r));
      const table = h("table", { class: "dt" });
      table.innerHTML = `<thead><tr><th>instrument</th><th>status</th><th>price</th>${d.scenario_names.map((c) => `<th>${c.replace("pricing_scenario_", "s")}</th>`).join("")}</tr></thead>`;
      const body = h("tbody");
      table.append(body);
      wrap.append(table);
      for (let i = 0; i < d.keys.length && !dead; i += 100) {
        const out = [];
        for (let j = i; j < Math.min(i + 100, d.keys.length); j++) {
          const p = d.price[j];
          out.push(`<tr><td>${esc(d.keys[j])}</td><td>${statusCell(d.outcomes[j])}</td><td>${fmt(p)}</td>${d.values[j].map((v) => `<td style="${heat(v, p)}">${fmt(v)}</td>`).join("")}</tr>`);
        }
        body.insertAdjacentHTML("beforeend", out.join(""));
        say(`parsed in ${((t2 - t1) / 1000).toFixed(1)} s · rendered ${n0(Math.min(i + 100, d.keys.length))} of ${n0(d.keys.length)} rows`);
        await new Promise((r) => setTimeout(r));
      }
      if (!dead) say(`done: ${((performance.now() - t0) / 1000).toFixed(1)} s in total, ${n0(document.getElementsByTagName("*").length)} DOM nodes`);
    }
    return () => { dead = true; };
  },
});
