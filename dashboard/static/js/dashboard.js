/* dashboard.js */
const MAX_POINTS = 60;
const labels = Array(MAX_POINTS).fill("");
const chartDefaults = {
  type: "line",
  options: {
    animation: false, responsive: true, maintainAspectRatio: true,
    plugins: { legend: { display: false } },
    scales: {
      x: { display: false },
      y: { grid: { color: "rgba(255,255,255,.07)" },
           ticks: { color: "#8892a4", font: { size: 11 } } }
    },
  }
};
const gasChart = new Chart(document.getElementById("chart-gas"), {
  ...chartDefaults,
  data: { labels, datasets: [{ data: Array(MAX_POINTS).fill(null),
    borderColor: "#3b82f6", borderWidth: 1.5, pointRadius: 0,
    fill: true, backgroundColor: "rgba(59,130,246,.08)", tension: 0.3 }] }
});
const tempChart = new Chart(document.getElementById("chart-temp"), {
  ...chartDefaults,
  data: { labels, datasets: [{ data: Array(MAX_POINTS).fill(null),
    borderColor: "#f59e0b", borderWidth: 1.5, pointRadius: 0,
    fill: true, backgroundColor: "rgba(245,158,11,.08)", tension: 0.3 }] }
});

const connBadge = document.getElementById("conn-status");
let evtSource;

function connectSSE() {
  evtSource = new EventSource("/api/stream");
  evtSource.onopen  = () => { connBadge.textContent = "Live"; connBadge.className = "badge badge-ok"; };
  evtSource.onerror = () => { connBadge.textContent = "Reconnecting…"; connBadge.className = "badge badge-warning"; };
  evtSource.onmessage = (e) => {
    try { const d = JSON.parse(e.data); if (!d.connected) updateGauges(d); } catch (_) {}
  };
}

function updateGauges(d) {
  const gasPct = Math.min((d.gas_adc / 1023) * 100, 100);
  document.getElementById("val-gas").textContent  = d.gas_adc;
  document.getElementById("bar-gas").style.width  = gasPct + "%";
  document.getElementById("bar-gas").style.background =
    d.gas_adc >= 400 ? "var(--danger)" : d.gas_adc >= 250 ? "var(--warn)" : "var(--ok)";
  document.getElementById("rate-gas").textContent =
    "rate: " + (d.gas_rate_pct >= 0 ? "+" : "") + d.gas_rate_pct.toFixed(1) + "% / 10s";
  setCardState("card-gas", d.gas_alarm ? "alarm" : d.gas_adc >= 250 ? "warn" : "ok");

  document.getElementById("val-temp").textContent = (d.temperature ?? "—") + " °C";
  document.getElementById("val-hum").textContent  = "humidity: " + (d.humidity ?? "—") + " %";
  const tempPct = Math.min(((d.temperature ?? 0) / 80) * 100, 100);
  document.getElementById("bar-temp").style.width = tempPct + "%";
  document.getElementById("bar-temp").style.background =
    d.temp_alarm ? "var(--danger)" : d.temperature >= 45 ? "var(--warn)" : "var(--ok)";
  setCardState("card-temp", d.temp_alarm ? "alarm" : d.temperature >= 45 ? "warn" : "ok");

  document.getElementById("val-flame").textContent = d.flame_detected ? "🔥 DETECTED" : "None";
  setCardState("card-flame", d.flame_detected ? "alarm" : "ok");

  document.getElementById("val-alarm").textContent = d.alarm ? "🚨 ALARM" : "✓ Normal";
  setCardState("card-alarm", d.alarm ? "alarm" : "ok");
  document.getElementById("val-time").textContent = "last update: " + new Date().toLocaleTimeString();

  shiftPush(gasChart.data.datasets[0].data,  d.gas_adc);
  shiftPush(tempChart.data.datasets[0].data, d.temperature);
  gasChart.update("none");
  tempChart.update("none");
}

function setCardState(cardId, state) {
  const el = document.getElementById(cardId);
  el.classList.remove("ok", "warn", "alarm");
  el.classList.add(state);
}

function shiftPush(arr, val) { arr.shift(); arr.push(val); }

async function loadEvents() {
  const res  = await fetch("/api/events?limit=30");
  const data = await res.json();
  const tbody = document.getElementById("events-body");
  tbody.innerHTML = "";
  data.events.forEach(ev => {
    const decClass =
      ev.ai_decision === "GENUINE_EMERGENCY"  ? "dec-genuine"  :
      ev.ai_decision === "LIKELY_FALSE_ALARM" ? "dec-false"    : "dec-uncertain";
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${ev.timestamp.replace("T"," ").slice(0,19)}</td>
      <td>${ev.trigger_reason ?? "—"}</td>
      <td class="${decClass}">${ev.ai_decision ?? "—"}</td>
      <td>${ev.ai_confidence != null ? (ev.ai_confidence*100).toFixed(0)+"%" : "—"}</td>
      <td>${ev.sms_sent   ? "✓" : "—"}</td>
      <td>${ev.email_sent ? "✓" : "—"}</td>
      <td>${ev.acknowledged ? "✓" : "—"}</td>
      <td>${!ev.acknowledged ? `<button onclick="openAck(${ev.id})">Ack</button>` : ""}</td>`;
    tbody.appendChild(tr);
  });
}

function openAck(id) {
  document.getElementById("ack-id").value = id;
  document.getElementById("ack-notes").value = "";
  document.getElementById("ack-modal").classList.remove("hidden");
}
function closeAck() { document.getElementById("ack-modal").classList.add("hidden"); }
async function submitAck() {
  const id    = document.getElementById("ack-id").value;
  const notes = document.getElementById("ack-notes").value;
  await fetch("/api/acknowledge", {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ event_id: parseInt(id), notes }),
  });
  closeAck(); loadEvents();
}

async function loadLatest() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    if (data.status === "ok" && data.latest) updateGauges(data.latest);
  } catch (_) {}
}

connectSSE();
loadLatest();
loadEvents();
setInterval(loadEvents, 30000);
