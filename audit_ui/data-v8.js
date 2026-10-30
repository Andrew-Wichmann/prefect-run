// Monaco, the editor from VS Code (MIT, from a CDN), as the SQL editor. Results in AG Grid.
registerView({
  n: 8, title: "SQL editor: Monaco",
  blurb: "Monaco (VS Code's editor) for writing SQL with highlighting and column-name completion, DuckDB-WASM to run it against the Parquet file, AG Grid for the results.",
  mount: (el) => sqlConsole(el, async (box, { value, run, columns }) => {
    const MON = "https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min";
    if (!window.monaco) {
      await loadScript(`${MON}/vs/loader.js`);
      window.MonacoEnvironment = { getWorkerUrl: () => URL.createObjectURL(new Blob([`self.MonacoEnvironment={baseUrl:"${MON}/"};importScripts("${MON}/vs/base/worker/workerMain.js");`], { type: "text/javascript" })) };
      require.config({ paths: { vs: `${MON}/vs` } });
      await new Promise((ok) => require(["vs/editor/editor.main"], ok));
    }
    const ed = monaco.editor.create(box, {
      value, language: "sql", theme: darkMode() ? "vs-dark" : "vs", minimap: { enabled: false }, automaticLayout: true,
      fontSize: 13, scrollBeyondLastLine: false, padding: { top: 8 }, renderLineHighlight: "none", overviewRulerLanes: 0,
    });
    ed.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, run);
    const K = monaco.languages.CompletionItemKind;
    const comp = monaco.languages.registerCompletionItemProvider("sql", {
      provideCompletionItems(model, pos) {
        const w = model.getWordUntilPosition(pos), range = { startLineNumber: pos.lineNumber, endLineNumber: pos.lineNumber, startColumn: w.startColumn, endColumn: w.endColumn };
        return { suggestions: [
          { label: "stage", kind: K.Struct, insertText: "stage", range, detail: "this stage's Parquet file" },
          ...["UNPIVOT", "quantile_cont", "arg_min", "arg_max", "any_value", "SUMMARIZE", "DESCRIBE", "COLUMNS('pricing_scenario_.*')"].map((l) => ({ label: l, kind: K.Function, insertText: l, range })),
          ...columns.filter((c) => !c.startsWith("pricing_scenario_") || /_(1|2|700)$/.test(c)).map((c) => ({ label: c, kind: K.Field, insertText: c, range, detail: "column" })),
        ] };
      },
    });
    return { getQuery: () => { const model = ed.getModel(), sel = ed.getSelection(); return sqlToRun(model.getValue(), model.getOffsetAt(sel.getStartPosition()), model.getOffsetAt(sel.getEndPosition())); }, setValue: (v) => ed.setValue(v), dispose: () => { comp.dispose(); ed.dispose(); } };
  }),
});
