from collections import defaultdict
from datetime import datetime, timezone
from fastapi import WebSocket

from app.storage import ChatStorage


class ConnectionManager:
    """Gerencia conexões ativas, salas, presença e histórico persistido."""

    DEFAULT_ROOMS = ["geral", "dev", "aleatorio"]

    def __init__(self, storage: ChatStorage | None = None, default_rooms: list[str] | None = None) -> None:
        self.storage = storage or ChatStorage()
        base_rooms = default_rooms or self.DEFAULT_ROOMS
        self.storage.ensure_rooms(base_rooms)

        # rooms[room_name][websocket] = nickname
        self.rooms: dict[str, dict[WebSocket, str]] = defaultdict(dict)
        for room in self.storage.list_rooms(base_rooms):
            self.rooms[room] = {}

    def list_rooms(self) -> list[str]:
        active = set(self.rooms.keys())
        persisted = set(self.storage.list_rooms(self.DEFAULT_ROOMS))
        return sorted(active | persisted)

    def online_users(self, room: str) -> list[str]:
        users = set(self.rooms.get(room, {}).values())
        return sorted(users, key=str.lower)

    async def connect(self, websocket: WebSocket, room: str, nickname: str) -> None:
        await websocket.accept()
        clean_room = room.strip().lower() or "geral"
        clean_nick = nickname.strip()[:24] or "Anônimo"

        self.storage.ensure_rooms([clean_room])
        self.rooms[clean_room][websocket] = clean_nick

        history = self.storage.get_recent_messages(clean_room, limit=50)
        await websocket.send_json(
            {
                "type": "history",
                "room": clean_room,
                "messages": history,
            }
        )

        await self.broadcast(
            clean_room,
            {
                "type": "presence",
                "event": "join",
                "room": clean_room,
                "nickname": clean_nick,
                "online": self.online_users(clean_room),
                "rooms": self.list_rooms(),
                "timestamp": self._now(),
            },
        )

    async def disconnect(self, websocket: WebSocket, room: str) -> None:
        clean_room = room.strip().lower() or "geral"
        room_clients = self.rooms.get(clean_room)
        if not room_clients or websocket not in room_clients:
            return

        nickname = room_clients.pop(websocket)
        online = self.online_users(clean_room)

        await self.broadcast(
            clean_room,
            {
                "type": "presence",
                "event": "leave",
                "room": clean_room,
                "nickname": nickname,
                "online": online,
                "rooms": self.list_rooms(),
                "timestamp": self._now(),
            },
        )

    async def send_chat_message(self, websocket: WebSocket, room: str, text: str) -> None:
        clean_room = room.strip().lower() or "geral"
        sender = self.rooms.get(clean_room, {}).get(websocket, "Anônimo")
        clean_text = text.strip()[:1000]
        if not clean_text:
            return

        timestamp = self._now()
        payload = self.storage.save_message(clean_room, sender, clean_text, timestamp)
        await self.broadcast(clean_room, payload)

    async def broadcast(self, room: str, payload: dict) -> None:
        clients = list(self.rooms.get(room, {}).keys())
        stale: list[WebSocket] = []

        for client in clients:
            try:
                await client.send_json(payload)
            except Exception:
                stale.append(client)

        for client in stale:
            self.rooms.get(room, {}).pop(client, None)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).astimezone().strftime("%H:%M")