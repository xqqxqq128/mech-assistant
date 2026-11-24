from pydantic import BaseModel, Field

from backend.services.trading import (
    MarketDataUnavailableError,
    Simulator,
    StrategyConfig,
)
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/trading", tags=["trading"])


class StrategyRequest(BaseModel):
    name: str = "双均线趋势策略"
    fast_period: int = Field(20, ge=2, le=500)
    slow_period: int = Field(60, ge=3, le=1000)
    position_size: float = Field(0.25, gt=0, le=1)
    stop_loss: float = Field(0.08, gt=0, le=1)
    take_profit: float = Field(0.2, gt=0, le=10)


class ConfigureRequest(BaseModel):
    symbols: list[str] = Field(default=["000001.SZ", "AAPL"], min_length=1, max_length=50)
    interval: str = Field("1d", min_length=1, max_length=20)
    strategy: StrategyRequest = Field(default_factory=StrategyRequest)


def _simulator_error(exc: Exception) -> HTTPException:
    if isinstance(exc, MarketDataUnavailableError):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail="模拟器操作失败。")


@router.get("/snapshot")
async def snapshot() -> dict:
    from backend.services.trading import simulator as default_simulator

    return default_simulator.snapshot()


@router.post("/configure")
async def configure(request: ConfigureRequest) -> dict:
    from backend.services.trading import simulator

    try:
        simulator.configure(
            request.symbols,
            request.interval,
            StrategyConfig(**request.strategy.model_dump()),
        )
    except Exception as exc:
        raise _simulator_error(exc) from exc
    return simulator.snapshot()


@router.post("/start")
async def start() -> dict:
    from backend.services.trading import simulator

    try:
        return await simulator.start()
    except Exception as exc:
        raise _simulator_error(exc) from exc


@router.post("/pause")
async def pause() -> dict:
    from backend.services.trading import simulator

    return simulator.pause()


@router.post("/reset")
async def reset() -> dict:
    from backend.services.trading import simulator

    simulator.reset()
    return simulator.snapshot()
