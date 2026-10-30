// v1, the original stage timeline for the job detail page: name and actions on the left, the Gantt in the
// middle, the status mix on the right. Every row is a "stage-card" with data-stage, which the page's click
// handler uses. (Helpers are in stage-common.js.)
function renderStages(j, stage) {
  const g = stageGeometry(j);
  if (g.empty) return `<p class="muted">${g.empty}</p>`;
  const rows = g.S.map((n) => {
    const t = g.T[n];
    return `<div ${cardAttrs(n, stage, "grow")}>
      <div><b>${esc(n)}</b><br>${g.status(n)} ${openLink(t, "Open in Prefect")} ${bustButton(j, n)} ${viewButton(t, n)}</div>
      ${g.track(n)}
      <div>${g.mix(n)}<span class="cnt">${g.took(n)} · historical ${g.usually(n)}</span></div></div>`;
  }).join("");
  return `<div class="gantt"><div class="grow axis"><span></span>${g.axis()}<span></span></div>${rows}</div>`;
}
