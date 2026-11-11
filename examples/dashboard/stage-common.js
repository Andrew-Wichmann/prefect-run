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
// The Prefect logo (from Prefect's own UI), a single-colour mark so it follows the page's text colour.
// Outlined, round-cornered table glyph: reads as "rows of data" rather than a solid block.
const DATA_ICON = '<svg class="dicon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="1.75" y="2.75" width="12.5" height="10.5" rx="3"/><path d="M2 6.5h12M2 9.9h12M6.2 6.5v6.6"/></svg>';
const PREFECT_ICON = '<svg class="picon" viewBox="0 0 700 700" aria-hidden="true"><g transform="translate(0.000000,700.000000) scale(0.100000,-0.100000)" fill="currentColor" stroke="none"><path d="M3385 6612 c-146 -77 -361 -189 -695 -362 -311 -161 -470 -244 -680 -353 -80 -42 -226 -118 -325 -169 -208 -108 -222 -115 -215 -121 3 -2 109 -57 235 -122 127 -65 253 -130 280 -145 28 -15 131 -69 230 -120 99 -51 225 -116 280 -145 237 -124 724 -376 882 -457 l123 -63 0 -1052 c0 -579 -3 -1053 -7 -1053 -5 0 -19 6 -33 13 -238 125 -476 249 -685 357 -99 51 -216 112 -260 135 -44 23 -156 82 -250 130 -93 48 -215 111 -270 140 -55 29 -190 99 -300 155 -110 57 -204 107 -209 111 -6 5 -13 9 -16 9 -3 0 -5 -475 -5 -1056 l0 -1055 125 -66 c69 -35 195 -101 280 -145 85 -44 200 -104 255 -133 94 -50 203 -106 530 -275 77 -40 190 -98 250 -130 61 -32 182 -95 270 -140 88 -45 197 -103 242 -127 l83 -44 2 1056 3 1056 50 28 c28 15 158 83 290 151 132 67 276 142 320 165 44 23 148 77 230 120 152 79 305 158 495 257 58 30 198 103 312 162 113 59 235 122 270 140 l63 34 2 1055 3 1056 -33 19 c-17 11 -135 72 -262 137 -126 65 -234 121 -240 125 -5 4 -118 62 -250 130 -132 67 -262 135 -290 150 -27 15 -135 71 -240 125 -104 54 -235 121 -290 150 -261 136 -433 225 -436 225 -2 0 -53 -27 -114 -58z"/></g></svg>';
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
