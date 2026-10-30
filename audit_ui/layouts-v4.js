// v4: accordion. Each stage is one quiet line (name, status, Gantt, time); selecting a stage opens a panel under it
// with the actions, the status mix and the timing detail, so the details only take space for the stage you are on.
window.rerenderOnSelect = true;
addStyle(`
  .v4 { container-type: inline-size; display: grid; gap: 4px; }
  .v4 .r4 { display: grid; grid-template-columns: minmax(90px, 170px) 1fr 64px; gap: 4px 14px; align-items: center; }
  .v4 .r4 .nm { min-width: 0; display: flex; flex-wrap: wrap; align-items: center; gap: 2px 8px; overflow-wrap: anywhere; }
  .v4 .r4 .t { text-align: right; }
  :where(.v4) .stage-card { padding: 6px 8px; border: 1px solid transparent; border-radius: 8px; }
  .v4 .axis4 { padding: 0 8px; display: grid; grid-template-columns: minmax(90px, 170px) 1fr 64px; gap: 14px; }
  .v4 .axis4 .axisl { grid-column: 2; }
  .v4 .panel { display: grid; gap: 8px; margin-top: 8px; padding-top: 8px; border-top: 1px dashed var(--line); }
  .v4 .acts { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 4px; }
  @container (max-width: 520px) {
    .v4 .r4 { grid-template-columns: 1fr auto; }
    .v4 .r4 .track { grid-column: 1 / -1; grid-row: 2; }
    .v4 .axis4 { grid-template-columns: 1fr; }
    .v4 .axis4 .axisl { grid-column: 1; }
  }
`);

function renderStages(j, stage) {
  const g = stageGeometry(j);
  if (g.empty) return `<p class="muted">${g.empty}</p>`;
  const rows = g.S.map((n) => {
    const t = g.T[n];
    const panel = n !== stage ? "" : `<div class="panel">
      <div class="acts">${bustButton(j, n)}${viewButton(t, n)}${openLink(t, "Open in Prefect")}</div>
      ${g.mix(n)}<span class="cnt">took ${g.took(n)} · usually ${g.usually(n)}</span></div>`;
    return `<div ${cardAttrs(n, stage, "")}>
      <div class="r4"><div class="nm"><b>${esc(n)}</b>${g.status(n)}</div>${g.track(n)}<span class="cnt t">${g.took(n)}</span></div>${panel}</div>`;
  }).join("");
  return `<div class="v4"><div class="axis4">${g.axis()}</div>${rows}</div>`;
}
