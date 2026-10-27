// Live-update connection: shows a Live/Disconnected indicator and calls onChange
// on every server push and each (re)connect, so missed changes are picked up.
function connectLive(onChange) {
  const badge = document.createElement("div");
  badge.className = "live";
  badge.setAttribute("role", "status");
  const set = (on) => { badge.classList.toggle("on", on); badge.textContent = on ? "Live" : "Disconnected"; };
  set(false);
  document.getElementById("topbar-controls").appendChild(badge);

  const source = new EventSource("api/stream");  // reconnects on its own
  source.onopen = () => { set(true); onChange(); };
  source.onerror = () => set(false);
  source.onmessage = onChange;
}
