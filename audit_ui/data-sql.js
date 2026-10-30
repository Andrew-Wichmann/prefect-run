// A SQL console shared by the editor-component variants: DuckDB-WASM on this stage's Parquet file, an editor
// (Monaco or CodeMirror, supplied by the variant), and AG Grid for the results.
const SQL_EXAMPLES = [
  ["first rows", "SELECT primary_key, price, curve_shift, pricing_scenario_1, pricing_scenario_2\nFROM stage\nLIMIT 20"],
  ["worst scenario per instrument", "SELECT primary_key, any_value(price) AS price, min(v) AS worst,\n       arg_min(scenario, v) AS worst_scenario,\n       round(min(v) / any_value(price) - 1, 4) AS worst_move\nFROM (UNPIVOT stage ON COLUMNS('pricing_scenario_.*') INTO NAME scenario VALUE v)\nGROUP BY primary_key\nORDER BY worst_move\nLIMIT 25"],
  ["scenario averages", "SELECT scenario, round(avg(v / price - 1), 4) AS mean_move,\n       round(min(v / price - 1), 4) AS min_move, round(max(v / price - 1), 4) AS max_move\nFROM (UNPIVOT stage ON COLUMNS('pricing_scenario_.*') INTO NAME scenario VALUE v)\nGROUP BY scenario\nORDER BY mean_move\nLIMIT 25"],
  ["columns", "SELECT column_name, column_type FROM (DESCRIBE stage) LIMIT 20"],
];

// The SQL to run: the highlighted text if any is selected; otherwise the statement (split on ;) under the cursor.
function sqlToRun(text, from, to) {
  if (from !== to) return text.slice(Math.min(from, to), Math.max(from, to));
  const parts = [];  // [start, end) of each statement, the ; ending it included in the span but not the text
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

// makeEditor(box, { value, run, columns }) -> { getQuery(), setValue(v), dispose() }, may be async.
// getQuery() is what Ctrl/⌘+Enter runs: the selection, else the statement at the cursor.
async function sqlConsole(el, makeEditor) {
  const status = h("div", { class: "note" }, "Loading DuckDB…");
  el.append(status);
  const duckdb = await import("https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@1.29.0/+esm");
  const bundle = await duckdb.selectBundle(duckdb.getJsDelivrBundles());
  const worker = new Worker(URL.createObjectURL(new Blob([`importScripts("${bundle.mainWorker}");`], { type: "text/javascript" })));
  const db = new duckdb.AsyncDuckDB(new duckdb.ConsoleLogger(duckdb.LogLevel.WARNING), worker);
  await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
  status.textContent = "Downloading the Parquet file…";
  const buf = new Uint8Array(await (await fetch(apiUrl("parquet"))).arrayBuffer());
  await db.registerFileBuffer("stage.parquet", buf);
  const conn = await db.connect();
  await conn.query("CREATE VIEW stage AS SELECT * FROM read_parquet('stage.parquet')");
  const columns = (await conn.query("SELECT column_name FROM (DESCRIBE stage)")).toArray().map((r) => r.column_name);
  await ensureAgGrid();
  status.textContent = "Loading the editor…";

  const editorBox = h("div", { style: "height:160px;flex:none;border:1px solid var(--line);border-radius:8px;overflow:hidden" });
  const out = h("div", { style: "flex:1;min-height:200px" });
  const info = h("span", { class: "note" }, `${(buf.length / 1e6).toFixed(1)} MB Parquet loaded`);
  const run = h("button", { class: "btn primary", onclick: exec }, "▶ Run selection  (Ctrl/⌘+Enter)");
  const csv = h("button", { class: "btn", disabled: true, title: "CSV opens directly in Excel" }, "⬇ Results (CSV for Excel)");
  el.append(h("div", { class: "tools" }, h("span", { class: "note" }, "examples:"), SQL_EXAMPLES.map(([t, q]) => h("button", { class: "btn", onclick: () => editor.setValue(q) }, t))),
    editorBox, h("div", { class: "tools" }, run, csv, info, h("span", { class: "sp" }), excelButtons(null)), out);
  const editor = await makeEditor(editorBox, { value: SQL_EXAMPLES[1][1], run: () => exec(), columns });
  status.remove();

  const cell = (v) => v == null ? "" : typeof v === "number" ? (Number.isInteger(v) ? String(v) : +v.toPrecision(7)) : v instanceof Date ? v.toISOString() : typeof v === "bigint" ? v.toString() : typeof v === "object" ? JSON.stringify(v, (_, x) => typeof x === "bigint" ? x.toString() : x) : v;
  let result = null, grid = null;
  async function exec() {
    run.disabled = true; info.textContent = "running…";
    const t0 = performance.now();
    try {
      const sql = editor.getQuery().trim();
      if (!sql) throw new Error("Nothing to run: highlight a query, or put the cursor in one.");
      const res = await conn.query(sql);
      const names = res.schema.fields.map((f) => f.name), rows = res.toArray().map((r) => names.map((n) => cell(r[n])));
      result = { names, rows };
      info.textContent = `${n0(rows.length)} rows × ${names.length} columns in ${(performance.now() - t0).toFixed(0)} ms`;
      csv.disabled = !rows.length;
      grid?.destroy(); out.innerHTML = "";
      const numeric = names.map((_, i) => rows.length && rows.slice(0, 50).every((r) => r[i] === "" || !isNaN(+r[i])));
      grid = agGrid.createGrid(out.appendChild(h("div", { class: `ag-theme-quartz${darkMode() ? "-dark" : ""}`, style: "height:100%" })), {
        columnDefs: names.map((n, i) => ({ headerName: n, valueGetter: (p) => p.data[i], sortable: true, resizable: true, filter: true, type: numeric[i] ? "rightAligned" : undefined,
          comparator: numeric[i] ? (a, b) => (a === "" ? -Infinity : +a) - (b === "" ? -Infinity : +b) : undefined })),
        rowData: rows, pagination: rows.length > 100, paginationPageSize: 100, paginationPageSizeSelector: [50, 100, 500],
      });
    } catch (e) { out.innerHTML = `<div class="err">${esc(e.message)}</div>`; info.textContent = "error"; csv.disabled = true; }
    run.disabled = false;
  }
  csv.onclick = () => csvDownload(`${STAGE}-query.csv`, result.names, result.rows);
  exec();
  return () => { worker.terminate(); editor.dispose(); grid?.destroy(); };
}
