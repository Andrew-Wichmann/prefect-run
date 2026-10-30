// The stage timeline for the job detail page. Three columns (name + icon actions | Gantt | mix and timing) when the
// widget is wide; it reflows by the widget's own width, not the viewport's, to name + actions / Gantt / mix when narrow.
// The actions are small icon buttons with tooltips (rerun from this stage, open in Prefect). Every row is a
// "stage-card" with data-stage, which the page's click handler uses to show that stage's table below.
// (Helpers are in stage-common.js.)
addStyle(`
  .v3 { container-type: inline-size; display: grid; gap: 6px; }
  .v3 .row3 { display: grid; gap: 4px 14px; align-items: center; padding: 6px 8px; border: 1px solid transparent; border-radius: 8px;
    grid-template-columns: minmax(110px, 170px) 1fr minmax(120px, 180px);
    grid-template-areas: "who track facts" "tools track facts"; }
  .v3 .row3.axis3 { grid-template-areas: "who track facts"; padding-top: 0; cursor: default; }
  .v3 .who { grid-area: who; min-width: 0; display: flex; flex-wrap: wrap; align-items: center; gap: 2px 8px; overflow-wrap: anywhere; }
  .v3 .tools { grid-area: tools; display: flex; gap: 4px; }
  .v3 .row3 > .track, .v3 .axis3 > .axisl { grid-area: track; }
  .v3 .facts { grid-area: facts; min-width: 0; }
  .v3 .ico { width: 26px; height: 26px; padding: 0; margin: 0; display: inline-grid; place-items: center; border: 1px solid var(--line);
    border-radius: 6px; background: none; color: inherit; font-size: 14px; line-height: 1; text-decoration: none; cursor: pointer; }
  .v3 .ico:hover { border-color: var(--run); }
  @container (max-width: 640px) {
    .v3 .row3 { grid-template-columns: 1fr auto; grid-template-areas: "who tools" "track track" "facts facts"; }
    .v3 .row3.axis3 { grid-template-areas: "track track"; }
  }
`);

function renderStages(j, stage) {
  const g = stageGeometry(j);
  if (g.empty) return `<p class="muted">${g.empty}</p>`;
  const rows = g.S.map((n) => {
    const t = g.T[n];
    return `<div ${cardAttrs(n, stage, "row3")}>
      <div class="who"><b>${esc(n)}</b>${g.status(n)}</div>
      <div class="tools">${bustButton(j, n, "↻", "ico")}${openLink(t, "↗", "ico")}</div>
      ${g.track(n)}
      <div class="facts">${g.mix(n)}<span class="cnt">${g.took(n)} · usually ${g.usually(n)}</span></div></div>`;
  }).join("");
  return `<div class="v3"><div class="row3 axis3">${g.axis()}</div>${rows}</div>`;
}
