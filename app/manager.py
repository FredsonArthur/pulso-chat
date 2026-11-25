from collections import defaultdict
from datetime import datetime, timezone
from fastapi import WebSocket

from app.storage import ChatStorage


class ConnectionManager:
    """Gerencia conexões ativas por sala/DM e presença global online."""

    def __init__(self, storage: ChatStorage) -> None:
        self.storage = storage
        # rooms[room][websocket] = username
        self.rooms: dict[str, dict[WebSocket, str]] = defaultdict(dict)
        # global_online[username] = set/count of active sockets
        self.global_online: dict[str, int] = defaultdict(int)

    def online_usernames(self) -> list[str]:
        return sorted([u for u, count in self.global_online.items() if count > 0])

    def room_online_usernames(self, room: str) -> list[str]:
        users = set(self.rooms.get(room, {}).values())
        return sorted(users)

    async def connect(self, websocket: WebSocket, room: str, username: str) -> None:
        await websocket.accept()
        clean_room = room.strip().lower()
        clean_user = username.strip().lower()

        self.storage.join_room(clean_room, clean_user)
        self.rooms[clean_room][websocket] = clean_user
        self.global_online[clean_user] += 1

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
                "username": clean_user,
                "room_online": self.room_online_usernames(clean_room),
                "global_online": self.online_usernames(),
                "timestamp": self._now(),
            },
        )

    async def disconnect(self, websocket: WebSocket, room: str) -> None:
        clean_room = room.strip().lower()
        clients = self.rooms.get(clean_room)
        if not clients or websocket not in clients:
            return

        username = clients.pop(websocket)
        if self.global_online[username] > 0:
            self.global_online[username] -= 1

        await self.broadcast(
            clean_room,
            {
                "type": "presence",
                "event": "leave",
                "room": clean_room,
                "username": username,
                "room_online": self.room_online_usernames(clean_room),
                "global_online": self.online_usernames(),
                "timestamp": self._now(),
            },
        )

    async def send_chat_message(self, websocket: WebSocket, room: str, text: str) -> None:
        clean_room = room.strip().lower()
        sender = self.rooms.get(clean_room, {}).get(websocket)
        if not sender:
            return

        clean_text = text.strip()[:1000]
        if not clean_text:
            return

        payload = self.storage.save_message(clean_room, sender, clean_text, self._now())
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