"""
Pages API Helper
================
Shared helper for WorkPilot pages.

DEMO_MODE=true:
    Uses local Streamlit session-state storage.

DEMO_MODE=false:
    Uses the original FastAPI backend.
"""

import requests
import streamlit as st

from config import FASTAPI_BASE, DEMO_MODE


def api_call(
    method: str,
    path: str,
    user: str,
    json_data: dict = None,
):
    """
    Make a WorkPilot API-style call.

    In demo mode, requests are handled locally without
    FastAPI or PostgreSQL.

    Returns:
        (data, error)
    """

    # ======================================================
    # DEMO MODE
    # ======================================================

    if DEMO_MODE:

        import work_manager

        method = method.upper()

        # --------------------------------------------------
        # TASKS
        # --------------------------------------------------

        if path == "/tasks" and method == "GET":
            return {
                "status": "success",
                "tasks": work_manager.get_tasks(user),
            }, None

        if path == "/tasks" and method == "POST":
            data = json_data or {}

            task = work_manager.create_task(
                user=user,
                title=data.get("title", ""),
                description=data.get(
                    "description",
                    "",
                ),
                due_date=data.get(
                    "due_date"
                ),
                priority=data.get(
                    "priority",
                    "Medium",
                ),
            )

            return {
                "status": "success",
                "task": task,
            }, None

        if path.startswith("/tasks/"):

            parts = path.strip("/").split("/")

            if len(parts) >= 2:
                task_id = parts[1]

                # ------------------------------------------
                # TOGGLE TASK
                # ------------------------------------------

                if (
                    len(parts) == 3
                    and parts[2] == "toggle"
                    and method == "POST"
                ):
                    task = work_manager.toggle_task(
                        task_id,
                        user,
                    )

                    if not task:
                        return None, "Task not found."

                    return {
                        "status": "success",
                        "task": task,
                    }, None

                # ------------------------------------------
                # UPDATE TASK
                # ------------------------------------------

                if (
                    len(parts) == 2
                    and method == "PUT"
                ):
                    data = json_data or {}

                    task = work_manager.update_task(
                        task_id,
                        user,
                        **data,
                    )

                    if not task:
                        return None, "Task not found."

                    return {
                        "status": "success",
                        "task": task,
                    }, None

                # ------------------------------------------
                # DELETE TASK
                # ------------------------------------------

                if (
                    len(parts) == 2
                    and method == "DELETE"
                ):
                    deleted = work_manager.delete_task(
                        task_id,
                        user,
                    )

                    if not deleted:
                        return None, "Task not found."

                    return {
                        "status": "success",
                    }, None

        # --------------------------------------------------
        # NOTES
        # --------------------------------------------------

        if path == "/notes" and method == "GET":
            return {
                "status": "success",
                "notes": work_manager.get_notes(user),
            }, None

        if path == "/notes" and method == "POST":
            data = json_data or {}

            note = work_manager.create_note(
                user=user,
                title=data.get("title", ""),
                content=data.get(
                    "content",
                    "",
                ),
            )

            return {
                "status": "success",
                "note": note,
            }, None

        if path.startswith("/notes/"):

            parts = path.strip("/").split("/")

            if len(parts) >= 2:
                note_id = parts[1]

                # ------------------------------------------
                # UPDATE NOTE
                # ------------------------------------------

                if (
                    len(parts) == 2
                    and method == "PUT"
                ):
                    data = json_data or {}

                    note = work_manager.update_note(
                        note_id,
                        user,
                        **data,
                    )

                    if not note:
                        return None, "Note not found."

                    return {
                        "status": "success",
                        "note": note,
                    }, None

                # ------------------------------------------
                # DELETE NOTE
                # ------------------------------------------

                if (
                    len(parts) == 2
                    and method == "DELETE"
                ):
                    deleted = work_manager.delete_note(
                        note_id,
                        user,
                    )

                    if not deleted:
                        return None, "Note not found."

                    return {
                        "status": "success",
                    }, None

        return None, f"Unsupported demo API request: {method} {path}"

    # ======================================================
    # ORIGINAL FASTAPI MODE
    # ======================================================

    url = f"{FASTAPI_BASE}{path}"
    params = {"user": user}

    # For GET requests with json_data, treat it as extra
    # query parameters.
    if method == "GET" and isinstance(json_data, dict):
        params.update(json_data)

    try:

        if method == "GET":
            r = requests.get(
                url,
                params=params,
                timeout=10,
            )

        elif method == "POST":
            r = requests.post(
                url,
                json=json_data,
                params=params,
                timeout=10,
            )

        elif method == "PUT":
            r = requests.put(
                url,
                json=json_data,
                params=params,
                timeout=10,
            )

        elif method == "DELETE":
            r = requests.delete(
                url,
                params=params,
                timeout=10,
            )

        else:
            return None, "Unsupported method"

        if r.status_code == 200:
            return r.json(), None

        return None, (
            f"Server returned status {r.status_code}: "
            f"{r.text[:200]}"
        )

    except requests.exceptions.ConnectionError:
        return None, (
            "Cannot connect to backend. "
            "Is the FastAPI server running on port 8001?"
        )

    except requests.exceptions.Timeout:
        return None, "Request timed out."

    except Exception as e:
        return None, str(e)


def api_get(path: str, user: str):
    """Convenience GET helper."""
    return api_call(
        "GET",
        path,
        user,
    )


def api_post(
    path: str,
    user: str,
    json_data: dict = None,
):
    """Convenience POST helper."""
    return api_call(
        "POST",
        path,
        user,
        json_data,
    )


def api_put(
    path: str,
    user: str,
    json_data: dict = None,
):
    """Convenience PUT helper."""
    return api_call(
        "PUT",
        path,
        user,
        json_data,
    )


def api_delete(
    path: str,
    user: str,
):
    """Convenience DELETE helper."""
    return api_call(
        "DELETE",
        path,
        user,
    )


def badge_html(priority: str) -> str:
    """Return styled badge HTML for a task priority."""

    cls = {
        "High": "wp-badge-high",
        "Medium": "wp-badge-medium",
        "Low": "wp-badge-low",
    }.get(
        priority,
        "wp-badge-medium",
    )

    return (
        f'<span class="wp-badge {cls}">'
        f'{priority}'
        f'</span>'
    )