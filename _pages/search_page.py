"""
pages/search_page.py
====================
WorkPilot AI — Search across tasks and notes
"""

import requests
import streamlit as st

from config import FASTAPI_BASE


def _get(user: str, path: str):
    try:
        r = requests.get(f"{FASTAPI_BASE}{path}", params={"user": user}, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def _badge(priority: str) -> str:
    cls = {"High": "wp-badge-high", "Medium": "wp-badge-medium", "Low": "wp-badge-low"}.get(priority, "wp-badge-medium")
    return f'<span class="wp-badge {cls}">{priority}</span>'


def render(user: dict):
    username = user.get("username", "default")
    query = st.session_state.get("_search_query", "")

    st.markdown(
        f'<div class="wp-greeting">🔍 Search Results</div>'
        f'<div class="wp-greeting-sub">Results for "{query}"</div>',
        unsafe_allow_html=True,
    )

    if not query:
        st.info("Enter a search term in the sidebar search box.")
        return

    query_lower = query.lower()

    # ── Search Tasks ───────────────────────────────────────
    data = _get(username, "/tasks")
    tasks = data.get("tasks", []) if data else []
    matching_tasks = [
        t for t in tasks
        if query_lower in (t.get("title", "") + " " + t.get("description", "")).lower()
    ]

    # ── Search Notes ───────────────────────────────────────
    data = _get(username, "/notes")
    notes = data.get("notes", []) if data else []
    matching_notes = [
        n for n in notes
        if query_lower in (n.get("title", "") + " " + n.get("content", "")).lower()
    ]

    # ── Display Results ────────────────────────────────────
    if not matching_tasks and not matching_notes:
        st.markdown(
            '<div class="wp-card wp-empty">'
            '<div class="wp-empty-icon">🔍</div>'
            'No results found. Try a different search term.'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    # Tasks results
    if matching_tasks:
        st.markdown(f'<div class="wp-section-title">✅ Tasks ({len(matching_tasks)})</div>', unsafe_allow_html=True)
        for t in matching_tasks:
            completed_style = "text-decoration:line-through;opacity:0.5" if t.get("completed") else ""
            badge = _badge(t.get("priority", "Medium"))
            due = t.get("due_date", "")
            st.markdown(
                f'<div class="wp-task-row">'
                f'<span class="wp-task-title" style="{completed_style}">{t["title"]}</span>'
                f'<span class="wp-task-due">{"Due " + due if due else ""}</span>'
                f'{badge}'
                f'</div>',
                unsafe_allow_html=True,
            )

    # Notes results
    if matching_notes:
        st.markdown(f'<div class="wp-section-title">📝 Notes ({len(matching_notes)})</div>', unsafe_allow_html=True)
        for n in matching_notes:
            content_preview = (n.get("content") or "")[:200]
            st.markdown(
                f'<div class="wp-note-card" style="margin-bottom:8px">'
                f'<div class="wp-note-title">{n["title"]}</div>'
                f'<div class="wp-note-content">{content_preview}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
