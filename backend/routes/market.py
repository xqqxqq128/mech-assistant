from __future__ import annotations

import asyncio
import json
from typing import Any

from backend.services.market import MarketDataError, market_session
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/market", tags=["market"])


class WatchlistRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list, max_length=100)


@router.get("/status")
async def status() -> dict[str, Any]:
    return market_session.status()


@router.get("/watchlist")
async def watchlist() -> dict[str, Any]:
    return {"symbols": market_session.watchlist, "quotes": list(market_session.last_quotes.values())}


@router.put("/watchlist")
async def update_watchlist(request: WatchlistRequest) -> dict[str, Any]:
    symbols = [symbol.strip().upper() for symbol in request.symbols if symbol.strip()]
    if len(symbols) != len(set(symbols)):
        raise HTTPException(status_code=400, detail="自选股代码不能重复。")
    market_session.watchlist = symbols
    return await watchlist()


@router.get("/history")
async def history(
    symbol: str = Query(..., min_length=3, max_length=20),
    interval: str = Query("1d", min_length=1, max_length=10),
    limit: int = Query(240, ge=1, le=2000),
) -> dict[str, Any]:
    try:
        bars = await market_session.provider.history(symbol.upper(), interval, limit)
    except MarketDataError as exc:
        raise HTTPException(status_code=503, detail={"code": exc.code, "message": str(exc)}) from exc
    return {"symbol": symbol.upper(), "interval": interval, "bars": bars, "provider": market_session.provider.name}


@router.get("/search")
async def search(query: str = Query(..., min_length=1, max_length=30)) -> dict[str, Any]:
    try:
        results = await market_session.provider.search(query)
    except MarketDataError as exc:
        raise HTTPException(status_code=503, detail={"code": exc.code, "message": str(exc)}) from exc
    return {"results": results}


@router.get("/signal")
async def signal(symbol: str = Query(..., min_length=3, max_length=20), limit: int = Query(80, ge=20, le=500)) -> dict[str, Any]:
    try:
        bars = await market_session.provider.history(symbol.upper(), "1d", limit)
    except MarketDataError as exc:
        raise HTTPException(status_code=503, detail={"code": exc.code, "message": str(exc)}) from exc
    closes = [float(bar["close"]) for bar in bars if bar.get("close") is not None]
    if len(closes) < 20:
        return {"symbol": symbol.upper(), "signal": None, "reason": "历史数据不足，至少需要 20 根收盘价。"}
    short = sum(closes[-5:]) / 5
    long = sum(closes[-20:]) / 20
    direction = "bullish" if short > long else "bearish" if short < long else "neutral"
    return {
        "symbol": symbol.upper(),
        "signal": direction,
        "reason": f"5 日均线 {short:.2f} 与 20 日均线 {long:.2f} 的相对位置",
        "timestamp": bars[-1].get("timestamp"),
    }


@router.websocket("/ws")
async def market_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    interval = 5.0
    try:
        await websocket.send_json({"type": "market_status", "data": market_session.status()})
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=interval)
                payload = json.loads(message)
                if payload.get("type") == "subscribe":
                    symbols = payload.get("symbols", [])
                    market_session.watchlist = [str(symbol).upper() for symbol in symbols if str(symbol).strip()]
                    await websocket.send_json({"type": "market_status", "data": market_session.status()})
                elif payload.get("type") == "ping":
                    await websocket.send_json({"type": "heartbeat", "data": market_session.status()})
            except asyncio.TimeoutError:
                try:
                    quotes = await market_session.poll()
                    if quotes:
                        await websocket.send_json({"type": "quote", "data": quotes})
                    else:
                        await websocket.send_json({"type": "heartbeat", "data": market_session.status()})
                except MarketDataError as exc:
                    await websocket.send_json(
                        {"type": "error", "data": {"code": exc.code, "message": str(exc), "status": market_session.status()}}
                    )
    except WebSocketDisconnect:
        return
