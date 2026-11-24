from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol


class MarketDataUnavailableError(RuntimeError):
    """Raised when a real market data provider has not been configured."""


class SimulatorState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"


class MarketDataProvider(Protocol):
    async def latest(self, symbols: list[str]) -> list[dict]:
        ...

    async def history(self, symbol: str, interval: str, limit: int) -> list[dict]:
        ...


@dataclass
class StrategyConfig:
    name: str = "双均线趋势策略"
    fast_period: int = 20
    slow_period: int = 60
    position_size: float = 0.25
    stop_loss: float = 0.08
    take_profit: float = 0.2


@dataclass
class Account:
    initial_cash: float = 1_000_000.0
    cash: float = 1_000_000.0
    equity: float = 1_000_000.0
    day_pnl: float = 0.0
    total_return: float = 0.0
    max_drawdown: float = 0.0


@dataclass
class Position:
    symbol: str
    quantity: int
    average_price: float
    market_value: float = 0.0
    unrealized_pnl: float = 0.0


@dataclass
class Simulator:
    provider: MarketDataProvider | None = None
    state: SimulatorState = SimulatorState.IDLE
    symbols: list[str] = field(default_factory=lambda: ["000001.SZ", "AAPL"])
    interval: str = "1d"
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    account: Account = field(default_factory=Account)
    positions: list[Position] = field(default_factory=list)
    trades: list[dict] = field(default_factory=list)
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def snapshot(self) -> dict:
        return {
            "state": self.state.value,
            "symbols": self.symbols,
            "interval": self.interval,
            "strategy": self.strategy.__dict__,
            "account": self.account.__dict__,
            "positions": [position.__dict__ for position in self.positions],
            "trades": self.trades[-20:],
            "updated_at": self.updated_at.isoformat(),
            "market_data_configured": self.provider is not None,
        }

    def configure(self, symbols: list[str], interval: str, strategy: StrategyConfig) -> None:
        if not symbols:
            raise ValueError("至少需要配置一个交易品种。")
        if strategy.fast_period >= strategy.slow_period:
            raise ValueError("短周期必须小于长周期。")
        if not 0 < strategy.position_size <= 1:
            raise ValueError("单品种仓位比例必须在 0 到 1 之间。")
        self.symbols = symbols
        self.interval = interval
        self.strategy = strategy
        self.updated_at = datetime.now(timezone.utc)

    def reset(self) -> None:
        self.state = SimulatorState.IDLE
        self.account = Account()
        self.positions.clear()
        self.trades.clear()
        self.updated_at = datetime.now(timezone.utc)

    async def start(self) -> dict:
        if self.provider is None:
            raise MarketDataUnavailableError("尚未配置真实行情服务，无法启动自动交易。")
        self.state = SimulatorState.RUNNING
        self.updated_at = datetime.now(timezone.utc)
        return self.snapshot()

    def pause(self) -> dict:
        self.state = SimulatorState.PAUSED
        self.updated_at = datetime.now(timezone.utc)
        return self.snapshot()


simulator = Simulator()
