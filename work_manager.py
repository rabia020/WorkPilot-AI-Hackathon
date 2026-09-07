"""
work_manager.py
===============
Clean interface for the WorkPilot task / note / dashboard features.
Wraps the PostgreSQL CRUD methods already in memory_store.PostgresMemory
so that the FastAPI endpoints and Streamlit pages don't need to import
the full MemoryStore or worry about connection details.
"""

import json
import psycopg2
import psycopg2.extras
from datetime import datetime, date
from typing import Optional

from config import PG_CONFIG, get_connection


# ==========================================================
# AUTO-TABLE CREATION
# ==========================================================

def _ensure_tables():
    """Create tasks and notes tables if they don't exist yet."""
    conn = psycopg2.connect(**PG_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    "user"      TEXT NOT NULL,
                    title       TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    due_date    DATE,
                    priority    TEXT DEFAULT 'Medium',
                    completed   BOOLEAN DEFAULT FALSE,
                    created_at  TIMESTAMPTZ DEFAULT NOW(),
                    updated_at  TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks ("user", completed);
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks (due_date);
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    "user"      TEXT NOT NULL,
                    title       TEXT NOT NULL,
                    content     TEXT DEFAULT '',
                    created_at  TIMESTAMPTZ DEFAULT NOW(),
                    updated_at  TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_notes_user ON notes ("user");
            """)
        conn.commit()
        print("[work_manager] Tasks & notes tables verified.")
    except Exception as e:
        print(f"[work_manager] Failed to ensure tables: {e}")
    finally:
        conn.close()


# Run on module import so tables are always ready
_ensure_tables()


# ==========================================================
# HELPERS
# ==========================================================

def _get_conn():
    return get_connection()


def _row_to_dict(row):
    """Convert a RealDictRow to a plain dict, serialising dates."""
    if row is None:
        return {}
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, (datetime, date)):
            d[k] = v.isoformat()
    return d


def _rows_to_list(rows):
    return [_row_to_dict(r) for r in rows]


# ==========================================================
# TASKS
# ==========================================================

def create_task(
    user: str,
    title: str,
    description: str = "",
    due_date: str = None,
    priority: str = "Medium",
) -> dict:
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO tasks ("user", title, description, due_date, priority)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *;
                """,
                (user, title, description, due_date or None, priority),
            )
            result = _row_to_dict(cur.fetchone())
            conn.commit()
            return result
    finally:
        conn.close()


def get_tasks(user: str) -> list:
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT * FROM tasks
                WHERE "user" = %s
                ORDER BY
                    completed ASC,
                    CASE priority
                        WHEN 'High'   THEN 1
                        WHEN 'Medium' THEN 2
                        WHEN 'Low'    THEN 3
                        ELSE 4
                    END,
                    due_date ASC NULLS LAST;
                """,
                (user,),
            )
            return _rows_to_list(cur.fetchall())
    finally:
        conn.close()


def update_task(task_id: str, user: str, **kwargs) -> dict:
    allowed = {"title", "description", "due_date", "priority", "completed"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not updates:
        return {}

    # Build SET clause — "updated_at = NOW()" is literal SQL
    parts = []
    values = []
    for k, v in updates.items():
        parts.append(f'"{k}" = %s')
        values.append(v)
    parts.append('"updated_at" = NOW()')

    set_sql = ", ".join(parts)
    values.extend([task_id, user])

    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                UPDATE tasks SET {set_sql}
                WHERE id = %s AND "user" = %s
                RETURNING *;
                """,
                tuple(values),
            )
            result = _row_to_dict(cur.fetchone())
            conn.commit()
            return result
    finally:
        conn.close()


def delete_task(task_id: str, user: str) -> bool:
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'DELETE FROM tasks WHERE id = %s AND "user" = %s;',
                (task_id, user),
            )
            deleted = cur.rowcount > 0
            conn.commit()
            return deleted
    finally:
        conn.close()


def toggle_task(task_id: str, user: str) -> dict:
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                UPDATE tasks
                SET completed = NOT completed, updated_at = NOW()
                WHERE id = %s AND "user" = %s
                RETURNING *;
                """,
                (task_id, user),
            )
            result = _row_to_dict(cur.fetchone())
            conn.commit()
            return result
    finally:
        conn.close()


def get_task_stats(user: str) -> dict:
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*)                            AS total,
                    COUNT(*) FILTER (WHERE completed)   AS completed,
                    COUNT(*) FILTER (WHERE NOT completed) AS pending
                FROM tasks WHERE "user" = %s;
                """,
                (user,),
            )
            row = cur.fetchone()
            return {
                "total":     row[0] if row else 0,
                "completed": row[1] if row else 0,
                "pending":   row[2] if row else 0,
            }
    finally:
        conn.close()


