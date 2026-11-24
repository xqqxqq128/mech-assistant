from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, time as dt_time, timezone
from typing import Any, Protocol
from zoneinfo import ZoneInfo

import httpx


class MarketDataError(RuntimeError):
    def __init__(self, message: str, code: str = "MARKET_DATA_ERROR") -> None:
        super().__init__(message)
        self.code = code


class MarketDataProvider(Protocol):
    name: str

    async def latest(self, symbols: list[str]) -> list[dict[str, Any]]:
        ...

    async def history(self, symbol: str, interval: str, limit: int) -> list[dict[str, Any]]:
        ...

    async def search(self, query: str) -> list[dict[str, str]]:
        ...


class UnconfiguredProvider:
    name = "未配置"

    async def latest(self, symbols: list[str]) -> list[dict[str, Any]]:
        raise MarketDataError("尚未配置 A 股行情服务，请设置 MARKET_DATA_PROVIDER 和对应凭据。", "PROVIDER_NOT_CONFIGURED")

    async def history(self, symbol: str, interval: str, limit: int) -> list[dict[str, Any]]:
        raise MarketDataError("尚未配置 A 股历史行情服务。", "PROVIDER_NOT_CONFIGURED")

    async def search(self, query: str) -> list[dict[str, str]]:
        raise MarketDataError("尚未配置 A 股股票搜索服务。", "PROVIDER_NOT_CONFIGURED")


class TushareProvider:
    name = "Tushare"
    endpoint = "https://api.tushare.pro"

    def __init__(self, token: str) -> None:
        if not token:
            raise MarketDataError("TUSHARE_TOKEN 未配置。", "PROVIDER_NOT_CONFIGURED")
        self.token = token

    async def _query(self, api_name: str, params: dict[str, Any], fields: str) -> list[dict[str, Any]]:
        payload = {"api_name": api_name, "token": self.token, "params": params, "fields": fields}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(self.endpoint, json=payload)
                response.raise_for_status()
                body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise MarketDataError("行情供应商请求失败，请检查网络或接口状态。", "PROVIDER_REQUEST_FAILED") from exc
        if body.get("code") != 0:
            raise MarketDataError(body.get("msg") or "行情供应商返回错误。", "PROVIDER_RESPONSE_ERROR")
        data = body.get("data") or {}
        return [dict(zip(data.get("fields", []), row)) for row in data.get("items", [])]

    async def latest(self, symbols: list[str]) -> list[dict[str, Any]]:
        rows = await self._query("realtime_quote", {"ts_code": ",".join(symbols)}, "*")
        return [
            {
                "symbol": row.get("TS_CODE") or row.get("ts_code"),
                "name": row.get("NAME") or row.get("name") or "",
                "price": row.get("PRICE") or row.get("price"),
                "open": row.get("OPEN") or row.get("open"),
                "high": row.get("HIGH") or row.get("high"),
                "low": row.get("LOW") or row.get("low"),
                "previous_close": row.get("PRE_CLOSE") or row.get("pre_close"),
                "volume": row.get("VOLUME") or row.get("volume"),
                "amount": row.get("AMOUNT") or row.get("amount"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            for row in rows
        ]

    async def history(self, symbol: str, interval: str, limit: int) -> list[dict[str, Any]]:
        if interval not in {"1d", "daily"}:
            raise MarketDataError("Tushare 日线适配器暂不支持该周期。", "INTERVAL_NOT_SUPPORTED")
        rows = await self._query("daily", {"ts_code": symbol}, "ts_code,trade_date,open,high,low,close,vol,amount")
        return [
            {
                "symbol": symbol,
                "timestamp": row.get("trade_date"),
                "open": row.get("open"),
                "high": row.get("high"),
                "low": row.get("low"),
                "close": row.get("close"),
                "volume": row.get("vol"),
                "amount": row.get("amount"),
            }
            for row in rows[-limit:]
        ]

    async def search(self, query: str) -> list[dict[str, str]]:
        rows = await self._query("stock_basic", {"exchange": "", "list_status": "L"}, "ts_code,name,exchange")
        needle = query.lower().strip()
        return [
            {"symbol": row.get("ts_code", ""), "name": row.get("name", ""), "exchange": row.get("exchange", "")}
            for row in rows
            if needle in row.get("ts_code", "").lower() or needle in row.get("name", "").lower()
        ][:20]


def _eastmoney_secid(symbol: str) -> str:
    code = symbol.upper().split(".")[0]
    if code.startswith(("5", "6", "688", "689")):
        return f"1.{code}"
    return f"0.{code}"


class EastmoneyWebProvider:
    """Low-frequency development adapter for Eastmoney's public web endpoints."""

    name = "东方财富网页行情（非官方）"
    quote_endpoint = "https://push2.eastmoney.com/api/qt/ulist.np/get"
    history_endpoint = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    search_endpoint = "https://searchapi.eastmoney.com/api/suggest/get"

    async def _get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                timeout=8,
                headers={"User-Agent": "QuantPilot/0.1 (research client)"},
            ) as client:
                response = await client.get(endpoint, params=params)
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise MarketDataError("东方财富网页行情请求失败。", "PROVIDER_REQUEST_FAILED") from exc

    async def latest(self, symbols: list[str]) -> list[dict[str, Any]]:
        if not symbols:
            return []
        secids = ",".join(_eastmoney_secid(symbol) for symbol in symbols)
        body = await self._get(
            self.quote_endpoint,
            {
                "secids": secids,
                "fields": "f43,f57,f58,f46,f44,f45,f47,f48,f60,f169,f170",
                "invt": "2",
                "fltt": "2",
            },
        )
        rows = (body.get("data") or {}).get("diff", [])
        result = []
        for row in rows or []:
            code = str(row.get("f57") or "")
            price = row.get("f43")
            previous_close = row.get("f60")
            result.append(
                {
                    "symbol": code,
                    "name": row.get("f58") or "",
                    "price": None if price in (None, "-") else float(price) / 1000,
                    "open": None if row.get("f46") in (None, "-") else float(row["f46"]) / 1000,
                    "high": None if row.get("f44") in (None, "-") else float(row["f44"]) / 1000,
                    "low": None if row.get("f45") in (None, "-") else float(row["f45"]) / 1000,
                    "previous_close": None if previous_close in (None, "-") else float(previous_close) / 1000,
                    "volume": row.get("f47"),
                    "amount": row.get("f48"),
                    "change_percent": row.get("f169"),
                    "change": row.get("f170"),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "data_quality": "unofficial_web_endpoint",
                }
            )
        return result

    async def history(self, symbol: str, interval: str, limit: int) -> list[dict[str, Any]]:
        klt = {"1d": "101", "5m": "5", "15m": "15", "30m": "30", "1h": "60"}.get(interval)
        if klt is None:
            raise MarketDataError("东方财富网页适配器不支持该 K 线周期。", "INTERVAL_NOT_SUPPORTED")
        body = await self._get(
            self.history_endpoint,
            {
                "secid": _eastmoney_secid(symbol),
                "klt": klt,
                "fqt": "1",
                "beg": "0",
                "end": "20500101",
                "lmt": str(limit),
                "fields1": "f1,f2,f3,f4",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            },
        )
        data = body.get("data") or {}
        columns = ["timestamp", "open", "close", "high", "low", "volume", "amount", "amplitude", "change_percent", "change", "turnover"]
        bars = []
        for item in data.get("klines") or []:
            values = item.split(",")
            row = dict(zip(columns, values))
            bars.append(
                {
                    "symbol": symbol.upper(),
                    "timestamp": row.get("timestamp"),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]),
                    "amount": float(row["amount"]),
                    "data_quality": "unofficial_web_endpoint",
                }
            )
        return bars[-limit:]

    async def search(self, query: str) -> list[dict[str, str]]:
        body = await self._get(
            self.search_endpoint,
            {"input": query, "type": "14", "count": "20", "token": "b7c5e1a3b8f34b4e"},
        )
        table = body.get("QuotationCodeTable") or {}
        rows = table.get("Data") or []
        return [
            {
                "symbol": str(row.get("Code") or ""),
                "name": str(row.get("Name") or ""),
                "exchange": str(row.get("MktNum") or ""),
            }
            for row in rows
            if row.get("Code")
        ]


