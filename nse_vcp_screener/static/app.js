let currentStage = "p-k-watch";
let currentScreen = "h:VCP";
let currentData = null;

const STAGE_DESCRIPTIONS = {
  "p-k-watch": "1. Forming: Market leaders pausing and coiling tighter and quieter under their resistance pivot line.",
  "p-k-trig":  "2. Fresh Breakouts: Stocks that cleared their pivot ceiling within the last 5 trading days on heavy volume.",
  "p-k-hold":  "3. Climbing: Established breakouts running in an uptrend, holding safely above stop-loss and moving averages.",
  "p-k-exit":  "4. Played Out: Completed setups that either triggered their −8% stop loss or closed below the trailing 50-DMA."
};

// Initialize
document.addEventListener("DOMContentLoaded", () => {
  loadMarketHealth();
  loadScreener();
  setupEventListeners();
});

function setupEventListeners() {
  // Preset selector
  document.getElementById("sel-screen").addEventListener("change", (e) => {
    currentScreen = e.target.value;
    if (currentScreen === "custom") {
      document.getElementById("dials-panel").style.display = "block";
    }
    loadScreener();
  });

  // Toggle dials
  document.getElementById("btn-toggle-dials").addEventListener("click", () => {
    const p = document.getElementById("dials-panel");
    p.style.display = p.style.display === "none" ? "block" : "none";
  });

  // Stage tab buttons
  document.querySelectorAll(".stage-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".stage-tab").forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      currentStage = tab.dataset.stage;
      document.getElementById("stage-desc").textContent = STAGE_DESCRIPTIONS[currentStage] || "";
      renderTable();
    });
  });

  // Dials live value display
  const dials = [
    { id: "dial-rs", lbl: "lbl-rs", suffix: "" },
    { id: "dial-coil", lbl: "lbl-coil", suffix: "x" },
    { id: "dial-dry", lbl: "lbl-dry", suffix: "x" },
    { id: "dial-baseWk", lbl: "lbl-baseWk", suffix: "w" },
    { id: "dial-depth", lbl: "lbl-depth", suffix: "%" },
    { id: "dial-vs50", lbl: "lbl-vs50", suffix: "%" }
  ];

  dials.forEach(d => {
    const el = document.getElementById(d.id);
    const lbl = document.getElementById(d.lbl);
    if (el && lbl) {
      el.addEventListener("input", (e) => {
        lbl.textContent = e.target.value + d.suffix;
      });
    }
  });

  // Apply dials
  document.getElementById("btn-apply-dials").addEventListener("click", () => {
    currentScreen = "custom";
    document.getElementById("sel-screen").value = "custom";
    loadScreener();
  });

  // Reset dials
  document.getElementById("btn-reset-dials").addEventListener("click", () => {
    document.getElementById("dial-rs").value = 70;
    document.getElementById("lbl-rs").textContent = "70";
    document.getElementById("dial-coil").value = 0.90;
    document.getElementById("lbl-coil").textContent = "0.90x";
    document.getElementById("dial-dry").value = 0.90;
    document.getElementById("lbl-dry").textContent = "0.90x";
    document.getElementById("dial-baseWk").value = 3;
    document.getElementById("lbl-baseWk").textContent = "3w";
    document.getElementById("dial-depth").value = 35;
    document.getElementById("lbl-depth").textContent = "35%";
    document.getElementById("dial-vs50").value = -10;
    document.getElementById("lbl-vs50").textContent = "-10%";
    currentScreen = "h:VCP";
    document.getElementById("sel-screen").value = "h:VCP";
    loadScreener();
  });

  // Sync button
  document.getElementById("btn-sync").addEventListener("click", async () => {
    const btn = document.getElementById("btn-sync");
    btn.disabled = true;
    btn.textContent = "Syncing Bhavcopy...";
    try {
      const res = await fetch("/api/sync_bhavcopy", { method: "POST" });
      const data = await res.json();
      alert(data.message || "Bhavcopy sync complete!");
      loadMarketHealth();
      loadScreener();
    } catch (e) {
      alert("Failed to sync Bhavcopy: " + e.message);
    } finally {
      btn.disabled = false;
      btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 21h5v-5"/></svg> Sync NSE EOD`;
    }
  });

  // Modal close
  document.getElementById("btn-close-modal").addEventListener("click", () => {
    document.getElementById("chart-modal").style.display = "none";
  });
  document.getElementById("chart-modal").addEventListener("click", (e) => {
    if (e.target.id === "chart-modal") {
      document.getElementById("chart-modal").style.display = "none";
    }
  });
}

