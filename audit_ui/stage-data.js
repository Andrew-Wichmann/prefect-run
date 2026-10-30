// The stage-output modal on the dashboard: openStageData(run, stage).
// "Table" tab: AG Grid (open-source) with the infinite row model: rows load in blocks as you scroll and the 700
// scenario columns are virtualised; instrument and status stay pinned. "SQL" tab: Monaco editor + DuckDB-WASM on
// the stage's Parquet file, results in AG Grid. Libraries load from a CDN the first time they are needed.
(() => {
  const AG = "32.3.3", MON = "https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min", DUCK = "1.29.0";
  const DEFAULT_SQL = "SELECT * FROM stage LIMIT 25";
  const EXAMPLES = [
    ["first rows", DEFAULT_SQL],
    ["worst scenario per instrument", "SELECT primary_key, any_value(price) AS price, min(v) AS worst,\n       arg_min(scenario, v) AS worst_scenario,\n       round(min(v) / any_value(price) - 1, 4) AS worst_move\nFROM (UNPIVOT stage ON COLUMNS('pricing_scenario_.*') INTO NAME scenario VALUE v)\nGROUP BY primary_key\nORDER BY worst_move\nLIMIT 25"],
    ["scenario averages", "SELECT scenario, round(avg(v / price - 1), 4) AS mean_move,\n       round(min(v / price - 1), 4) AS min_move, round(max(v / price - 1), 4) AS max_move\nFROM (UNPIVOT stage ON COLUMNS('pricing_scenario_.*') INTO NAME scenario VALUE v)\nGROUP BY scenario\nORDER BY mean_move\nLIMIT 25"],
    ["columns", "SELECT column_name, column_type FROM (DESCRIBE stage) LIMIT 20"],
  ];

  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const dark = () => matchMedia("(prefers-color-scheme: dark)").matches;
  function h(tag, attrs = {}, ...kids) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
      else if (v !== false && v != null) e.setAttribute(k, v === true ? "" : v);
    }
    e.append(...kids.flat().filter((k) => k != null));
    return e;
  }
  const loadScript = (src) => new Promise((ok, no) => document.head.append(h("script", { src, onload: ok, onerror: () => no(new Error(`could not load ${src}`)) })));
  let agLoading = null;
  const ensureAgGrid = () => agLoading ||= (async () => {
    for (const f of ["ag-grid", "ag-theme-quartz"]) document.head.append(h("link", { rel: "stylesheet", href: `https://cdn.jsdelivr.net/npm/ag-grid-community@${AG}/styles/${f}.css` }));
    await loadScript(`https://cdn.jsdelivr.net/npm/ag-grid-community@${AG}/dist/ag-grid-community.min.js`);
  })();
  const theme = () => `ag-theme-quartz${dark() ? "-dark" : ""}`;

  window.agGridReady = ensureAgGrid;
  window.agTheme = theme;

  // The SQL to run: the highlighted text if any; otherwise the statement (split on ;) under the cursor.
  function sqlToRun(text, from, to) {
    if (from !== to) return text.slice(Math.min(from, to), Math.max(from, to));
    const parts = [];
    let start = 0, quote = null;
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (quote) { if (c === quote) quote = null; continue; }
      if (c === "'" || c === '"') quote = c;
      else if (c === ";") { parts.push([start, i + 1]); start = i + 1; }
    }
    parts.push([start, text.length + 1]);
    const real = parts.filter(([a, b]) => text.slice(a, b).replace(/;/g, "").trim());
    const hit = real.find(([a, b]) => from >= a && from < b) || [...real].reverse().find(([a]) => a <= from) || real[0];
    return hit ? text.slice(hit[0], hit[1]).replace(/;\s*$/, "") : "";
  }

  function csvDownload(name, header, rows) {
    const q = (v) => v == null ? "" : /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v);
    const blob = new Blob([[header, ...rows].map((r) => r.map(q).join(",")).join("\n")], { type: "text/csv" });
    const a = h("a", { href: URL.createObjectURL(blob), download: name });
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  }

  // ---- SQL tab -------------------------------------------------------------------------------------------------
  async function mountSql(el, api, name, xl) {
    const status = h("div", { class: "sd-note" }, "Loading DuckDB…");
    el.append(status);
    const duckdb = await import(`https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@${DUCK}/+esm`);
    const bundle = await duckdb.selectBundle(duckdb.getJsDelivrBundles());
    const worker = new Worker(URL.createObjectURL(new Blob([`importScripts("${bundle.mainWorker}");`], { type: "text/javascript" })));
    const db = new duckdb.AsyncDuckDB(new duckdb.ConsoleLogger(duckdb.LogLevel.WARNING), worker);
    let ed = null, comp = null, grid = null, gone = false;
    const cleanup = () => { gone = true; worker.terminate(); comp?.dispose(); ed?.dispose(); grid?.destroy(); };
    try {
      await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
      status.textContent = "Downloading the Parquet file…";
      const buf = new Uint8Array(await (await fetch(api("parquet"))).arrayBuffer());
      await db.registerFileBuffer("stage.parquet", buf);
      const conn = await db.connect();
      await conn.query("CREATE VIEW stage AS SELECT * FROM read_parquet('stage.parquet')");
      const columns = (await conn.query("SELECT column_name FROM (DESCRIBE stage)")).toArray().map((r) => r.column_name);
      await ensureAgGrid();
      status.textContent = "Loading the editor…";
      if (!window.monaco) {
        await loadScript(`${MON}/vs/loader.js`);
        window.MonacoEnvironment = { getWorkerUrl: () => URL.createObjectURL(new Blob([`self.MonacoEnvironment={baseUrl:"${MON}/"};importScripts("${MON}/vs/base/worker/workerMain.js");`], { type: "text/javascript" })) };
        require.config({ paths: { vs: `${MON}/vs` } });
        await new Promise((ok) => require(["vs/editor/editor.main"], ok));
      }
      if (gone) return cleanup;

      const editorBox = h("div", { class: "sd-editor" });
      const out = h("div", { style: "flex:1;min-height:0" });
      const info = h("span", { class: "sd-note" }, `${(buf.length / 1e6).toFixed(1)} MB Parquet loaded`);
      const run = h("button", { class: "sd-btn primary", onclick: () => exec() }, "▶ Run selection  (Ctrl/⌘+Enter)");
      const csv = h("button", { class: "sd-btn", disabled: true, title: "CSV opens directly in Excel" }, "⬇ Results (CSV)");
      status.replaceWith(
        h("div", { class: "sd-tools" }, h("span", { class: "sd-note" }, "examples:"), EXAMPLES.map(([t, q]) => h("button", { class: "sd-btn", onclick: () => ed.setValue(q) }, t))),
        editorBox, h("div", { class: "sd-tools" }, run, csv, xl, info), out);

      ed = monaco.editor.create(editorBox, {
        value: DEFAULT_SQL, language: "sql", theme: dark() ? "vs-dark" : "vs", minimap: { enabled: false }, automaticLayout: true,
        fontSize: 13, scrollBeyondLastLine: false, padding: { top: 8 }, renderLineHighlight: "none", overviewRulerLanes: 0,
      });
      ed.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => exec());
      const K = monaco.languages.CompletionItemKind;
      comp = monaco.languages.registerCompletionItemProvider("sql", {
        provideCompletionItems(model, pos) {
          const w = model.getWordUntilPosition(pos), range = { startLineNumber: pos.lineNumber, endLineNumber: pos.lineNumber, startColumn: w.startColumn, endColumn: w.endColumn };
          return { suggestions: [
            { label: "stage", kind: K.Struct, insertText: "stage", range, detail: "this stage's Parquet file" },
            ...["UNPIVOT", "quantile_cont", "arg_min", "arg_max", "any_value", "SUMMARIZE", "DESCRIBE", "COLUMNS('pricing_scenario_.*')"].map((l) => ({ label: l, kind: K.Function, insertText: l, range })),
            ...columns.filter((c) => !c.startsWith("pricing_scenario_") || /_(1|2|700)$/.test(c)).map((c) => ({ label: c, kind: K.Field, insertText: c, range, detail: "column" })),
          ] };
        },
      });

      const cell = (v) => v == null ? "" : typeof v === "number" ? (Number.isInteger(v) ? String(v) : +v.toPrecision(7)) : v instanceof Date ? v.toISOString() : typeof v === "bigint" ? v.toString() : typeof v === "object" ? JSON.stringify(v, (_, x) => typeof x === "bigint" ? x.toString() : x) : v;
      let result = null;
      async function exec() {
        run.disabled = true; info.textContent = "running…";
        const t0 = performance.now();
        try {
          const model = ed.getModel(), sel = ed.getSelection();
          const sql = sqlToRun(model.getValue(), model.getOffsetAt(sel.getStartPosition()), model.getOffsetAt(sel.getEndPosition())).trim();
          if (!sql) throw new Error("Nothing to run: highlight a query, or put the cursor in one.");
          const res = await conn.query(sql);
          const names = res.schema.fields.map((f) => f.name), rows = res.toArray().map((r) => names.map((n) => cell(r[n])));
          result = { names, rows };
          info.textContent = `${rows.length.toLocaleString()} rows × ${names.length} columns in ${(performance.now() - t0).toFixed(0)} ms`;
          csv.disabled = !rows.length;
          grid?.destroy(); out.innerHTML = "";
          const numeric = names.map((_, i) => rows.length && rows.slice(0, 50).every((r) => r[i] === "" || !isNaN(+r[i])));
          grid = agGrid.createGrid(out.appendChild(h("div", { class: theme(), style: "height:100%" })), {
            columnDefs: names.map((n, i) => ({ headerName: n, valueGetter: (p) => p.data[i], sortable: true, resizable: true, filter: true,
              pinned: n === "primary_key" ? "left" : undefined, type: numeric[i] ? "rightAligned" : undefined,
              comparator: numeric[i] ? (a, b) => (a === "" ? -Infinity : +a) - (b === "" ? -Infinity : +b) : undefined })),
            rowData: rows, pagination: rows.length > 100, paginationPageSize: 100, paginationPageSizeSelector: [50, 100, 500],
          });
        } catch (e) { out.innerHTML = `<div class="sd-err">${esc(e.message)}</div>`; info.textContent = "error"; csv.disabled = true; }
        run.disabled = false;
      }
      csv.onclick = () => csvDownload(`${name}-query.csv`, result.names, result.rows);
      exec();
    } catch (e) { status.className = "sd-err"; status.textContent = e.message; }
    return cleanup;
  }

  // ---- the modal -----------------------------------------------------------------------------------------------
  let dlg = null, cleanups = [];
  window.openStageData = async function (run, stage) {
    if (!dlg) {
      dlg = h("dialog", { id: "stagedata" });
      dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); });
      dlg.addEventListener("close", () => { cleanups.forEach((c) => c?.()); cleanups = []; dlg.innerHTML = ""; });
      document.body.append(dlg);
    }
    const api = (path, p = {}) => `api/${path}?` + new URLSearchParams({ run, stage, ...p });
    const meta = h("span", { class: "sd-note" });
    const pane = h("div", { class: "sd-pane" });
    const xl = h("button", { class: "sd-btn", title: "Every instrument and every scenario, as .xlsx", onclick: () => { location.href = api("xlsx"); } }, "⬇ Excel (all)");
    dlg.innerHTML = "";
    dlg.append(
      h("div", { class: "sd-head" }, h("h3", {}, h("code", {}, stage), " output"), meta, h("span", { style: "flex:1" }),
        h("form", { method: "dialog" }, h("button", { "aria-label": "Close", class: "sd-x" }, "✕"))),
      pane);
    if (!dlg.open) dlg.showModal();
    fetch(api("matrix", { row_limit: 1, col_limit: 1 })).then((r) => r.json()).then((info) => {
      meta.textContent = `${info.total_rows.toLocaleString()} instruments × ${info.total_cols.toLocaleString()} scenarios · run ${run.slice(0, 8)}`;
    }).catch(() => {});
    try { cleanups.push(await mountSql(pane, api, stage, xl)); }
    catch (e) { pane.innerHTML = `<div class="sd-err">${esc(e.message)}</div>`; }
  };
})();
