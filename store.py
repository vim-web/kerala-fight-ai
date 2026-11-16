"""Local history, kept in one SQLite file next to the app.

Standard library only, no server, no account: the file never leaves the
laptop. `main.py` writes a turn after every real reply and reads it back when
someone reopens an old conversation. Every write is best-effort there, so a
locked or corrupt database can never break a chat.
"""

import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent / "data" / "sparring.db"
PREVIEW = 90  # characters of the last message shown in the list

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id         TEXT PRIMARY KEY,
    mode       TEXT NOT NULL,
    scenario   TEXT NOT NULL DEFAULT '',
    lang       TEXT NOT NULL DEFAULT 'en',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role       TEXT NOT NULL,
    text       TEXT NOT NULL,
    anger      INTEGER NOT NULL DEFAULT 0,
    delta      INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);
"""


def _preview(text: str) -> str:
    one_line = " ".join((text or "").split())
    return one_line if len(one_line) <= PREVIEW else one_line[: PREVIEW - 1] + "…"


def _streak(deltas: list) -> int:
    """Turns in a row, from the end, that did not make things worse."""
    run = 0
    for change in reversed(deltas):
        if change > 0:
            break
        run += 1
    return run


class Store:
    """One file, one connection per call, no ORM."""

    def __init__(self, path=None):
        self.path = str(path or DEFAULT_PATH)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as db:
            db.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        db = sqlite3.connect(self.path, timeout=5.0)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    # ---------- writing ----------

    def add_turn(
        self,
        sid: str,
        *,
        mode: str,
        scenario: str = "",
        lang: str = "en",
        user_text: str,
        reply: str,
        anger: int = 0,
        delta: int = 0,
    ) -> None:
        """Save one exchange. A retried message replaces itself, never duplicates."""
        user_text = (user_text or "").strip()[:2000]
        reply = (reply or "").strip()[:4000]
        if not sid or not user_text:
            return
        now = time.time()
        with self._conn() as db:
            db.execute(
                "INSERT INTO sessions (id, mode, scenario, lang, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET updated_at = excluded.updated_at",
                (sid, mode, scenario or "", lang or "en", now, now),
            )
            last = db.execute(
                "SELECT id, role, text FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT 1",
                (sid,),
            ).fetchone()
            if last and last["role"] == "user" and last["text"] == user_text:
                db.execute(
                    "UPDATE messages SET anger = ?, delta = ?, created_at = ? WHERE id = ?",
                    (anger, delta, now, last["id"]),
                )
            else:
                db.execute(
                    "INSERT INTO messages (session_id, role, text, anger, delta, created_at) "
                    "VALUES (?, 'user', ?, ?, ?, ?)",
                    (sid, user_text, anger, delta, now),
                )
            if reply:
                db.execute(
                    "INSERT INTO messages (session_id, role, text, anger, delta, created_at) "
                    "VALUES (?, 'ai', ?, ?, 0, ?)",
                    (sid, reply, anger, now),
                )

    def delete(self, sid: str) -> int:
        with self._conn() as db:
            db.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
            return db.execute("DELETE FROM sessions WHERE id = ?", (sid,)).rowcount

    def clear(self) -> int:
        """Delete everything and report how many sessions went."""
        with self._conn() as db:
            count = db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            db.execute("DELETE FROM messages")
            db.execute("DELETE FROM sessions")
        return count

    # ---------- reading ----------

    def get(self, sid: str):
        """One session with its messages, or None."""
        with self._conn() as db:
            row = db.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
            if not row:
                return None
            rows = db.execute(
                "SELECT role, text, anger, delta, created_at FROM messages "
                "WHERE session_id = ? ORDER BY id",
                (sid,),
            ).fetchall()
        sessions = dict(row)
        messages = [dict(m) for m in rows]
        deltas = [m["delta"] for m in messages if m["role"] == "user"]
        sessions["messages"] = messages
        sessions["turns"] = len(deltas)
        sessions["streak"] = _streak(deltas)
        sessions["anger"] = messages[-1]["anger"] if messages else 0
        return sessions

    def list(self, limit: int = 50) -> list:
        """Newest first, with just enough for a picker list."""
        with self._conn() as db:
            rows = db.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
            out = []
            for row in rows:
                deltas = [
                    r["delta"]
                    for r in db.execute(
                        "SELECT delta FROM messages WHERE session_id = ? AND role = 'user' "
                        "ORDER BY id",
                        (row["id"],),
                    )
                ]
                last = db.execute(
                    "SELECT text, anger FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT 1",
                    (row["id"],),
                ).fetchone()
                item = dict(row)
                item["turns"] = len(deltas)
                item["streak"] = _streak(deltas)
                item["anger"] = last["anger"] if last else 0
                item["preview"] = _preview(last["text"]) if last else ""
                out.append(item)
        return out

    def state(self, sid: str):
        """Anger and turn count for resuming after the server restarted."""
        with self._conn() as db:
            row = db.execute(
                "SELECT anger FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT 1",
                (sid,),
            ).fetchone()
            if not row:
                return None
            turns = db.execute(
                "SELECT COUNT(*) FROM messages WHERE session_id = ? AND role = 'user'",
                (sid,),
            ).fetchone()[0]
        return {"anger": row["anger"], "turns": turns}

    def stats(self) -> dict:
        with self._conn() as db:
            sessions = db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            turns = db.execute("SELECT COUNT(*) FROM messages WHERE role = 'user'").fetchone()[0]
            rows = db.execute(
                "SELECT session_id, delta FROM messages WHERE role = 'user' "
                "ORDER BY session_id, id"
            ).fetchall()
        best, run, current = 0, 0, None
        for row in rows:
            if row["session_id"] != current:
                current, run = row["session_id"], 0
            run = run + 1 if row["delta"] <= 0 else 0
            best = max(best, run)
        return {"sessions": sessions, "turns": turns, "best_streak": best}

    def export(self) -> dict:
        """Everything, as one JSON-able dict the user can keep or delete."""
        with self._conn() as db:
            ids = [r["id"] for r in db.execute("SELECT id FROM sessions ORDER BY created_at")]
        sessions = [self.get(sid) for sid in ids]
        return {
            "app": "Sparring AI",
            "version": 1,
            "exported_at": time.time(),
            "sessions": [s for s in sessions if s],
        }