async function loadMarketHealth() {
  try {
    const res = await fetch("/api/market_health");
    const d = await res.json();
    if (d.ok) {
      const regimeEl = document.getElementById("val-regime");
      regimeEl.textContent = d.regime;
      regimeEl.style.color = d.regime === "Risk-On" ? "var(--green)" : "var(--yellow)";
      document.getElementById("val-uptrend").textContent = `${d.pct_uptrend}% (${d.in_uptrend}/${d.universe})`;
      document.getElementById("val-leaders").textContent = d.leaders;
    }
  } catch (e) {
    console.error("Health load error:", e);
  }
}

async function loadScreener() {
  const tbody = document.getElementById("table-body");
  tbody.innerHTML = `<tr><td colspan="13" class="loading-cell">Evaluating ${currentScreen} across NSE universe...</td></tr>`;

  let payload = { sel: currentScreen };
  if (currentScreen === "custom") {
    payload.spec = {
      rs: [+document.getElementById("dial-rs").value, 99],
      coil: [0.3, +document.getElementById("dial-coil").value],
      dry: [0.05, +document.getElementById("dial-dry").value],
      baseWk: [+document.getElementById("dial-baseWk").value, 300],
      baseDepth: [2, +document.getElementById("dial-depth").value],
      vs50: [+document.getElementById("dial-vs50").value, 200]
    };
  }

  try {
    const res = await fetch("/api/screen", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    currentData = await res.json();

    // Update badges
    const counts = currentData.counts || [0, 0, 0, 0];
    document.getElementById("badge-watch").textContent = counts[0];
    document.getElementById("badge-trig").textContent = counts[1];
    document.getElementById("badge-hold").textContent = counts[2];
    document.getElementById("badge-exit").textContent = counts[3];

    renderTable();
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="13" class="loading-cell">Failed to run screen: ${e.message}</td></tr>`;
  }
}

function renderTable() {
  const tbody = document.getElementById("table-body");
  if (!currentData || !currentData.stages) return;

  const stageData = currentData.stages[currentStage] || { rows: [] };
  const rows = stageData.rows || [];

  if (rows.length === 0) {
    tbody.innerHTML = `<tr><td colspan="13" class="loading-cell">No stocks currently in this stage matching your filter criteria.</td></tr>`;
    return;
  }

  tbody.innerHTML = rows.map(r => {
    const gainClass = r.gain >= 0 ? "pos" : "neg";
    const gainSign = r.gain >= 0 ? "+" : "";
    const extClass = r.ext >= 0 ? "pos" : "neg";
    const extSign = r.ext >= 0 ? "+" : "";
    
    // RS Badge style
    let rsClass = "rs-low";
    if (r.rs >= 80) rsClass = "rs-lead";
    else if (r.rs >= 60) rsClass = "rs-mid";

    return `
      <tr onclick="openChartModal('${r.sym}')">
        <td>
          <div style="font-weight:700;color:var(--yellow)">${r.sym}</div>
          <div style="font-size:11px;color:var(--text-muted)">${r.name || ""}</div>
        </td>
        <td class="num font-bold">₹${r.price.toFixed(2)}</td>
        <td class="num ${gainClass}">${gainSign}${r.gain.toFixed(2)}%</td>
        <td><span class="rs-badge ${rsClass}">${r.rs}</span></td>
        <td class="num font-bold">₹${r.pivot ? r.pivot.toFixed(2) : "--"}</td>
        <td class="num ${extClass}">${extSign}${r.ext !== undefined ? r.ext.toFixed(1) : "--"}%</td>
        <td class="num">${r.baseWk || "--"}w</td>
        <td class="num">${r.baseDepth || "--"}%</td>
        <td class="num">${r.coil ? r.coil.toFixed(2) + "x" : "--"}</td>
        <td class="num">${r.dry ? r.dry.toFixed(2) + "x" : "--"}</td>
        <td class="num">${r.squats || 0}</td>
        <td><span class="num" style="background:#202018;padding:2px 6px;border-radius:4px">L${r.lvl || 1}</span></td>
        <td><button class="btn-chart" onclick="event.stopPropagation();openChartModal('${r.sym}')">Chart</button></td>
      </tr>
    `;
  }).join("");
}

async function openChartModal(symbol) {
  const modal = document.getElementById("chart-modal");
  modal.style.display = "flex";
  
  document.getElementById("modal-stock-title").textContent = symbol;
  document.getElementById("modal-stock-sub").textContent = "Loading candle bars and base structure...";
  
  try {
    const res = await fetch(`/api/stocks/${symbol}`);
    const data = await res.json();
    if (!data.ok) throw new Error("Stock data not found");

    document.getElementById("modal-stock-title").textContent = data.symbol;
    document.getElementById("modal-stock-sub").textContent = `${data.name} · ₹${data.bars[data.bars.length - 1].close.toFixed(2)}`;

    // Metrics bar
    const m = data.metrics || {};
    const barHtml = `
      <div class="modal-metric">Pivot: <b>₹${m.pivot || "--"}</b></div>
      <div class="modal-metric">Base: <b>${m.baseWk || "--"}w (${m.baseDepth || "--"}% depth)</b></div>
      <div class="modal-metric">Coil (ATR ratio): <b>${m.coil ? m.coil.toFixed(2) + "x" : "--"}</b></div>
      <div class="modal-metric">Dry-up (Vol ratio): <b>${m.dry ? m.dry.toFixed(2) + "x" : "--"}</b></div>
      <div class="modal-metric">RS Rating: <b>${m.rs || "--"}</b></div>
      <div class="modal-metric">Ext vs Pivot: <b>${m.ext ? m.ext.toFixed(1) + "%" : "--"}</b></div>
      <div class="modal-metric">50-DMA: <b>₹${m.dma50 || "--"}</b></div>
    `;
    document.getElementById("modal-metrics").innerHTML = barHtml;

    drawCandlestickChart(data.bars, m);
  } catch (e) {
    document.getElementById("modal-stock-sub").textContent = "Error: " + e.message;
  }
}

function drawCandlestickChart(bars, metrics) {
  const canvas = document.getElementById("chart-canvas");
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;

  ctx.clearRect(0, 0, width, height);

  if (!bars || bars.length === 0) return;

  // Render recent 80 bars
  const slice = bars.slice(-80);
  const n = slice.length;

  let minPrice = Infinity;
  let maxPrice = -Infinity;
  let maxVol = 0;

  slice.forEach(b => {
    if (b.low < minPrice) minPrice = b.low;
    if (b.high > maxPrice) maxPrice = b.high;
    if (b.volume > maxVol) maxVol = b.volume;
  });

  if (metrics.pivot && metrics.pivot > maxPrice) maxPrice = metrics.pivot * 1.02;
  const priceMargin = (maxPrice - minPrice) * 0.08;
  minPrice -= priceMargin;
  maxPrice += priceMargin;

  const chartBottom = height - 90;
  const volTop = height - 80;

  const getY = (p) => chartBottom - ((p - minPrice) / (maxPrice - minPrice)) * chartBottom;
  const barWidth = Math.max(3, (width - 60) / n - 2);

  // Grid lines
  ctx.strokeStyle = "#1e1e18";
  ctx.lineWidth = 1;
  for (let i = 1; i <= 4; i++) {
    const y = (chartBottom / 4) * i;
    ctx.beginPath();
    ctx.moveTo(10, y);
    ctx.lineTo(width - 50, y);
    ctx.stroke();
  }

  // Draw Candlesticks & Volume
  slice.forEach((b, i) => {
    const x = 20 + i * (barWidth + 2);
    const isUp = b.close >= b.open;
    const color = isUp ? "#26a69a" : "#ef5350";

    // Wick
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(x + barWidth / 2, getY(b.high));
    ctx.lineTo(x + barWidth / 2, getY(b.low));
    ctx.stroke();

    // Body
    const yOpen = getY(b.open);
    const yClose = getY(b.close);
    const bodyTop = Math.min(yOpen, yClose);
    const bodyHeight = Math.max(2, Math.abs(yClose - yOpen));

    ctx.fillStyle = color;
    ctx.fillRect(x, bodyTop, barWidth, bodyHeight);

    // Volume bar
    const vHeight = maxVol > 0 ? (b.volume / maxVol) * 70 : 0;
    ctx.fillStyle = isUp ? "rgba(38, 166, 154, 0.4)" : "rgba(239, 83, 80, 0.4)";
    ctx.fillRect(x, height - vHeight - 10, barWidth, vHeight);
  });

  // Base Pivot Resistance Line
  if (metrics.pivot) {
    const pY = getY(metrics.pivot);
    ctx.strokeStyle = "#ffc926";
    ctx.lineWidth = 2;
    ctx.setLineDash([6, 4]);
    ctx.beginPath();
    ctx.moveTo(20, pY);
    ctx.lineTo(width - 50, pY);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.fillStyle = "#ffc926";
    ctx.font = "bold 11px JetBrains Mono";
    ctx.fillText(`PIVOT ₹${metrics.pivot}`, width - 110, pY - 6);
  }
}
