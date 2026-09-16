"""
work_manager.py
===============
WorkPilot AI — Task / Note / Dashboard Manager

Supports two modes:

DEMO_MODE=false
    Uses the original PostgreSQL backend.

DEMO_MODE=true
    Uses Streamlit session state.
    No PostgreSQL, FastAPI, or backend is required.
"""

import uuid
from datetime import datetime, date

import streamlit as st

from config import DEMO_MODE


# ==========================================================
# DEMO STORAGE
# ==========================================================

def _init_demo_storage():
    """
    Initialize session-state storage for demo mode.
    """

    if "demo_tasks" not in st.session_state:
        st.session_state["demo_tasks"] = []

    if "demo_notes" not in st.session_state:
        st.session_state["demo_notes"] = []


def _demo_tasks():
    _init_demo_storage()
    return st.session_state["demo_tasks"]


def _demo_notes():
    _init_demo_storage()
    return st.session_state["demo_notes"]


def _new_id():
    """Generate a local ID for demo records."""
    return str(uuid.uuid4())


def _now():
    """Return current timestamp as ISO string."""
    return datetime.now().isoformat(timespec="seconds")


# ==========================================================
# DEMO SEED DATA
# ==========================================================

def seed_demo_data(user: str) -> dict:
    """
    Add sample tasks and notes for the current demo session.

    Only used when DEMO_MODE=true.
    """

    if not DEMO_MODE:
        return {
            "tasks_created": 0,
            "notes_created": 0,
            "skipped": True,
        }

    _init_demo_storage()

    # Don't seed twice.
    if st.session_state.get("demo_seeded", False):
        return {
            "tasks_created": 0,
            "notes_created": 0,
            "skipped": True,
        }

    demo_tasks = [
        {
            "title": "Prepare client proposal",
            "priority": "High",
            "description": "Draft the Q3 client proposal using the latest project data and company templates.",
        },
        {
            "title": "Review unread emails",
            "priority": "Medium",
            "description": "Check inbox for urgent replies from the project team.",
        },
        {
            "title": "Complete project documentation",
            "priority": "Medium",
            "description": "Finish the API docs and README for the internal tool.",
        },
        {
            "title": "Follow up with HR",
            "priority": "Low",
            "description": "Ask about the new onboarding process for next quarter.",
        },
        {
            "title": "Organize GitHub repository",
            "priority": "Medium",
            "description": "Clean up branches, update .gitignore, and tag releases.",
        },
        {
            "title": "Test task functionality",
            "priority": "High",
            "description": "Verify task editing, completion, and deletion.",
        },
    ]

    demo_notes = [
        {
            "title": "Presentation Ideas",
            "content": (
                "Focus on:\n"
                "- Full-stack architecture\n"
                "- AI-powered task management\n"
                "- Team collaboration\n"
                "- Human-in-the-loop approvals"
            ),
        },
        {
            "title": "Meeting Notes",
            "content": (
                "Sprint priorities:\n"
                "1. Complete AI integration\n"
                "2. Improve calendar workflow\n"
                "3. Add email notification support\n"
                "4. Improve dashboard performance"
            ),
        },
        {
            "title": "Quick Reminders",
            "content": (
                "- Deploy to staging\n"
                "- Send proposal to client\n"
                "- Update documentation\n"
                "- Review pending tasks"
            ),
        },
    ]

    today = date.today()

    for i, task in enumerate(demo_tasks):
        due = today.isoformat()

        _demo_tasks().append(
            {
                "id": _new_id(),
                "user": user,
                "title": task["title"],
                "description": task["description"],
                "due_date": due,
                "priority": task["priority"],
                "completed": False,
                "created_at": _now(),
                "updated_at": _now(),
            }
        )

    for note in demo_notes:
        _demo_notes().append(
            {
                "id": _new_id(),
                "user": user,
                "title": note["title"],
                "content": note["content"],
                "created_at": _now(),
                "updated_at": _now(),
            }
        )

    st.session_state["demo_seeded"] = True

    return {
        "tasks_created": len(demo_tasks),
        "notes_created": len(demo_notes),
        "skipped": False,
    }


# ==========================================================
# ORIGINAL POSTGRESQL HELPERS
# ==========================================================

def _get_postgres_manager():
    """
    Lazy import of the original PostgreSQL implementation.

    This is intentionally imported only when DEMO_MODE is false.
    """

    import psycopg2
    import psycopg2.extras

    from config import PG_CONFIG, get_connection

    return psycopg2, psycopg2.extras, PG_CONFIG, get_connection


