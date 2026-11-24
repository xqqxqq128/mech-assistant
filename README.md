# QuantPilot A 股实时分时看盘

一个面向 A 股的实时看盘终端原型：维护自选股、接收后端 WebSocket 行情、观察分时走势和数据源状态，并为后续策略信号与回测提供统一接口。

> 当前版本不会生成虚构行情。未配置行情服务时，会显示明确的“未配置”状态，不会伪造价格或成交。

## 快速开始

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
```

浏览器打开 <http://127.0.0.1:8000>。

## 当前能力

- A 股自选股列表：手动添加股票代码，状态保存在后端会话中。
- WebSocket 实时链路：`/ws/market` 推送 `market_status`、`quote`、`heartbeat` 和 `error` 事件。
- 透明状态：展示数据源、交易时段、连接状态、行情请求延迟和最后更新时间。
- 历史行情接口：`GET /api/market/history`，为日 K 图和指标层预留统一数据格式。
- Tushare 适配器：通过环境变量配置，未配置凭据时返回结构化错误。
- 东方财富网页实验适配器：设置 `MARKET_DATA_PROVIDER=eastmoney_web` 可用于低频 UI 联调；该接口非官方开发者 API，不保证稳定性、授权或商业使用，不能作为未来实盘生产数据源。

## API

- `GET /api/health` — 健康检查
- `GET /api/market/status` — 市场、交易时段、数据源状态
- `GET /api/market/watchlist` — 获取自选股与最近报价
- `PUT /api/market/watchlist` — 更新自选股，body 为 `{"symbols":["000001.SZ"]}`
- `GET /api/market/history?symbol=000001.SZ&interval=1d` — 获取历史 K 线
- `GET /api/market/search?query=平安` — 股票搜索
- `WS /ws/market` — 实时事件流

## 配置 Tushare

复制 `.env.example` 为 `.env`，填写 `TUSHARE_TOKEN`。`MARKET_DATA_PROVIDER=tushare` 后启动：

```powershell
python -m uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
```

Tushare 账户的权限、频率限制和实时接口可用性以供应商控制台为准；页面会保留数据源和延迟状态，不把延迟行情标记为实时。

## 东方财富网页接口（仅开发联调）

如果暂时没有 Choice/Tushare 凭据，可以在 `.env` 中设置：

```env
MARKET_DATA_PROVIDER=eastmoney_web
```

此模式使用东方财富网页端公开请求来联调自选股、最新价和历史 K 线。它不是东方财富面向第三方的正式 API，可能限频、变更或不可用；系统会在数据质量字段中标记 `unofficial_web_endpoint`。不要高频抓取、绕过访问限制或把该模式用于真实交易决策。

## GitHub 灵感

界面采用量化终端常见的信息架构（指标卡、策略面板、行情图表、持仓/成交双栏），参考了 GitHub 上的公开项目方向，包括：

- [RanvirSinghN/Quantitative_Trading_Simulator](https://github.com/RanvirSinghN/Quantitative_Trading_Simulator)
- [JMR825/quant-trading-simulator](https://github.com/JMR825/quant-trading-simulator)
- [SBascon/Backtesting-Trading-Dashboard-React](https://github.com/SBascon/Backtesting-Trading-Dashboard-React)

本项目仅借鉴公开项目的信息架构与功能思路，没有复制其代码。
