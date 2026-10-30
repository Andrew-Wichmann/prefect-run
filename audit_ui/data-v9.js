// CodeMirror 6 with its SQL language package (@codemirror/lang-sql, MIT), bundled into codemirror-sql.js, as the SQL editor.
// A lighter editor than Monaco; completion is schema-aware, so it knows the table `stage` and its columns.
registerView({
  n: 9, title: "SQL editor: CodeMirror",
  blurb: "CodeMirror 6 with @codemirror/lang-sql: SQL highlighting, and completion that knows the table (stage) and its columns. DuckDB-WASM runs the query; AG Grid shows the results.",
  mount: (el) => sqlConsole(el, async (box, { value, run, columns }) => {
    const { EditorView, basicSetup, sql, PostgreSQL, oneDark } = await import("./codemirror-sql.js");
    const view = new EditorView({
      parent: box, doc: value,
      extensions: [
        basicSetup,
        sql({ dialect: PostgreSQL, upperCaseKeywords: true, schema: { stage: columns.filter((c) => !c.startsWith("pricing_scenario_") || /_(1|2|700)$/.test(c)) }, defaultTable: "stage" }),
        EditorView.theme({ "&": { height: "100%", fontSize: "13px" }, ".cm-scroller": { overflow: "auto", fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace" } }),
        ...(darkMode() ? [oneDark] : []),
      ],
    });
    // Ctrl/⌘+Enter, ahead of the editor's own Enter handling (capture phase).
    box.addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); e.stopPropagation(); run(); } }, true);
    return {
      getQuery: () => { const r = view.state.selection.main; return sqlToRun(view.state.doc.toString(), r.anchor, r.head); },
      setValue: (v) => view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: v } }),
      dispose: () => view.destroy(),
    };
  }),
});
