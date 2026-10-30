// DuckDB's own browser shell (the REPL behind shell.duckdb.org, @duckdb/duckdb-wasm-shell) pointed at this stage's
// Parquet file. DuckDB runs in the browser; the file is downloaded once and exposed as the table `stage`.
registerView({
  n: 7, title: "SQL shell (DuckDB)",
  blurb: "DuckDB's own terminal shell, running in your browser against this stage's Parquet file (table: stage). Dot-commands work: .help, .tables, .maxrows, .timer on.",
  async mount(el) {
    const VER = "1.33.1-dev57.0";
    const EXAMPLES = [
      ["first rows", "SELECT primary_key, price, curve_shift, pricing_scenario_1, pricing_scenario_2 FROM stage LIMIT 20;"],
      ["worst scenario per instrument", "SELECT primary_key, any_value(price) AS price, min(v) AS worst, arg_min(scenario, v) AS worst_scenario, round(min(v) / any_value(price) - 1, 4) AS worst_move FROM (UNPIVOT stage ON COLUMNS('pricing_scenario_.*') INTO NAME scenario VALUE v) GROUP BY primary_key ORDER BY worst_move LIMIT 25;"],
      ["scenario averages", "SELECT scenario, round(avg(v / price - 1), 4) AS mean_move, round(min(v / price - 1), 4) AS min_move, round(max(v / price - 1), 4) AS max_move FROM (UNPIVOT stage ON COLUMNS('pricing_scenario_.*') INTO NAME scenario VALUE v) GROUP BY scenario ORDER BY mean_move LIMIT 25;"],
      ["summarize", "SUMMARIZE SELECT primary_key, price, curve_shift, pricing_scenario_1 FROM stage;"],
    ];
    const copied = h("span", { class: "note" });
    const term = h("div", { style: "flex:1;min-height:300px;border-radius:8px;overflow:hidden" });
    el.append(
      h("div", { class: "tools" }, h("span", { class: "note" }, "copy an example, then paste it into the shell:"),
        EXAMPLES.map(([t, q]) => h("button", { class: "btn", onclick: async () => { await navigator.clipboard.writeText(q); copied.textContent = `copied “${t}”`; } }, t)),
        copied, h("span", { class: "sp" }), excelButtons(null)),
      term);
    loadCss("https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css");
    const [duckdb, shell] = await Promise.all([
      import(`https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@${VER}/+esm`),
      import(`https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm-shell@${VER}/+esm`),
    ]);
    const cs = getComputedStyle(document.body);
    let worker;
    await shell.embed({
      shellModule: new URL(`https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm-shell@${VER}/dist/shell_bg.wasm`),
      container: term,
      fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
      backgroundColor: cs.backgroundColor,
      resolveDatabase: async (progress) => {
        const bundle = await duckdb.selectBundle(duckdb.getJsDelivrBundles());
        worker = new Worker(URL.createObjectURL(new Blob([`importScripts("${bundle.mainWorker}");`], { type: "text/javascript" })));
        const db = new duckdb.AsyncDuckDB(new duckdb.ConsoleLogger(duckdb.LogLevel.WARNING), worker);
        await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
        // Download the Parquet file with progress, then expose it as `stage`.
        const res = await fetch(apiUrl("parquet")), total = +res.headers.get("content-length") || 0, parts = [];
        let got = 0;
        const reader = res.body.getReader();
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          parts.push(value); got += value.length;
          progress({ bytesLoaded: got, bytesTotal: total });
        }
        const buf = new Uint8Array(got);
        let at = 0;
        for (const p of parts) { buf.set(p, at); at += p.length; }
        await db.registerFileBuffer("stage.parquet", buf);
        const conn = await db.connect();
        await conn.query("CREATE VIEW stage AS SELECT * FROM read_parquet('stage.parquet')");
        await conn.close();
        return db;
      },
    });
    return () => { worker?.terminate(); };
  },
});
