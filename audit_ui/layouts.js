// Stage timeline for the job detail page.

const secs = (s) => s == null ? "–" : `${s.toFixed(1)} s`;
const totalOf = (counts) => Object.values(counts || {}).reduce((a, b) => a + b, 0);

// Instruments in each status at a stage, as one segmented bar scaled to `base` (the instruments the job
// started with), so rows filtered out by earlier stages show as empty track on the left; failed sits leftmost
// of the live segments, so the filled part shrinks from the left as the stages go down the timeline.
function statusMix(counts, base) {
  const total = totalOf(counts);
  base = Math.max(base || 0, total);
  const segs = [...STATUSES].sort((a, b) => (b === "failed") - (a === "failed")).filter((s) => counts && counts[s]).map((s) =>
    `<span class="seg ${s}" style="flex:${counts[s]}" title="${s}: ${counts[s]} of ${total} (${(100 * counts[s] / total).toFixed(1)}%)"></span>`);
  if (base > total) segs.unshift(`<span style="flex:${base - total}" title="${base - total} of ${base} no longer in the pipeline"></span>`);
  return `<div class="mix" role="img" aria-label="${total} of ${base} instruments">${segs.join("")}</div>`;
}

// Prefect's "run from deployment" page, prefilled with this run's parameters and the cache busted from `stage`.
// The Prefect UI expects the JSON URL-encoded once inside the query value, which the router then encodes again.
const bustLink = (j, stage) => {
  if (!j.deployment_id) return "";
  const params = encodeURIComponent(JSON.stringify({ ...j.parameters, bust_cache_from: stage }));
  return `<a class="bust" href="/prefect/deployments/deployment/${j.deployment_id}/run?parameters=${encodeURIComponent(params)}" target="_blank" rel="noopener" title="Open a new run in Prefect with the cache busted from ${esc(stage)} (it and everything after it rerun)">rerun from here ↗</a>`;
};

const cardAttrs = (n, stage, cls) =>
  `class="stage-card ${cls} ${n === stage ? "selected" : ""}" role="button" tabindex="0" data-stage="${esc(n)}"`;

// Stages placed on this run's clock; the dashed outline is where the stage usually ran, and for how long.
// Every row is a "stage-card" with data-stage, which the page's click handler uses.
// (esc and STATUSES come from the page's own script.)
function renderStages(j, stage) {
  if (!j.stages.length) return `<p class="muted">No stages declared</p>`;
  const S = j.stages, T = j.stage_times, B = j.stage_baseline;
  const now = Date.now();
  const starts = S.map((n) => T[n]?.start_time).filter(Boolean).map((t) => +new Date(t));
  if (!starts.length) return `<p class="muted">No stage has started yet</p>`;
  const t0 = Math.min(...starts);
  const h0 = Math.min(...S.map((n) => B[n]?.start_s ?? Infinity));  // anchor history to this run's first start
  const ghostSpan = (b) => [t0 + (b.start_s - h0) * 1000, t0 + (b.start_s - h0 + b.duration_s) * 1000];
  // The axis covers the run and where the stages usually ran, so neither can overflow the track.
  const t1 = Math.max(
    ...S.map((n) => T[n]?.start_time ? +new Date(T[n].end_time || now) : 0),
    ...S.filter((n) => B[n]).map((n) => ghostSpan(B[n])[1]),
  );
  const span = Math.max(t1 - t0, 1);
  const runSpan = Math.max(...S.map((n) => T[n]?.start_time ? +new Date(T[n].end_time || now) : 0)) - t0;  // this run only, not the history
  const pct = (ms) => `${(100 * (ms - t0) / span).toFixed(2)}%`;
  const w = (ms) => `${Math.min(100, 100 * ms / span).toFixed(2)}%`;
  const base = Math.max(...S.map((n) => totalOf(j.stage_counts[n])));  // the most instruments any stage saw
  // Where the job's duration SLA falls on the run's clock (the run's first start + the allowed seconds).
  const lim = t0 + j.duration_sla.max_seconds * 1000;
  const limit = lim <= t1 ? `<div class="limit" style="left:${pct(lim)}" title="Duration SLA: ${j.duration_sla.max_seconds} s"></div>` : "";
  const rows = S.map((n) => {
    const t = T[n], b = B[n];
    const s = t?.start_time ? +new Date(t.start_time) : null, e = t?.start_time ? +new Date(t.end_time || now) : null;
    const ghost = b ? `<div class="ghost" style="left:${pct(t0 + (b.start_s - h0) * 1000)};width:${w(b.duration_s * 1000)}"></div>` : "";
    const bar = s == null ? "" : `<div class="bar" style="left:${pct(s)};width:${w(e - s)}" title="${secs((e - s) / 1000)}"></div>`;
    return `<div ${cardAttrs(n, stage, "grow")}>
      <div><b>${esc(n)}</b><br>${t ? pill(t.status, t.status_type) : `<span class="muted">–</span>`} ${t?.id ? `<a class="tlink" href="/prefect/runs/task-run/${t.id}">Open in Prefect</a>` : ""} ${bustLink(j, n)} ${t ? `<button class="snap" data-stage="${esc(n)}" title="Inspect this stage's output table">view data</button>` : ""}</div>
      <div class="track">${ghost}${bar}${limit}</div>
      <div>${statusMix(j.stage_counts[n], base)}<span class="cnt">${t?.end_time ? secs(t.duration_s) : t ? "running…" : "–"} · historical ${b ? secs(b.duration_s) : "–"}</span></div></div>`;
  }).join("");
  return `<div class="gantt"><div class="grow axis"><span></span><div class="axisl"><span>${fmtTime(t0)}</span><span>${secs(runSpan / 1000)} total</span><span>${fmtTime(t1)}</span></div><span></span></div>${rows}</div>`;
}
