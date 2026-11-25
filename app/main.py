from fastapi import FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.auth import SessionStore
from app.manager import ConnectionManager
from app.storage import ChatStorage

app = FastAPI(title="pulso-chat", version="0.4.0")
storage = ChatStorage()
sessions = SessionStore()
manager = ConnectionManager(storage=storage)

app.mount("/static", StaticFiles(directory="static"), name="static")


class AuthPayload(BaseModel):
    username: str
    password: str
    display_name: str | None = None


class CreateRoomPayload(BaseModel):
    name: str


class DmPayload(BaseModel):
    target_username: str


def _require_user(authorization: str | None) -> str:
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    user = sessions.get_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada.")
    return user


@app.get("/")
async def get_index():
    return FileResponse("static/index.html")


@app.post("/api/register")
async def register(payload: AuthPayload):
    ok, result = storage.register_user(payload.username, payload.password, payload.display_name)
    if not ok:
        raise HTTPException(status_code=400, detail=result)
    token = sessions.create_session(result)
    return {"token": token, "username": result}


@app.post("/api/login")
async def login(payload: AuthPayload):
    user = storage.authenticate_user(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Usuário ou senha inválidos.")
    token = sessions.create_session(user)
    return {"token": token, "username": user}


@app.get("/api/lobby")
async def get_lobby(authorization: str | None = Header(default=None)):
    user = _require_user(authorization)
    return {
        "username": user,
        "my_rooms": storage.user_rooms(user),
        "users": storage.list_users(exclude_user=user),
        "online_users": manager.online_usernames(),
    }


@app.post("/api/rooms")
async def create_room(payload: CreateRoomPayload, authorization: str | None = Header(default=None)):
    user = _require_user(authorization)
    ok, result = storage.create_room(payload.name, user)
    if not ok:
        raise HTTPException(status_code=400, detail=result)
    return {"room": result, "my_rooms": storage.user_rooms(user)}


@app.post("/api/dm")
async def open_dm(payload: DmPayload, authorization: str | None = Header(default=None)):
    user = _require_user(authorization)
    dm_room = storage.get_or_create_dm(user, payload.target_username)
    if not dm_room:
        raise HTTPException(status_code=400, detail="Usuário de destino inválido.")
    return {"room": dm_room, "my_rooms": storage.user_rooms(user)}


@app.websocket("/ws/{room}")
async def websocket_endpoint(
    websocket: WebSocket,
    room: str,
    token: str = Query(default=""),
):
    user = sessions.get_user(token)
    if not user:
        await websocket.close(code=4001)
        return

    clean_room = room.strip().lower()
    await manager.connect(websocket, clean_room, user)
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