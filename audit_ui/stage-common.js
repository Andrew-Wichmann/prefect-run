// Pieces the stage timeline (layouts.js) is built from.
// (esc, pill, fmtTime and STATUSES come from the page's own script.)

const secs = (s) => s == null ? "–" : `${s.toFixed(1)} s`;
const totalOf = (counts) => Object.values(counts || {}).reduce((a, b) => a + b, 0);

function addStyle(css) {
  document.head.append(Object.assign(document.createElement("style"), { textContent: css }));
}

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

// What you can do to a stage. The page's click handler recognises them by class (bust, tlink).
// `label` is the visible text (an icon in the compact layouts); `tip` explains it.
const bustButton = (j, stage, label = "rerun from here", cls = "") => !j.deployment_id ? "" :
  `<button class="bust ${cls}" data-label="${esc(label)}" data-deployment="${esc(j.deployment_id)}" data-params="${esc(JSON.stringify({ ...j.parameters, bust_cache_from: stage }))}" title="Start a new run with the cache busted from ${esc(stage)} (it and everything after it rerun)" aria-label="Rerun from ${esc(stage)}">${label}</button>`;
const openLink = (t, label = "Open in Prefect", cls = "") => !t?.id ? "" :
  `<a class="tlink ${cls}" href="/prefect/runs/task-run/${t.id}" title="Open this task run in Prefect" aria-label="Open ${esc(t.name || "stage")} in Prefect">${label}</a>`;

const cardAttrs = (n, stage, cls) =>
  `class="stage-card ${cls} ${n === stage ? "selected" : ""}" role="button" tabindex="0" data-stage="${esc(n)}"`;

// Stages placed on this run's clock; the dashed outline is where the stage usually ran, and for how long.
// Returns null (and `empty`, a message) when there is nothing to draw; otherwise the pieces a layout assembles.
function stageGeometry(j) {
  const S = j.stages, T = j.stage_times, B = j.stage_baseline;
  if (!S.length) return { empty: "No stages declared" };
  const now = Date.now();
  const starts = S.map((n) => T[n]?.start_time).filter(Boolean).map((t) => +new Date(t));
  if (!starts.length) return { empty: "No stage has started yet" };
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
  return {
    j, S, T, B, base,
    axis: () => `<div class="axisl"><span>${fmtTime(t0)}</span><span>${secs(runSpan / 1000)} total</span><span>${fmtTime(t1)}</span></div>`,
    track(n) {
      const t = T[n], b = B[n];
      const s = t?.start_time ? +new Date(t.start_time) : null, e = t?.start_time ? +new Date(t.end_time || now) : null;
      const ghost = b ? `<div class="ghost" style="left:${pct(t0 + (b.start_s - h0) * 1000)};width:${w(b.duration_s * 1000)}"></div>` : "";
      const bar = s == null ? "" : `<div class="bar" style="left:${pct(s)};width:${w(e - s)}" title="${secs((e - s) / 1000)}"></div>`;
      return `<div class="track">${ghost}${bar}${limit}</div>`;
    },
    mix: (n) => statusMix(j.stage_counts[n], base),
    took: (n) => T[n]?.end_time ? secs(T[n].duration_s) : T[n] ? "running…" : "–",
    usually: (n) => B[n] ? secs(B[n].duration_s) : "–",
    status: (n) => T[n] ? pill(T[n].status, T[n].status_type) : `<span class="muted">–</span>`,
  };
}
