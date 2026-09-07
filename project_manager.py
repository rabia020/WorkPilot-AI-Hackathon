"""
project_manager.py
==================
WorkPilot AI — Projects Management

Projects are a first-class concept that lets users organize work
around meaningful goals. A project connects tasks, notes, emails,
and AI actions into a unified context.
"""

import psycopg2
import psycopg2.extras
from datetime import datetime, date
from typing import Optional

from config import get_connection


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
# AUTO-TABLE CREATION
# ==========================================================

def _ensure_tables():
    """Create projects table and add project_id to tasks/notes if missing."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            # Projects table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    "user"      TEXT NOT NULL,
                    name        TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    color       TEXT DEFAULT '#8f75ca',
                    status      TEXT DEFAULT 'active',
                    created_at  TIMESTAMPTZ DEFAULT NOW(),
                    updated_at  TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_projects_user
                ON projects ("user", status);
            """)

            # Add project_id to tasks if not present
            cur.execute("""
                ALTER TABLE tasks
                ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES projects(id) ON DELETE SET NULL;
            """)

            # Add project_id to notes if not present
            cur.execute("""
                ALTER TABLE notes
                ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES projects(id) ON DELETE SET NULL;
            """)

        conn.commit()
        print("[project_manager] Projects table verified, FK columns ensured.")
    except Exception as e:
        print(f"[project_manager] Failed to ensure tables: {e}")
    finally:
        conn.close()


# Run on import so tables are always ready
_ensure_tables()


# ==========================================================
# PROJECTS CRUD
# ==========================================================

def create_project(
    user: str,
    name: str,
    description: str = "",
    color: str = "#8f75ca",
) -> dict:
    """Create a new project for the user."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO projects ("user", name, description, color)
                VALUES (%s, %s, %s, %s)
                RETURNING *;
                """,
                (user, name, description, color),
            )
            result = _row_to_dict(cur.fetchone())
            conn.commit()
            return result
    finally:
        conn.close()


def get_projects(user: str, status: str = None) -> list:
    """Get all projects for the user, optionally filtered by status."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if status:
                cur.execute(
                    """
                    SELECT * FROM projects
                    WHERE "user" = %s AND status = %s
                    ORDER BY updated_at DESC;
                    """,
                    (user, status),
                )
            else:
                cur.execute(
                    """
                    SELECT * FROM projects
                    WHERE "user" = %s
                    ORDER BY updated_at DESC;
                    """,
                    (user,),
                )
            return _rows_to_list(cur.fetchall())
    finally:
        conn.close()


def get_project(project_id: str, user: str) -> dict:
    """Get a single project by ID."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT * FROM projects
                WHERE id = %s AND "user" = %s;
                """,
                (project_id, user),
            )
            row = cur.fetchone()
            return _row_to_dict(row) if row else {}
    finally:
        conn.close()


def update_project(project_id: str, user: str, **kwargs) -> dict:
    """Update a project's fields."""
    allowed = {"name", "description", "color", "status"}
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
    values.extend([project_id, user])

    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                UPDATE projects SET {set_sql}
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


def delete_project(project_id: str, user: str) -> bool:
    """Delete a project. Tasks/notes have ON DELETE SET NULL for project_id."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'DELETE FROM projects WHERE id = %s AND "user" = %s;',
                (project_id, user),
            )
            deleted = cur.rowcount > 0
            conn.commit()
            return deleted
    finally:
        conn.close()


# ==========================================================
# PROJECT CONTEXT
# ==========================================================

def get_project_context(project_id: str, user: str) -> dict:
    """
    Get unified context for a project: the project itself plus
    all linked tasks and notes.
    """
    project = get_project(project_id, user)
    if not project:
        return {}

    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Tasks linked to this project
            cur.execute(
                """
                SELECT * FROM tasks
                WHERE project_id = %s AND "user" = %s
                ORDER BY completed ASC,
                    CASE priority
                        WHEN 'High' THEN 1
                        WHEN 'Medium' THEN 2
                        WHEN 'Low' THEN 3
                        ELSE 4
                    END,
                    due_date ASC NULLS LAST;
                """,
                (project_id, user),
            )
            tasks = _rows_to_list(cur.fetchall())

            # Notes linked to this project
            cur.execute(
                """
                SELECT * FROM notes
                WHERE project_id = %s AND "user" = %s
                ORDER BY updated_at DESC;
                """,
                (project_id, user),
            )
            notes = _rows_to_list(cur.fetchall())

        return {
            **project,
            "tasks": tasks,
            "notes": notes,
            "task_count": len(tasks),
            "note_count": len(notes),
            "completed_tasks": sum(1 for t in tasks if t.get("completed")),
            "pending_tasks": sum(1 for t in tasks if not t.get("completed")),
        }
    finally:
        conn.close()


def get_all_project_contexts(user: str) -> list:
    """
    Get lightweight context for all active projects:
    project info + task/note counts.
    """
    projects = get_projects(user, status="active")
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            for proj in projects:
                cur.execute(
                    """
                    SELECT
                        COUNT(*) FILTER (WHERE NOT completed) AS pending,
                        COUNT(*) AS total
                    FROM tasks
                    WHERE project_id = %s AND "user" = %s;
                    """,
                    (proj["id"], user),
                )
                stats = cur.fetchone()
                proj["pending_tasks"] = stats["pending"] if stats else 0
                proj["total_tasks"] = stats["total"] if stats else 0

        return projects
    finally:
        conn.close()


# ==========================================================
# LINK TASKS / NOTES TO PROJECTS
# ==========================================================

def link_task_to_project(task_id: str, project_id: str, user: str) -> bool:
    """Associate a task with a project."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE tasks SET project_id = %s, updated_at = NOW()
                WHERE id = %s AND "user" = %s;
                """,
                (project_id, task_id, user),
            )
            updated = cur.rowcount > 0
            conn.commit()
            return updated
    finally:
        conn.close()


def link_note_to_project(note_id: str, project_id: str, user: str) -> bool:
    """Associate a note with a project."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE notes SET project_id = %s, updated_at = NOW()
                WHERE id = %s AND "user" = %s;
                """,
                (project_id, note_id, user),
            )
            updated = cur.rowcount > 0
            conn.commit()
            return updated
    finally:
        conn.close()


def unlink_task_from_project(task_id: str, user: str) -> bool:
    """Remove a task's project association."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE tasks SET project_id = NULL, updated_at = NOW()
                WHERE id = %s AND "user" = %s;
                """,
                (task_id, user),
            )
            updated = cur.rowcount > 0
            conn.commit()
            return updated
    finally:
        conn.close()


def unlink_note_from_project(note_id: str, user: str) -> bool:
    """Remove a note's project association."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE notes SET project_id = NULL, updated_at = NOW()
                WHERE id = %s AND "user" = %s;
                """,
                (note_id, user),
            )
            updated = cur.rowcount > 0
            conn.commit()
            return updated
    finally:
        conn.close()
