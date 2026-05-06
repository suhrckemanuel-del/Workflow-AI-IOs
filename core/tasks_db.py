"""
AI-OS Tasks Database Layer
--------------------------
Tables for goals, tasks, daily_log, and checkins.
Safe to call init_tasks_db() on every startup (CREATE IF NOT EXISTS).
"""

import sqlite3
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "aios.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_tasks_db() -> None:
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS goals (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                slug        TEXT UNIQUE NOT NULL,
                title       TEXT NOT NULL,
                description TEXT,
                quarter     TEXT,
                status      TEXT DEFAULT 'active',
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                title            TEXT NOT NULL,
                goal_ref         INTEGER REFERENCES goals(id),
                due_date         DATE,
                status           TEXT DEFAULT 'pending',
                recurrence       TEXT,
                delegated_reason TEXT,
                skip_count       INTEGER DEFAULT 0,
                source           TEXT DEFAULT 'manual',
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at     TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_tasks_due_date
                ON tasks(due_date, status);

            CREATE TABLE IF NOT EXISTS daily_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                log_date   DATE NOT NULL,
                task_id    INTEGER REFERENCES tasks(id),
                outcome    TEXT NOT NULL,
                note       TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_daily_log_date
                ON daily_log(log_date DESC);

            CREATE TABLE IF NOT EXISTS checkins (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                checkin_date DATE NOT NULL,
                type         TEXT NOT NULL,
                responded    BOOLEAN DEFAULT 0,
                sent_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                responded_at TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_checkins_date
                ON checkins(checkin_date DESC);
        """)

        # Phase G: mirror tasks to Google Calendar. Safe to run on existing DBs.
        try:
            conn.execute("ALTER TABLE tasks ADD COLUMN calendar_event_id TEXT")
        except sqlite3.OperationalError:
            pass


# ── Goals ────────────────────────────────────────────────────────────────────

def upsert_goal(slug: str, title: str, description: str = "", quarter: str | None = None) -> dict:
    with _connect() as conn:
        conn.execute(
            """INSERT INTO goals (slug, title, description, quarter, updated_at)
               VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(slug) DO UPDATE SET
                   title       = excluded.title,
                   description = excluded.description,
                   quarter     = excluded.quarter,
                   updated_at  = CURRENT_TIMESTAMP""",
            (slug, title, description, quarter),
        )
        row = conn.execute("SELECT * FROM goals WHERE slug = ?", (slug,)).fetchone()
        return dict(row)


def get_goal_by_slug(slug: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM goals WHERE slug = ?", (slug,)).fetchone()
        return dict(row) if row else None


def list_goals() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM goals ORDER BY id ASC").fetchall()
        return [dict(r) for r in rows]


# ── Tasks ─────────────────────────────────────────────────────────────────────

def create_task(
    title: str,
    goal_ref: int | None = None,
    due_date: str | None = None,
    source: str = "manual",
    recurrence: str | None = None,
) -> dict:
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO tasks (title, goal_ref, due_date, source, recurrence)
               VALUES (?, ?, ?, ?, ?)""",
            (title, goal_ref, due_date, source, recurrence),
        )
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)


def get_tasks_for_date(date_str: str) -> list[dict]:
    """Return tasks due on date_str plus any still-pending tasks from before."""
    with _connect() as conn:
        rows = conn.execute(
            """SELECT t.*, g.slug AS goal_slug, g.title AS goal_title
               FROM tasks t
               LEFT JOIN goals g ON g.id = t.goal_ref
               WHERE t.status = 'pending'
                 AND (t.due_date = ? OR (t.due_date IS NOT NULL AND t.due_date < ?))
               ORDER BY t.due_date ASC, t.created_at ASC""",
            (date_str, date_str),
        ).fetchall()
        return [dict(r) for r in rows]


def update_task(task_id: int, **fields: Any) -> dict | None:
    allowed = {"status", "delegated_reason", "completed_at", "due_date", "recurrence", "skip_count", "goal_ref"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        with _connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            return dict(row) if row else None
    assignments = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [task_id]
    with _connect() as conn:
        conn.execute(f"UPDATE tasks SET {assignments} WHERE id = ?", values)
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row) if row else None


def update_task_calendar_event(task_id: int, event_id: str | None) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE tasks SET calendar_event_id = ? WHERE id = ?",
            (event_id, task_id),
        )


def get_task(task_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row) if row else None


# ── Daily Log ─────────────────────────────────────────────────────────────────

def create_daily_log(log_date: str, outcome: str, task_id: int | None = None, note: str = "") -> dict:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO daily_log (log_date, task_id, outcome, note) VALUES (?, ?, ?, ?)",
            (log_date, task_id, outcome, note),
        )
        row = conn.execute("SELECT * FROM daily_log WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)


def list_daily_log(log_date: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM daily_log WHERE log_date = ? ORDER BY created_at DESC",
            (log_date,),
        ).fetchall()
        return [dict(r) for r in rows]


# ── Checkins ──────────────────────────────────────────────────────────────────

def create_checkin(checkin_date: str, checkin_type: str) -> dict:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO checkins (checkin_date, type) VALUES (?, ?)",
            (checkin_date, checkin_type),
        )
        row = conn.execute("SELECT * FROM checkins WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)


def mark_checkin_responded(checkin_id: int) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE checkins SET responded = 1, responded_at = CURRENT_TIMESTAMP WHERE id = ?",
            (checkin_id,),
        )


def get_today_checkin(checkin_date: str, checkin_type: str) -> dict | None:
    """Return the most recent checkin of given type for the date, or None."""
    with _connect() as conn:
        row = conn.execute(
            """SELECT * FROM checkins
               WHERE checkin_date = ? AND type = ?
               ORDER BY sent_at DESC LIMIT 1""",
            (checkin_date, checkin_type),
        ).fetchone()
        return dict(row) if row else None


def get_weekly_log(start_date: str, end_date: str) -> list[dict]:
    """
    Return all daily_log rows between start_date and end_date (inclusive),
    joined to tasks and goals.
    Each row: {task_title, goal_title, outcome, note, log_date}
    """
    with _connect() as conn:
        rows = conn.execute(
            """SELECT
                   dl.log_date,
                   dl.outcome,
                   dl.note,
                   t.title  AS task_title,
                   g.title  AS goal_title
               FROM daily_log dl
               LEFT JOIN tasks t ON t.id = dl.task_id
               LEFT JOIN goals g ON g.id = t.goal_ref
               WHERE dl.log_date >= ? AND dl.log_date <= ?
               ORDER BY dl.log_date ASC, dl.id ASC""",
            (start_date, end_date),
        ).fetchall()
        return [dict(r) for r in rows]


def count_unresponded_streak(before_date: str, days: int = 2) -> int:
    """Count how many of the last `days` days have zero responded checkins."""
    with _connect() as conn:
        rows = conn.execute(
            """SELECT checkin_date, MAX(responded) AS any_responded
               FROM checkins
               WHERE checkin_date < ?
               GROUP BY checkin_date
               ORDER BY checkin_date DESC
               LIMIT ?""",
            (before_date, days),
        ).fetchall()
    if len(rows) < days:
        return 0
    return sum(1 for r in rows if not r["any_responded"])