# ==========================================================
# NOTES
# ==========================================================

def create_note(user: str, title: str, content: str = "") -> dict:
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO notes ("user", title, content)
                VALUES (%s, %s, %s)
                RETURNING *;
                """,
                (user, title, content),
            )
            result = _row_to_dict(cur.fetchone())
            conn.commit()
            return result
    finally:
        conn.close()


def get_notes(user: str) -> list:
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT * FROM notes
                WHERE "user" = %s
                ORDER BY updated_at DESC;
                """,
                (user,),
            )
            return _rows_to_list(cur.fetchall())
    finally:
        conn.close()


def update_note(note_id: str, user: str, **kwargs) -> dict:
    allowed = {"title", "content"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not updates:
        return {}

    parts = []
    values = []
    for k, v in updates.items():
        parts.append(f'"{k}" = %s')
        values.append(v)
    parts.append('"updated_at" = NOW()')

    set_sql = ", ".join(parts)
    values.extend([note_id, user])

    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                UPDATE notes SET {set_sql}
                WHERE id = %s AND "user" = %s
                RETURNING *;
                """,
                tuple(values),
            )
            result = _row_to_dict(cur.fetchone())
            conn.commit()
            return result
    finally:
        conn.close()


def delete_note(note_id: str, user: str) -> bool:
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'DELETE FROM notes WHERE id = %s AND "user" = %s;',
                (note_id, user),
            )
            deleted = cur.rowcount > 0
            conn.commit()
            return deleted
    finally:
        conn.close()


# ==========================================================
# DASHBOARD AGGREGATOR
# ==========================================================

def get_dashboard_stats(user: str) -> dict:
    """Aggregate stats + recent items for the dashboard view."""
    stats  = get_task_stats(user)
    tasks  = get_tasks(user)
    notes  = get_notes(user)

    # Priority breakdown for pending tasks
    pending = [t for t in tasks if not t.get("completed")]
    priority_counts = {"High": 0, "Medium": 0, "Low": 0}
    for t in pending:
        p = t.get("priority", "Medium")
        priority_counts[p] = priority_counts.get(p, 0) + 1

    return {
        "task_stats":     stats,
        "recent_tasks":   tasks[:5],
        "recent_notes":   notes[:5],
        "pending_count":  len(pending),
        "priority_counts": priority_counts,
    }


# ==========================================================
# WORK CONTEXT (for AI agents)
# ==========================================================

def get_work_context(user: str) -> str:
    """
    Build a text summary of the user's current work state.
    Used by the Daily Planner Agent and Ask AI to inject context.
    Now includes projects for richer work awareness.
    """
    tasks = get_tasks(user)
    notes = get_notes(user)

    lines = [f"=== WORK CONTEXT for {user} ===\n"]

    # Tasks
    pending = [t for t in tasks if not t.get("completed")]
    done    = [t for t in tasks if t.get("completed")]

    lines.append(f"TASKS ({len(pending)} pending, {len(done)} completed):")
    for t in pending:
        due = t.get("due_date", "no due date")
        lines.append(
            f"  [{t['priority']}] {t['title']} — due {due}"
            + (f" — {t['description']}" if t.get("description") else "")
        )
    if not pending:
        lines.append("  (no pending tasks)")

    # Notes
    lines.append(f"\nNOTES ({len(notes)} total):")
    for n in notes[:10]:
        preview = (n["content"] or "")[:120]
        lines.append(f"  \u2022 {n['title']}: {preview}")
    if not notes:
        lines.append("  (no notes)")

    # Projects (if available)
    try:
        import project_manager
        projects = project_manager.get_projects(user)
        if projects:
            lines.append(f"\nPROJECTS ({len(projects)} total):")
            for p in projects[:5]:
                pname = p.get("name", "Untitled")
                pdesc = p.get("description", "")
                pstatus = p.get("status", "active")
                lines.append(f"  \U0001f4c1 {pname} [{pstatus}]: {pdesc[:100] if pdesc else 'No description'}")
        else:
            lines.append("\nPROJECTS: (none)")
    except Exception:
        pass  # Projects are optional

    lines.append("\n=== END WORK CONTEXT ===")
    return "\n".join(lines)
