const state = { symbols: [], selected: null, quotes: new Map(), points: [], socket: null };
const $ = (selector) => document.querySelector(selector);

function log(message, level = "info") {
  const row = document.createElement("div");
  row.className = `log-row ${level}`;
  row.innerHTML = `<span>${new Date().toLocaleTimeString("zh-CN")}</span><b>${message}</b>`;
  $("#logs").prepend(row);
  while ($("#logs").children.length > 8) $("#logs").lastElementChild.remove();
}

function setSocketStatus(online, text) {
  const badge = $("#socket-status");
  badge.className = `socket-badge ${online ? "online" : "offline"}`;
  badge.textContent = `● ${text}`;
}

function formatPrice(value) {
  return value == null ? "—" : Number(value).toFixed(2);
}

function renderWatchlist() {
  const container = $("#watchlist");
  if (!state.symbols.length) {
    container.innerHTML = '<div class="empty-list">添加股票代码开始看盘</div>';
    return;
  }
  container.innerHTML = state.symbols.map((symbol) => {
    const quote = state.quotes.get(symbol);
    const price = quote?.price;
    const change = price != null && quote?.previous_close ? ((price - quote.previous_close) / quote.previous_close) * 100 : null;
    return `<button class="watch-item ${symbol === state.selected ? "selected" : ""}" data-symbol="${symbol}">
      <span><b>${symbol}</b><small>${quote?.name || "等待行情"}</small></span>
      <span class="watch-price"><b>${formatPrice(price)}</b><small class="${change >= 0 ? "up" : "down"}">${change == null ? "—" : `${change >= 0 ? "+" : ""}${change.toFixed(2)}%`}</small></span>
    </button>`;
  }).join("");
  container.querySelectorAll("[data-symbol]").forEach((button) => button.addEventListener("click", () => selectSymbol(button.dataset.symbol)));
}

function renderQuote(quote) {
  if (!quote) return;
  $("#selected-symbol").textContent = `${quote.symbol}${quote.name ? ` · ${quote.name}` : ""}`;
  $("#last-price").textContent = formatPrice(quote.price);
  $("#open-close").textContent = `${formatPrice(quote.open)} / ${formatPrice(quote.previous_close)}`;
  $("#high-low").textContent = `${formatPrice(quote.high)} / ${formatPrice(quote.low)}`;
  $("#volume").textContent = quote.volume == null ? "—" : Number(quote.volume).toLocaleString("zh-CN");
  $("#quote-time").textContent = quote.timestamp ? new Date(quote.timestamp).toLocaleTimeString("zh-CN") : "—";
  const change = quote.price != null && quote.previous_close ? ((quote.price - quote.previous_close) / quote.previous_close) * 100 : null;
  $("#price-change").textContent = change == null ? "—" : `${change >= 0 ? "+" : ""}${change.toFixed(2)}%`;
  $("#price-change").className = change >= 0 ? "up" : "down";
  $("#latency").textContent = `延迟：${quote.latency_ms == null ? "—" : `${quote.latency_ms} ms`}`;
}

function drawChart() {
  const canvas = $("#market-chart");
  const empty = $("#chart-empty");
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (state.points.length < 2) {
    empty.classList.add("visible");
    return;
  }
  empty.classList.remove("visible");
  const values = state.points.map((point) => point.price).filter(Number.isFinite);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  ctx.strokeStyle = "#263651";
  ctx.lineWidth = 1;
  for (let y = 40; y < 400; y += 72) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke(); }
  ctx.strokeStyle = "#52e2b0";
  ctx.lineWidth = 3;
  ctx.beginPath();
  state.points.forEach((point, index) => {
    const x = (index / (state.points.length - 1)) * canvas.width;
    const y = 380 - ((point.price - min) / range) * 320;
    index ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  });
  ctx.stroke();
}

function selectSymbol(symbol) {
  state.selected = symbol;
  state.points = [];
  renderWatchlist();
  $("#selected-symbol").textContent = symbol;
  if (state.socket?.readyState === WebSocket.OPEN) state.socket.send(JSON.stringify({ type: "subscribe", symbols: state.symbols }));
  log(`已选择 ${symbol}`);
}

async function request(path, options = {}) {
  const response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail?.message || data.detail || "请求失败");
  return data;
}

async function loadWatchlist() {
  try {
    const data = await request("/api/market/watchlist");
    state.symbols = data.symbols || [];
    (data.quotes || []).forEach((quote) => state.quotes.set(quote.symbol, quote));
    state.selected = state.symbols[0] || null;
    renderWatchlist();
    if (state.selected) $("#selected-symbol").textContent = state.selected;
  } catch (error) { log(error.message, "error"); }
}

function connectSocket() {
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  state.socket = new WebSocket(`${protocol}://${location.host}/ws/market`);
  state.socket.onopen = () => {
    setSocketStatus(true, "已连接");
    state.socket.send(JSON.stringify({ type: "subscribe", symbols: state.symbols }));
    log("WebSocket 已连接");
  };
  state.socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.type === "market_status") {
      const status = message.data;
      $("#data-source").textContent = `数据源：${status.provider}`;
      $("#market-session").textContent = `市场状态：${status.session}`;
      return;
    }
    if (message.type === "quote") {
      message.data.forEach((quote) => {
        state.quotes.set(quote.symbol, quote);
        if (quote.symbol === state.selected && Number.isFinite(Number(quote.price))) state.points.push({ price: Number(quote.price) });
      });
      renderWatchlist();
      renderQuote(state.quotes.get(state.selected));
      drawChart();
      return;
    }
    if (message.type === "error") log(message.data.message, "error");
  };
  state.socket.onclose = () => {
    setSocketStatus(false, "重连中");
    log("行情连接断开，正在重连", "error");
    setTimeout(connectSocket, 3000);
  };
}

$("#watchlist-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = $("#symbol-input");
  const symbol = input.value.trim().toUpperCase();
  if (!symbol || state.symbols.includes(symbol)) return;
  state.symbols.push(symbol);
  input.value = "";
  await request("/api/market/watchlist", { method: "PUT", body: JSON.stringify({ symbols: state.symbols }) });
  selectSymbol(symbol);
  renderWatchlist();
});

$("#refresh-btn").addEventListener("click", () => {
  if (state.socket?.readyState === WebSocket.OPEN) state.socket.send(JSON.stringify({ type: "ping" }));
});

$("#history-btn").addEventListener("click", async () => {
  if (!state.selected) return;
  try {
    const data = await request(`/api/market/history?symbol=${encodeURIComponent(state.selected)}&interval=1d&limit=240`);
    state.points = (data.bars || []).map((bar) => ({ price: Number(bar.close) })).filter((point) => Number.isFinite(point.price));
    $("#chart-title").textContent = "日线收盘走势";
    drawChart();
    const signal = await request(`/api/market/signal?symbol=${encodeURIComponent(state.selected)}`);
    $("#signals").innerHTML = signal.signal
      ? `<div class="signal-row"><b>${signal.signal.toUpperCase()}</b><span>${signal.reason}</span><small>${signal.timestamp || ""}</small></div>`
      : `<div class="empty-list">${signal.reason}</div>`;
    log(`${state.selected} 历史数据已加载`);
  } catch (error) {
    log(error.message, "error");
  }
});

window.addEventListener("resize", drawChart);
loadWatchlist().then(connectSocket);
