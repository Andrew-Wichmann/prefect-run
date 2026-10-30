// v5: one toolbar. The rows are just name, status and Gantt (with a thin status mix under each bar); the actions
// exist once, in a toolbar above the chart that acts on whichever stage is selected, instead of three per row.
window.rerenderOnSelect = true;
addStyle(`
  .v5 { container-type: inline-size; display: grid; gap: 8px; }
  .v5 .tb { display: grid; gap: 6px; padding: 10px 12px; border: 1px solid var(--line); border-radius: 10px; }
  .v5 .tb .line { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 10px; }
  .v5 .tb .acts { margin-left: auto; display: flex; flex-wrap: wrap; align-items: center; gap: 6px 4px; }
  .v5 .r5 { display: grid; grid-template-columns: minmax(80px, 140px) 1fr; gap: 4px 14px; align-items: center; }
  .v5 .r5 .nm { min-width: 0; display: flex; flex-wrap: wrap; align-items: center; gap: 2px 8px; overflow-wrap: anywhere; }
  .v5 .r5 .mix { margin: 3px 0 0; height: 4px; }
  :where(.v5) .stage-card { padding: 6px 8px; border: 1px solid transparent; border-radius: 8px; }
  .v5 .axis5 { display: grid; grid-template-columns: minmax(80px, 140px) 1fr; gap: 14px; padding: 0 8px; }
  .v5 .axis5 .axisl { grid-column: 2; }
  @container (max-width: 480px) {
    .v5 .r5, .v5 .axis5 { grid-template-columns: 1fr; }
    .v5 .axis5 .axisl { grid-column: 1; }
  }
`);

function renderStages(j, stage) {
  const g = stageGeometry(j);
  if (g.empty) return `<p class="muted">${g.empty}</p>`;
  const t = stage && g.T[stage];
  const bar = !g.S.includes(stage) ? `<div class="tb"><span class="muted">Select a stage to rerun from it, view its data or open it in Prefect.</span></div>` : `<div class="tb">
      <div class="line"><b>${esc(stage)}</b>${g.status(stage)}<span class="cnt">took ${g.took(stage)} · usually ${g.usually(stage)}</span>
        <span class="acts">${bustButton(j, stage)}${viewButton(t, stage)}${openLink(t, "Open in Prefect")}</span></div>
      ${g.mix(stage)}</div>`;
  const rows = g.S.map((n) => `<div ${cardAttrs(n, stage, "")}>
      <div class="r5"><div class="nm"><b>${esc(n)}</b>${g.status(n)}</div><div>${g.track(n)}${g.mix(n)}</div></div></div>`).join("");
  return `<div class="v5">${bar}<div class="axis5">${g.axis()}</div>${rows}</div>`;
}
