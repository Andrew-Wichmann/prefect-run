// Every timestamp on the page goes through here: 24-hour clock, always followed by its time zone.
// The zone is picked client-side (top bar) and remembered in this browser.
const ZONES = [["local", "Local"], ["UTC", "UTC"], ["America/New_York", "New York"], ["Europe/London", "London"], ["Asia/Tokyo", "Tokyo"]];
let zone = "local";
try { const z = localStorage.getItem("zone"); if (ZONES.some(([k]) => k === z)) zone = z; } catch {}

const zoneId = (z = zone) => z === "local" ? undefined : z;
function parts(t, z, withDate, withSeconds) {
  const o = { hourCycle: "h23", hour: "2-digit", minute: "2-digit", timeZone: zoneId(z), timeZoneName: "short" };
  if (withSeconds) o.second = "2-digit";
  if (withDate) Object.assign(o, { year: "numeric", month: "2-digit", day: "2-digit" });
  const p = Object.fromEntries(new Intl.DateTimeFormat("en-US", o).formatToParts(new Date(t)).map((x) => [x.type, x.value]));
  const hm = `${p.hour}:${p.minute}${withSeconds ? ":" + p.second : ""}`;
  return `${withDate ? `${p.year}-${p.month}-${p.day} ` : ""}${hm} ${p.timeZoneName}`;
}
// e.g. "23:19:50 EDT"; the date is included only when asked for.
const fmtTime = (t, { seconds = true, date = false } = {}) => t ? parts(t, zone, date, seconds) : "–";
// A wall-clock time (HH:MM) in a named zone, e.g. an SLA, shown as that zone's own clock.
const fmtZoned = (hhmm, tz) => `${hhmm} ${new Intl.DateTimeFormat("en-US", { timeZone: tz, timeZoneName: "short" }).formatToParts(new Date()).find((x) => x.type === "timeZoneName")?.value}`;

function zonePicker(onChange) {
  const sel = document.createElement("select");
  sel.className = "tzsel";
  sel.title = "Time zone for every timestamp";
  sel.setAttribute("aria-label", "Time zone");
  sel.innerHTML = ZONES.map(([k, label]) => `<option value="${k}">${k === "local" ? `Local (${Intl.DateTimeFormat().resolvedOptions().timeZone})` : label}</option>`).join("");
  sel.value = zone;
  sel.onchange = () => {
    zone = sel.value;
    try { localStorage.setItem("zone", zone); } catch {}
    onChange();
  };
  document.getElementById("topbar-controls").appendChild(sel);
}
