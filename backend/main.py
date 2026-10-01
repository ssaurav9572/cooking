from pathlib import Path
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from api import router

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

app = FastAPI(title="CookAI", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


@app.get("/app")
def application():
    return FileResponse(FRONTEND / "app.html")


@app.get("/cooking")
def cooking():
    return FileResponse(FRONTEND / "cooking.html")


@app.get("/import")
def recipe_import():
    return FileResponse(FRONTEND / "import.html")


@app.get("/health")
def health():
    return {"ok": True, "store": "memory", "mysql": "optional"}


@app.websocket("/ws/cooking/{session_id}")
async def cooking_ws(ws: WebSocket, session_id: int):
    await ws.accept()
    await ws.send_json({"session_id": session_id, "status": "ready"})
    try:
        while True:
            msg = await ws.receive_json()
            await ws.send_json({"echo": msg, "note": "vision frames stay ephemeral"})
    except Exception:
        return
