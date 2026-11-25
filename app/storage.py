import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ChatStorage:
    """Persistência leve de salas e mensagens em SQLite."""

    def __init__(self, db_path: str = "pulso_chat.db") -> None:
        self.db_path = Path(db_path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rooms (
                    name TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    text TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_room_id
                ON messages (room, id DESC)
                """
            )
            conn.commit()

    def ensure_rooms(self, rooms: list[str]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            for room in rooms:
                clean = room.strip().lower()
                if clean:
                    conn.execute(
                        "INSERT OR IGNORE INTO rooms (name, created_at) VALUES (?, ?)",
                        (clean, now),
                    )
            conn.commit()

    def list_rooms(self, fallback: list[str] | None = None) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT name FROM rooms ORDER BY name ASC").fetchall()
        names = [row["name"] for row in rows]
        if names:
            return names
        return sorted(fallback or ["geral", "dev", "aleatorio"])

    def save_message(self, room: str, sender: str, text: str, timestamp: str) -> dict[str, Any]:
        clean_room = room.strip().lower() or "geral"
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO rooms (name, created_at) VALUES (?, ?)",
                (clean_room, now),
            )
            cursor = conn.execute(
                """
                INSERT INTO messages (room, sender, text, timestamp, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (clean_room, sender, text, timestamp, now),
            )
            msg_id = cursor.lastrowid
            conn.commit()

        return {
            "id": msg_id,
            "type": "message",
            "room": clean_room,
            "sender": sender,
            "text": text,
            "timestamp": timestamp,
        }

    def get_recent_messages(self, room: str, limit: int = 50) -> list[dict[str, Any]]:
        clean_room = room.strip().lower() or "geral"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, room, sender, text, timestamp
                FROM messages
                WHERE room = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (clean_room, limit),
            ).fetchall()

        ordered = list(reversed(rows))
        return [
            {
                "id": row["id"],
                "type": "message",
                "room": row["room"],
                "sender": row["sender"],
                "text": row["text"],
                "timestamp": row["timestamp"],
            }
            for row in ordered
        ]