def _row_to_dict(row):
    """Convert a database row to a normal dictionary."""
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

    if DEMO_MODE:
        task = {
            "id": _new_id(),
            "user": user,
            "title": title,
            "description": description,
            "due_date": due_date,
            "priority": priority,
            "completed": False,
            "created_at": _now(),
            "updated_at": _now(),
        }

        _demo_tasks().append(task)
        return task

    # Original PostgreSQL behavior
    psycopg2, extras, PG_CONFIG, get_connection = _get_postgres_manager()

    conn = get_connection()

    try:
        with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
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

    if DEMO_MODE:
        tasks = [
            dict(t)
            for t in _demo_tasks()
            if t.get("user") == user
        ]

        priority_order = {
            "High": 1,
            "Medium": 2,
            "Low": 3,
        }

        tasks.sort(
            key=lambda t: (
                t.get("completed", False),
                priority_order.get(t.get("priority"), 4),
                t.get("due_date") or "9999-12-31",
            )
        )

        return tasks

    # Original PostgreSQL behavior
    psycopg2, extras, PG_CONFIG, get_connection = _get_postgres_manager()

    conn = get_connection()

    try:
        with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
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

    allowed = {
        "title",
        "description",
        "due_date",
        "priority",
        "completed",
    }

    updates = {
        k: v
        for k, v in kwargs.items()
        if k in allowed and v is not None
    }

    if not updates:
        return {}

    if DEMO_MODE:

        for task in _demo_tasks():

            if (
                str(task.get("id")) == str(task_id)
                and task.get("user") == user
            ):

                task.update(updates)
                task["updated_at"] = _now()

                return dict(task)

        return {}

    # Original PostgreSQL behavior
    psycopg2, extras, PG_CONFIG, get_connection = _get_postgres_manager()

    parts = []
    values = []

    for k, v in updates.items():
        parts.append(f'"{k}" = %s')
        values.append(v)

    parts.append('"updated_at" = NOW()')

    set_sql = ", ".join(parts)
    values.extend([task_id, user])

    conn = get_connection()

    try:
        with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                UPDATE tasks
                SET {set_sql}
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

    if DEMO_MODE:

        tasks = _demo_tasks()

        before = len(tasks)

        st.session_state["demo_tasks"] = [
            t for t in tasks
            if not (
                str(t.get("id")) == str(task_id)
                and t.get("user") == user
            )
        ]

        return len(st.session_state["demo_tasks"]) < before

    # Original PostgreSQL behavior
    psycopg2, extras, PG_CONFIG, get_connection = _get_postgres_manager()

    conn = get_connection()

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

    if DEMO_MODE:

        for task in _demo_tasks():

            if (
                str(task.get("id")) == str(task_id)
                and task.get("user") == user
            ):

                task["completed"] = not task.get("completed", False)
                task["updated_at"] = _now()

                return dict(task)

        return {}

    # Original PostgreSQL behavior
    psycopg2, extras, PG_CONFIG, get_connection = _get_postgres_manager()

    conn = get_connection()

    try:
        with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
            cur.execute(
                """
                UPDATE tasks
                SET completed = NOT completed,
                    updated_at = NOW()
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

    tasks = get_tasks(user)

    total = len(tasks)
    completed = sum(
        1 for t in tasks
        if t.get("completed")
    )

    return {
        "total": total,
        "completed": completed,
        "pending": total - completed,
    }


# ==========================================================
# NOTES
# ==========================================================

def create_note(
    user: str,
    title: str,
    content: str = "",
) -> dict:

    if DEMO_MODE:

        note = {
            "id": _new_id(),
            "user": user,
            "title": title,
            "content": content,
            "created_at": _now(),
            "updated_at": _now(),
        }

        _demo_notes().append(note)
        return note

    # Original PostgreSQL behavior
    psycopg2, extras, PG_CONFIG, get_connection = _get_postgres_manager()

    conn = get_connection()

    try:
        with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
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

    if DEMO_MODE:

        notes = [
            dict(n)
            for n in _demo_notes()
            if n.get("user") == user
        ]

        notes.sort(
            key=lambda n: n.get("updated_at", ""),
            reverse=True,
        )

        return notes

    # Original PostgreSQL behavior
    psycopg2, extras, PG_CONFIG, get_connection = _get_postgres_manager()

    conn = get_connection()

    try:
        with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
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


def update_note(
    note_id: str,
    user: str,
    **kwargs,
) -> dict:

    allowed = {
        "title",
        "content",
    }

    updates = {
        k: v
        for k, v in kwargs.items()
        if k in allowed and v is not None
    }

    if not updates:
        return {}

    if DEMO_MODE:

        for note in _demo_notes():

            if (
                str(note.get("id")) == str(note_id)
                and note.get("user") == user
            ):

                note.update(updates)
                note["updated_at"] = _now()

                return dict(note)

        return {}

    # Original PostgreSQL behavior
    psycopg2, extras, PG_CONFIG, get_connection = _get_postgres_manager()

    parts = []
    values = []

    for k, v in updates.items():
        parts.append(f'"{k}" = %s')
        values.append(v)

    parts.append('"updated_at" = NOW()')

    set_sql = ", ".join(parts)
    values.extend([note_id, user])

    conn = get_connection()

    try:
        with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                UPDATE notes
                SET {set_sql}
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


def delete_note(
    note_id: str,
    user: str,
) -> bool:

    if DEMO_MODE:

        notes = _demo_notes()

        before = len(notes)

        st.session_state["demo_notes"] = [
            n for n in notes
            if not (
                str(n.get("id")) == str(note_id)
                and n.get("user") == user
            )
        ]

        return len(st.session_state["demo_notes"]) < before

    # Original PostgreSQL behavior
    psycopg2, extras, PG_CONFIG, get_connection = _get_postgres_manager()

    conn = get_connection()

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
# DASHBOARD
# ==========================================================

def get_dashboard_stats(user: str) -> dict:

    stats = get_task_stats(user)
    tasks = get_tasks(user)
    notes = get_notes(user)

    pending = [
        t for t in tasks
        if not t.get("completed")
    ]

    priority_counts = {
        "High": 0,
        "Medium": 0,
        "Low": 0,
    }

    for task in pending:
        priority = task.get("priority", "Medium")
        priority_counts[priority] = (
            priority_counts.get(priority, 0) + 1
        )

    return {
        "task_stats": stats,
        "recent_tasks": tasks[:5],
        "recent_notes": notes[:5],
        "pending_count": len(pending),
        "priority_counts": priority_counts,
    }


# ==========================================================
# WORK CONTEXT FOR AI
# ==========================================================

def get_work_context(user: str) -> str:
    """
    Build a text summary of the user's current work state.

    Works with both PostgreSQL and demo session-state storage.
    """

    tasks = get_tasks(user)
    notes = get_notes(user)

    lines = [
        f"=== WORK CONTEXT for {user} ===\n"
    ]

    # ------------------------------------------------------
    # TASKS
    # ------------------------------------------------------

    pending = [
        t for t in tasks
        if not t.get("completed")
    ]

    done = [
        t for t in tasks
        if t.get("completed")
    ]

    lines.append(
        f"TASKS ({len(pending)} pending, "
        f"{len(done)} completed):"
    )

    for task in pending:

        due = task.get(
            "due_date",
            "no due date",
        )

        description = task.get(
            "description",
            "",
        )

        lines.append(
            f"  [{task.get('priority', 'Medium')}] "
            f"{task.get('title', '')} — due {due}"
            + (
                f" — {description}"
                if description
                else ""
            )
        )

    if not pending:
        lines.append(
            "  (no pending tasks)"
        )

    # ------------------------------------------------------
    # NOTES
    # ------------------------------------------------------

    lines.append(
        f"\nNOTES ({len(notes)} total):"
    )

    for note in notes[:10]:

        preview = (
            note.get("content", "") or ""
        )[:120]

        lines.append(
            f"  • {note.get('title', '')}: "
            f"{preview}"
        )

    if not notes:
        lines.append(
            "  (no notes)"
        )

    # ------------------------------------------------------
    # PROJECTS
    # ------------------------------------------------------

    try:

        import project_manager

        projects = project_manager.get_projects(user)

        if projects:

            lines.append(
                f"\nPROJECTS ({len(projects)} total):"
            )

            for project in projects[:5]:

                name = project.get(
                    "name",
                    "Untitled",
                )

                description = project.get(
                    "description",
                    "",
                )

                status = project.get(
                    "status",
                    "active",
                )

                lines.append(
                    f"  📁 {name} "
                    f"[{status}]: "
                    f"{description[:100] if description else 'No description'}"
                )

        else:
            lines.append(
                "\nPROJECTS: (none)"
            )

    except Exception:
        # Projects are optional in demo mode.
        pass

    lines.append(
        "\n=== END WORK CONTEXT ==="
    )

    return "\n".join(lines)