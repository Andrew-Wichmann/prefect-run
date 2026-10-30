// v6: label over bar. Each stage is a heading line (name, status, timing) over a full-width Gantt and status mix.
// The actions are quiet text links on the heading line, shown when you hover or focus the stage or select it
// (always shown on touch screens), so the resting layout is just the chart.
addStyle(`
  .v6 { display: grid; gap: 4px; }
  .v6 .axisl { padding: 0 10px; }
  :where(.v6) .stage-card { display: grid; gap: 6px; padding: 8px 10px; border: 1px solid transparent; border-radius: 8px; }
  .v6 .l1 { display: flex; flex-wrap: wrap; align-items: baseline; gap: 2px 10px; }
  .v6 .l1 b { overflow-wrap: anywhere; }
  .v6 .acts { margin-left: auto; display: flex; flex-wrap: wrap; gap: 2px 12px; font-size: 12px; opacity: 0; transition: opacity .12s; }
  .v6 .stage-card:hover .acts, .v6 .stage-card:focus-within .acts, .v6 .stage-card.selected .acts { opacity: 1; }
  @media (hover: none) { .v6 .acts { opacity: 1; } }
  .v6 .acts :is(a, button) { margin: 0; padding: 0; border: 0; background: none; color: var(--run); font: inherit; text-decoration: underline; cursor: pointer; }
  .v6 .mix { margin: 0; }
`);

function renderStages(j, stage) {
  const g = stageGeometry(j);
  if (g.empty) return `<p class="muted">${g.empty}</p>`;
  const rows = g.S.map((n) => {
    const t = g.T[n];
    return `<div ${cardAttrs(n, stage, "")}>
      <div class="l1"><b>${esc(n)}</b>${g.status(n)}<span class="cnt">${g.took(n)} · usually ${g.usually(n)}</span>
        <span class="acts">${bustButton(j, n, "rerun from here")}${viewButton(t, n, "view data")}${openLink(t, "open in Prefect")}</span></div>
      ${g.track(n)}${g.mix(n)}</div>`;
  }).join("");
  return `<div class="v6">${g.axis()}${rows}</div>`;
}
