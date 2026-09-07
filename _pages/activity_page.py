"""
pages/activity_page.py
======================
WorkPilot AI — Activity History
Shows a timeline of AI actions, completed workflows, and task completions.
"""

import requests
import streamlit as st

from config import FASTAPI_BASE


def _get(user: str, path: str):
    try:
        r = requests.get(f"{FASTAPI_BASE}{path}", params={"user": user}, timeout=10)
        if r.status_code == 200:
            return r.json()
        return None
    except Exception:
        return None


def render(user: dict):
    username = user.get("username", "default")
    full_name = user.get("full_name") or username

    st.markdown(
        '<div class="wp-page-header"><div class="wp-greeting">🧠 Activity</div>'
        '<div class="wp-greeting-sub">Your AI workflow history and completed actions.</div></div>',
        unsafe_allow_html=True,
    )

    # ── Summary Stats ──
    dash_data = _get(username, f"/dashboard/{username}")

    if dash_data:
        task_stats = dash_data.get("task_stats", {})
        total = task_stats.get("total", 0)
        completed = task_stats.get("completed", 0)
        pending = task_stats.get("pending", 0)

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Total Tasks", total)
        with c2:
            st.metric("Completed", completed)
        with c3:
            st.metric("Pending", pending)
        with c4:
            notes_count = len(dash_data.get("recent_notes", []))
            st.metric("Notes", notes_count)
    else:
        st.warning("Cannot connect to backend. Start the FastAPI server for full activity tracking.")

    st.markdown('<div style="height: 20px"></div>', unsafe_allow_html=True)

    # ── Recent Tasks Activity ──
    st.markdown(
        '<div style="font-weight:700;font-size:15px;margin-bottom:10px;color:var(--text-primary)">'
        '📋 Task Activity</div>',
        unsafe_allow_html=True,
    )

    tasks_data = _get(username, "/tasks")
    if tasks_data:
        tasks = tasks_data.get("tasks", [])

        # Show recently completed tasks
        completed_tasks = [t for t in tasks if t.get("completed")]
        if completed_tasks:
            st.markdown("**Recently Completed:**")
            for t in completed_tasks[:5]:
                updated = t.get("updated_at", "")
                date_str = updated[:10] if updated else ""
                st.markdown(
                    f'<div style="display:flex;gap:10px;padding:8px 14px;'
                    f'background:#f0fdf4;border-radius:10px;margin-bottom:6px;'
                    f'font-size:13px;color:#166534">'
                    f'<span>✅</span>'
                    f'<span style="flex:1">{t["title"]}</span>'
                    f'<span style="color:#86efac;font-size:11px">{date_str}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                '<div style="font-size:13px;color:var(--text-muted);padding:12px">'
                'No completed tasks yet.</div>',
                unsafe_allow_html=True,
            )

        # Show pending tasks
        pending_tasks = [t for t in tasks if not t.get("completed")]
        if pending_tasks:
            st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
            st.markdown("**In Progress:**")
            for t in pending_tasks[:5]:
                priority = t.get("priority", "Medium")
                badge_color = {"High": "#ef4444", "Medium": "#f59e0b", "Low": "#3b82f6"}.get(priority, "#6b7280")
                st.markdown(
                    f'<div style="display:flex;gap:10px;padding:8px 14px;'
                    f'background:var(--purple-50, #f5f3ff);border-radius:10px;margin-bottom:6px;'
                    f'font-size:13px;color:var(--text-secondary)">'
                    f'<span style="width:8px;height:8px;border-radius:50%;background:{badge_color};margin-top:5px;flex-shrink:0"></span>'
                    f'<span style="flex:1">{t["title"]}</span>'
                    f'<span style="font-size:11px;color:{badge_color};font-weight:600">{priority}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
    else:
        st.info("No task activity available.")

    st.markdown('<div style="height: 20px"></div>', unsafe_allow_html=True)

    # ── Recent Notes Activity ──
    st.markdown(
        '<div style="font-weight:700;font-size:15px;margin-bottom:10px;color:var(--text-primary)">'
        '📝 Recent Notes</div>',
        unsafe_allow_html=True,
    )

    notes_data = _get(username, "/notes")
    if notes_data:
        notes = notes_data.get("notes", [])
        if notes:
            for n in notes[:5]:
                updated = n.get("updated_at", "")
                date_str = updated[:10] if updated else ""
                st.markdown(
                    f'<div style="display:flex;gap:10px;padding:8px 14px;'
                    f'background:var(--purple-50, #f5f3ff);border-radius:10px;margin-bottom:6px;'
                    f'font-size:13px;color:var(--text-secondary)">'
                    f'<span>📝</span>'
                    f'<span style="flex:1"><strong>{n["title"]}</strong>: {(n.get("content") or "")[:80]}</span>'
                    f'<span style="color:var(--text-muted);font-size:11px">{date_str}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                '<div style="font-size:13px;color:var(--text-muted);padding:12px">'
                'No notes yet.</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No note activity available.")
