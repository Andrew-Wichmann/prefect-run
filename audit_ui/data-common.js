// Shared by the stage-output viewer variants. Each data-vN.js calls registerView({ n, title, blurb, mount }).
// mount(el, ctx) draws into el and may return a cleanup function; ctx.meta has total_rows / total_cols.

const Q = new URLSearchParams(location.search);
const RUN = Q.get("run"), STAGE = Q.get("stage"), TASK = Q.get("task_run");
const VIEWS = [];
const registerView = (v) => VIEWS.push(v);

const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const $ = (id) => document.getElementById(id);
const apiUrl = (path, p = {}) => `api/${path}?` + new URLSearchParams({ run: RUN, stage: STAGE, ...(TASK ? { task_run: TASK } : {}), ...p });
async function getJSON(path, p) {
  const r = await fetch(apiUrl(path, p));
  if (!r.ok) throw new Error(`${path}: ${r.status} ${(await r.text()).slice(0, 200)}`);
  return r.json();
}

const fmt = (v, d = 2) => v == null ? "–" : v.toFixed(d);
const pct = (v) => v == null ? "–" : `${(100 * v).toFixed(1)}%`;
const n0 = (v) => v.toLocaleString();
// Shade a scenario price by its move against the instrument's input price: red down, green up.
function heat(v, base) {
  if (v == null || !base) return "";
  const m = v / base - 1, a = Math.min(Math.abs(m) / 0.3, 1) * 0.5;
  return `background:${m < 0 ? `rgba(220,38,38,${a.toFixed(2)})` : `rgba(22,163,74,${a.toFixed(2)})`}`;
}
const statusCell = (o) => o ? `<span class="st ${esc(o[0])}">${esc(o[0])}</span>` : "";

// Element helper: h("div", {class: "x", onclick}, child, ...)
function h(tag, attrs = {}, ...kids) {
  const e = ["svg", "rect"].includes(tag) ? document.createElementNS("http://www.w3.org/2000/svg", tag) : document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (k === "html") e.innerHTML = v;
    else if (v !== false && v != null) e.setAttribute(k, v === true ? "" : v);
  }
  e.append(...kids.flat().filter((k) => k != null));
  return e;
}

// "Download Excel" for the Joule-side xlsx writer (api/xlsx). `win()` gives the window the viewer is showing, or
// null to offer only the whole table. Navigating to an attachment response downloads without leaving the page.
function excelButtons(win) {
  const go = (p) => { location.href = apiUrl("xlsx", p); };
  return h("span", { class: "xl" },
    win ? h("button", { class: "btn", title: "An .xlsx of the rows and columns currently in view", onclick: () => go(win()) }, "⬇ Excel (this view)") : null,
    win ? " " : null,
    h("button", { class: "btn", title: "Every instrument and every scenario", onclick: () => go({}) }, "⬇ Excel (all)"));
}

function csvDownload(name, header, rows) {
  const q = (v) => v == null ? "" : /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v);
  const blob = new Blob([[header, ...rows].map((r) => r.map(q).join(",")).join("\n")], { type: "text/csv" });
  const a = h("a", { href: URL.createObjectURL(blob), download: name });
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
}

const loadScript = (src) => new Promise((ok, no) => document.head.append(h("script", { src, onload: ok, onerror: () => no(new Error(`could not load ${src}`)) })));
const loadCss = (href) => document.head.append(h("link", { rel: "stylesheet", href }));

const AG = "32.3.3";
async function ensureAgGrid() {
  if (window.agGrid) return;
  loadCss(`https://cdn.jsdelivr.net/npm/ag-grid-community@${AG}/styles/ag-grid.css`);
  loadCss(`https://cdn.jsdelivr.net/npm/ag-grid-community@${AG}/styles/ag-theme-quartz.css`);
  await loadScript(`https://cdn.jsdelivr.net/npm/ag-grid-community@${AG}/dist/ag-grid-community.min.js`);
}
const darkMode = () => matchMedia("(prefers-color-scheme: dark)").matches;

async function boot() {
  $("title").innerHTML = STAGE ? `<code>${esc(STAGE)}</code> output` : "Stage output";
  if (!RUN || !STAGE) { $("view").innerHTML = `<div class="err">Open this from a stage's data button (needs ?run= and ?stage=).</div>`; return; }
  let meta;
  try { meta = await getJSON("matrix", { row_limit: 1, col_limit: 1 }); }
  catch (e) { $("view").innerHTML = `<div class="err">${esc(e.message)}</div>`; return; }
  $("meta").textContent = `${n0(meta.total_rows)} instruments × ${n0(meta.total_cols)} scenarios · run ${RUN.slice(0, 8)}`;
  const views = [...VIEWS].sort((a, b) => a.n - b.n);
  let cleanup = null, token = 0;
  const show = async (n) => {
    const v = views.find((x) => x.n === n) || views[0], mine = ++token;
    for (const b of $("tabs").children) b.setAttribute("aria-selected", String(+b.dataset.n === v.n));
    history.replaceState(null, "", `#v${v.n}`);
    cleanup?.(); cleanup = null;
    $("blurb").textContent = v.blurb;
    const el = $("view");
    el.innerHTML = "";
    try { const c = await v.mount(el, { meta }); if (mine === token) cleanup = c; else c?.(); }
    catch (e) { el.innerHTML = `<div class="err">${esc(e.message)}</div>`; }
  };
  $("tabs").append(...views.map((v) => h("button", { role: "tab", "data-n": v.n, onclick: () => show(v.n) }, `${v.n}. ${v.title}`)));
  show(+(location.hash.match(/^#v(\d+)/)?.[1] || 1));
}
