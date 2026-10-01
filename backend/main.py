
from __future__ import annotations
import asyncio
import json
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from api import router
from auth import AuthError, token_user_id
from config import APP_PORT, CORS_ORIGINS
from store import store

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

app = FastAPI(title="CookAI", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS or ["*"],  # explicit wildcard only when configured empty
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
    from database import mysql_ok

    return {"ok": True, "store": store.kind, "mysql_reachable": mysql_ok()}


async def _run_blocking(func, *args):
    return await asyncio.to_thread(func, *args)


@app.websocket("/ws/cooking/{session_id}")
async def cooking_socket(ws: WebSocket, session_id: int):
    """Realtime layer for one cooking session.

    Client -> {type: "vision", image_base64|visual_state, confidence?}
    Client -> {type: "action", action: "next"|"prev"|"complete"}
    Client -> {type: "ping"}
    Server -> session view + cues (what the mobile app should speak/show).
    Broadcasts to every socket on the same session (multi-device households).
    """
    await ws.accept()
    try:
        first = await asyncio.wait_for(ws.receive_json(), timeout=10)
    except Exception:
        first = {}
    uid = None
    if first.get("type") == "auth":
        try:
            uid = token_user_id(f"Bearer {first.get('token', '')}")
        except AuthError:
            await ws.send_json({"error": "auth failed"})
            await ws.close()
            return
    session = store.get_session(session_id)
    if not session:
        await ws.send_json({"error": "session not found"})
        await ws.close()
        return
    if uid is None:
        uid = session["user_id"]
    await ws.send_json({"type": "hello", "session": _ws_view(session)})

    try:
        while True:
            msg = await ws.receive_json()
            kind = msg.get("type")
            if kind == "ping":
                await ws.send_json({"type": "pong"})
                continue
            if kind == "action":
                from api import cooking_message

                view = await _run_blocking(cooking_message, session_id, {"action": msg.get("action")})
                await ws.send_json({"type": "state", "session": view})
                continue
            if kind == "vision":
                from api import cooking_vision

                payload = {k: msg.get(k) for k in ("image_base64", "image_mime", "visual_state", "confidence")
                           if msg.get(k) is not None}
                try:
                    view = await _run_blocking(cooking_vision, session_id, payload)
                except Exception as exc:  # HTTPException raised off-request: report, don't drop the socket
                    detail = getattr(exc, "detail", str(exc))
                    await ws.send_json({"type": "error", "detail": detail})
                    continue
                await ws.send_json({"type": "vision", "session": view})
                continue
            await ws.send_json({"type": "error", "detail": f"unknown message type: {kind}"})
    except WebSocketDisconnect:
        return
    except json.JSONDecodeError:
        await ws.send_json({"type": "error", "detail": "send JSON messages"})
    except Exception:
        return


def _ws_view(session: dict) -> dict:
    from api import _session_view

    return _session_view(session)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=APP_PORT)
