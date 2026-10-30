// v2: stacked cards. Name, status and timing on one wrapping line; the Gantt and status mix get the full width
// beneath it; the three actions live behind one "⋯" menu, so nothing competes with the chart at any width.
addStyle(`
  .v2 { display: grid; gap: 10px; }
  .v2 .axisl { padding: 0 4px; }
  :where(.v2) .stage-card { display: grid; gap: 8px; padding: 10px 12px; border: 1px solid var(--line); border-radius: 10px; }
  .v2 .head { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 10px; }
  .v2 .head b { overflow-wrap: anywhere; }
  .v2 .head .cnt { margin-left: auto; }
  .v2 details.more { position: relative; }
  .v2 details.more summary { list-style: none; cursor: pointer; padding: 0 10px; border: 1px solid var(--line); border-radius: 6px; line-height: 20px; user-select: none; }
  .v2 details.more summary::-webkit-details-marker { display: none; }
  .v2 .menu { position: absolute; right: 0; top: calc(100% + 4px); z-index: 5; min-width: 190px; display: grid; gap: 2px; padding: 6px;
    background: var(--bg); border: 1px solid var(--line); border-radius: 8px; box-shadow: 0 8px 24px rgb(0 0 0 / .28); }
  .v2 .menu :is(a, button) { display: block; margin: 0; padding: 6px 10px; border: 0; border-radius: 6px; background: none; color: inherit;
    font: inherit; font-size: 13px; text-align: left; text-decoration: none; cursor: pointer; }
  .v2 .menu :is(a, button):hover { background: color-mix(in srgb, var(--run) 14%, transparent); }
`);

function renderStages(j, stage) {
  const g = stageGeometry(j);
  if (g.empty) return `<p class="muted">${g.empty}</p>`;
  const cards = g.S.map((n) => {
    const t = g.T[n];
    const menu = [bustButton(j, n, "Rerun from here"), viewButton(t, n, "View data"), openLink(t, "Open in Prefect")].join("");
    return `<div ${cardAttrs(n, stage, "")}>
      <div class="head"><b>${esc(n)}</b>${g.status(n)}<span class="cnt">${g.took(n)} · usually ${g.usually(n)}</span>
        ${menu ? `<details class="more"><summary aria-label="Actions for ${esc(n)}">⋯</summary><div class="menu">${menu}</div></details>` : ""}</div>
      ${g.track(n)}
      ${g.mix(n)}</div>`;
  }).join("");
  return `<div class="v2">${g.axis()}${cards}</div>`;
}
