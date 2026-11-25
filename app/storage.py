import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.auth import hash_password, verify_password


class ChatStorage:
    """Persistência em SQLite para usuários, salas, participações e mensagens."""

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
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rooms (
                    name TEXT PRIMARY KEY,
                    is_dm INTEGER NOT NULL DEFAULT 0,
                    created_by TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS room_members (
                    room TEXT NOT NULL,
                    username TEXT NOT NULL,
                    joined_at TEXT NOT NULL,
                    PRIMARY KEY (room, username)
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

    def register_user(self, username: str, password: str, display_name: str | None = None) -> tuple[bool, str]:
        clean_user = username.strip().lower()
        clean_display = (display_name or username).strip()[:24] or clean_user

        if len(clean_user) < 3 or len(clean_user) > 20:
            return False, "Usuário deve ter entre 3 e 20 caracteres."
        if not clean_user.replace("_", "").isalnum():
            return False, "Use apenas letras, números ou underline no usuário."
        if len(password) < 4:
            return False, "A senha deve ter pelo menos 4 caracteres."

        now = datetime.now(timezone.utc).isoformat()
        pw_hash = hash_password(password)

        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO users (username, display_name, password_hash, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (clean_user, clean_display, pw_hash, now),
                )
                # Entra automaticamente na sala 'geral' ao criar conta
                conn.execute(
                    "INSERT OR IGNORE INTO rooms (name, is_dm, created_by, created_at) VALUES ('geral', 0, 'system', ?)",
                    (now,),
                )
                conn.execute(
                    "INSERT OR IGNORE INTO room_members (room, username, joined_at) VALUES ('geral', ?, ?)",
                    (clean_user, now),
                )
                conn.commit()
            return True, clean_user
        except sqlite3.IntegrityError:
            return False, "Esse nome de usuário já existe."

    def authenticate_user(self, username: str, password: str) -> str | None:
        clean_user = username.strip().lower()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT username, password_hash FROM users WHERE username = ?",
                (clean_user,),
            ).fetchone()
        if not row or not verify_password(password, row["password_hash"]):
            return None
        return row["username"]

    def list_users(self, exclude_user: str | None = None) -> list[dict[str, str]]:
        with self._connect() as conn:
            if exclude_user:
                rows = conn.execute(
                    "SELECT username, display_name FROM users WHERE username != ? ORDER BY username ASC",
                    (exclude_user.lower(),),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT username, display_name FROM users ORDER BY username ASC"
                ).fetchall()
        return [{"username": r["username"], "display_name": r["display_name"]} for r in rows]

    def create_room(self, room_name: str, creator: str) -> tuple[bool, str]:
        clean_room = "-".join(room_name.strip().lower().split())
        if len(clean_room) < 2 or len(clean_room) > 30:
            return False, "Nome da sala deve ter entre 2 e 30 caracteres."
        if clean_room.startswith("dm-"):
            return False, "Nome reservado para conversas diretas."

        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            existing = conn.execute("SELECT name FROM rooms WHERE name = ?", (clean_room,)).fetchone()
            if existing:
                conn.execute(
                    "INSERT OR IGNORE INTO room_members (room, username, joined_at) VALUES (?, ?, ?)",
                    (clean_room, creator.lower(), now),
                )
                conn.commit()
                return True, clean_room

            conn.execute(
                "INSERT INTO rooms (name, is_dm, created_by, created_at) VALUES (?, 0, ?, ?)",
                (clean_room, creator.lower(), now),
            )
            conn.execute(
                "INSERT OR IGNORE INTO room_members (room, username, joined_at) VALUES (?, ?, ?)",
                (clean_room, creator.lower(), now),
            )
            conn.commit()
        return True, clean_room

    def join_room(self, room: str, username: str) -> None:
        clean_room = room.strip().lower()
        if not clean_room:
            return
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO rooms (name, is_dm, created_by, created_at) VALUES (?, 0, ?, ?)",
                (clean_room, username.lower(), now),
            )
            conn.execute(
                "INSERT OR IGNORE INTO room_members (room, username, joined_at) VALUES (?, ?, ?)",
                (clean_room, username.lower(), now),
            )
            conn.commit()

    def get_or_create_dm(self, user_a: str, user_b: str) -> str | None:
        a = user_a.strip().lower()
        b = user_b.strip().lower()
        if not a or not b or a == b:
            return None

        with self._connect() as conn:
            target = conn.execute("SELECT username FROM users WHERE username = ?", (b,)).fetchone()
            if not target:
                return None

            pair = sorted([a, b])
            dm_room = f"dm-{pair[0]}-{pair[1]}"
            now = datetime.now(timezone.utc).isoformat()

            conn.execute(
                "INSERT OR IGNORE INTO rooms (name, is_dm, created_by, created_at) VALUES (?, 1, ?, ?)",
                (dm_room, a, now),
            )
            conn.execute(
                "INSERT OR IGNORE INTO room_members (room, username, joined_at) VALUES (?, ?, ?)",
                (dm_room, a, now),
            )
            conn.execute(
                "INSERT OR IGNORE INTO room_members (room, username, joined_at) VALUES (?, ?, ?)",
                (dm_room, b, now),
            )
            conn.commit()
        return dm_room

    def user_rooms(self, username: str) -> list[dict[str, Any]]:
        clean_user = username.strip().lower()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT r.name, r.is_dm
                FROM rooms r
                INNER JOIN room_members m ON m.room = r.name
                WHERE m.username = ?
                ORDER BY r.is_dm ASC, r.name ASC
                """,
                (clean_user,),
            ).fetchall()

        result: list[dict[str, Any]] = []
        for r in rows:
            name = r["name"]
            is_dm = bool(r["is_dm"])
            label = name
            if is_dm and name.startswith("dm-"):
                parts = name.split("-")
                if len(parts) == 3:
                    other = parts[1] if parts[2] == clean_user else parts[2]
                    label = f"@{other}"
            result.append({"room": name, "label": label, "is_dm": is_dm})
        return result

    def is_member(self, room: str, username: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM room_members WHERE room = ? AND username = ?",
                (room.strip().lower(), username.strip().lower()),
            ).fetchone()
        return row is not None

    def save_message(self, room: str, sender: str, text: str, timestamp: str) -> dict[str, Any]:
        clean_room = room.strip().lower()
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO messages (room, sender, text, timestamp, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (clean_room, sender.lower(), text, timestamp, now),
            )
            msg_id = cursor.lastrowid
            conn.commit()

        return {
            "id": msg_id,
            "type": "message",
            "room": clean_room,
            "sender": sender.lower(),
            "text": text,
            "timestamp": timestamp,
        }

    def get_recent_messages(self, room: str, limit: int = 50) -> list[dict[str, Any]]:
        clean_room = room.strip().lower()
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

        return [
            {
                "id": r["id"],
                "type": "message",
                "room": r["room"],
                "sender": r["sender"],
                "text": r["text"],
                "timestamp": r["timestamp"],
            }
            for r in reversed(rows)
        ]