from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.manager import ConnectionManager

app = FastAPI(title="pulso-chat", version="0.2.0")
manager = ConnectionManager()

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def get_index():
    return FileResponse("static/index.html")


@app.get("/api/rooms")
async def get_rooms():
    return {"rooms": manager.list_rooms()}


@app.websocket("/ws/{room}")
async def websocket_endpoint(
    websocket: WebSocket,
    room: str,
    nickname: str = Query(default="Anônimo"),
):
    clean_room = room.strip().lower() or "geral"
    await manager.connect(websocket, clean_room, nickname)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "message":
                await manager.send_chat_message(
                    websocket,
                    clean_room,
                    str(data.get("text", "")),
                )
    except WebSocketDisconnect:
        await manager.disconnect(websocket, clean_room)
    except Exception:
        await manager.disconnect(websocket, clean_room)