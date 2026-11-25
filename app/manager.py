from collections import defaultdict
from datetime import datetime, timezone
from fastapi import WebSocket


class ConnectionManager:
    """Gerencia conexões ativas, salas e presença online/offline em memória."""

    def __init__(self, default_rooms: list[str] | None = None) -> None:
        # rooms[room_name][websocket] = nickname
        self.rooms: dict[str, dict[WebSocket, str]] = defaultdict(dict)
        for room in (default_rooms or ["geral", "dev", "aleatorio"]):
            self.rooms[room] = {}

    def list_rooms(self) -> list[str]:
        return sorted(self.rooms.keys())

    def online_users(self, room: str) -> list[str]:
        users = set(self.rooms.get(room, {}).values())
        return sorted(users, key=str.lower)

    async def connect(self, websocket: WebSocket, room: str, nickname: str) -> None:
        await websocket.accept()
        clean_room = room.strip().lower() or "geral"
        clean_nick = nickname.strip()[:24] or "Anônimo"

        self.rooms[clean_room][websocket] = clean_nick

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
        # Mantém salas padrão mesmo vazias; remove salas extras vazias
        if clean_room not in {"geral", "dev", "aleatorio"} and not room_clients:
            del self.rooms[clean_room]
            online = []
        else:
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
        clean_text = text.strip()
        if not clean_text:
            return

        await self.broadcast(
            clean_room,
            {
                "type": "message",
                "room": clean_room,
                "sender": sender,
                "text": clean_text[:1000],
                "timestamp": self._now(),
            },
        )

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