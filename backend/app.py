from pathlib import Path

from backend.routes.chat import router as chat_router
from backend.routes.market import router as market_router
from backend.routes.trading import router as trading_router
from fastapi import FastAPI
from fastapi import WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"

app = FastAPI(title="自动量化交易模拟器", version="1.0.0")
app.include_router(chat_router)
app.include_router(trading_router)
app.include_router(market_router)


@app.websocket("/ws/market")
async def market_websocket_alias(websocket: WebSocket):
    from backend.routes.market import market_socket

    await market_socket(websocket)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.mount("/css", StaticFiles(directory=FRONTEND_DIR / "css"), name="css")
app.mount("/js", StaticFiles(directory=FRONTEND_DIR / "js"), name="js")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")