@dataclass
class MarketSession:
    provider: MarketDataProvider
    watchlist: list[str] = field(default_factory=list)
    last_quotes: dict[str, dict[str, Any]] = field(default_factory=dict)
    last_success_at: str | None = None
    last_error: dict[str, str] | None = None

    def status(self) -> dict[str, Any]:
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
        current = now.time()
        weekday = now.weekday() < 5
        if not weekday:
            session = "closed"
        elif dt_time(9, 15) <= current < dt_time(9, 30):
            session = "auction"
        elif dt_time(9, 30) <= current < dt_time(11, 30) or dt_time(13, 0) <= current < dt_time(15, 0):
            session = "continuous"
        elif dt_time(11, 30) <= current < dt_time(13, 0):
            session = "lunch_break"
        else:
            session = "closed"
        return {
            "market": "CN_A_SHARE",
            "session": session,
            "timezone": "Asia/Shanghai",
            "provider": self.provider.name,
            "watchlist": self.watchlist,
            "last_success_at": self.last_success_at,
            "last_error": self.last_error,
            "server_time": now.isoformat(),
        }

    async def poll(self) -> list[dict[str, Any]]:
        if not self.watchlist:
            return []
        started = time.perf_counter()
        try:
            quotes = await self.provider.latest(self.watchlist)
        except MarketDataError as exc:
            self.last_error = {"code": exc.code, "message": str(exc)}
            raise
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        for quote in quotes:
            quote["latency_ms"] = latency_ms
            self.last_quotes[quote["symbol"]] = quote
        self.last_success_at = datetime.now(timezone.utc).isoformat()
        self.last_error = None
        return quotes


def build_provider() -> MarketDataProvider:
    provider_name = os.getenv("MARKET_DATA_PROVIDER", "").lower()
    if provider_name == "tushare":
        try:
            return TushareProvider(os.getenv("TUSHARE_TOKEN", ""))
        except MarketDataError:
            return UnconfiguredProvider()
    if provider_name == "eastmoney_web":
        return EastmoneyWebProvider()
    return UnconfiguredProvider()


market_session = MarketSession(provider=build_provider())
