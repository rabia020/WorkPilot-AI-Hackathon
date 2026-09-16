"""
pages/dashboard.py
==================
WorkPilot AI — Home Dashboard / Morning Briefing
AI-generated daily overview with priority tasks, schedule, and suggestions.
"""

import requests
import streamlit as st
from datetime import datetime

from config import FASTAPI_BASE, DEMO_MODE


def _get(user: str, path: str):
    try:
        r = requests.get(f"{FASTAPI_BASE}{path}", params={"user": user}, timeout=10)
        if r.status_code == 200:
            return r.json()
        return None
    except requests.exceptions.ConnectionError:
        return None
    except Exception:
        return None


def _badge(priority: str) -> str:
    cls = {
        "High": "wp-badge-high",
        "Medium": "wp-badge-medium",
        "Low": "wp-badge-low",
    }.get(priority, "wp-badge-medium")
    return f'<span class="wp-badge {cls}">{priority}</span>'


def render(user: dict):
    username = user.get("username", "User")
    full_name = user.get("full_name") or username
    role = (user.get("role") or "employee").capitalize()

    # -- Greeting --
    hour = datetime.now().hour
    if hour < 12:
        greeting = "Good morning"
        emoji = "\u2600\ufe0f"
    elif hour < 17:
        greeting = "Good afternoon"
        emoji = "\U0001f324\ufe0f"
    else:
        greeting = "Good evening"
        emoji = "\U0001f319"

    today_str = datetime.now().strftime("%A, %B %d")

    # -- Hero card --
    st.markdown(
        '<div style="overflow:hidden;border-radius:2rem;border:1px solid rgba(255,255,255,0.7);'
        'background:white;box-shadow:0 24px 60px rgba(123,92,173,0.08);margin-bottom:24px">'
        '<div style="background:radial-gradient(circle at top left, rgba(225,216,247,0.7), transparent 30%),'
        'linear-gradient(135deg, #fcfbff 0%, #f6f1ff 100%);padding:28px 32px">'
        '<div style="display:flex;flex-direction:column;gap:20px;align-items:flex-start">'
        '<div>'
        '<p style="font-size:12px;font-weight:700;letter-spacing:0.22em;text-transform:uppercase;'
        f'color:#8f75ca;margin:0">Home \u2022 {today_str}</p>'
        f'<h1 style="font-size:32px;font-weight:700;color:#1e293b;margin:6px 0 0 0">{emoji} {greeting}, {full_name}</h1>'
        '<p style="font-size:14px;color:#64748b;margin:8px 0 0 0;line-height:1.6">'
        "Here's a calm snapshot of your day -- tasks and what to focus on.</p>"
        '</div>'
        '<div style="display:flex;gap:12px;flex-wrap:wrap">'
        f'<div style="display:flex;align-items:center;gap:12px;border-radius:1.35rem;'
        f'border:1px solid #e4daf7;background:rgba(255,255,255,0.9);padding:10px 16px">'
        f'<div style="width:44px;height:44px;border-radius:50%;background:linear-gradient(135deg,#8f75ca,#b596e5);'
        f'display:flex;align-items:center;justify-content:center;color:white;font-size:16px;font-weight:700;'
        f'box-shadow:0 8px 16px rgba(143,117,202,0.22)">{full_name[0].upper()}</div>'
        f'<div><p style="font-size:13px;font-weight:600;color:#1e293b;margin:0">{full_name}</p>'
        f'<p style="font-size:11px;color:#64748b;margin:2px 0 0 0">{role}</p></div></div>'
        '</div></div></div></div>',
        unsafe_allow_html=True,
    )

  

    # -- Fetch all data --
    if DEMO_MODE:
        # Demo deployment uses Task data stored in Streamlit session state.
        # No FastAPI or PostgreSQL connection is required.
        demo_tasks = st.session_state.get("demo_tasks", [])

        total_tasks = len(demo_tasks)
        completed_tasks_count = sum(
            1 for task in demo_tasks if task.get("completed")
        )
        pending_tasks_count = total_tasks - completed_tasks_count

        priority_counts = {
            "High": sum(
                1 for task in demo_tasks
                if task.get("priority") == "High"
            ),
            "Medium": sum(
                1 for task in demo_tasks
                if task.get("priority") == "Medium"
            ),
            "Low": sum(
                1 for task in demo_tasks
                if task.get("priority") == "Low"
            ),
        }

        stats = {
            "total": total_tasks,
            "completed": completed_tasks_count,
            "pending": pending_tasks_count,
        }

        data = {
            "status": "success",
            "task_stats": stats,
            "priority_counts": priority_counts,
            "recent_tasks": demo_tasks,
        }

    else:
        # Original production behavior — use FastAPI.
        data = _get(username, f"/dashboard/{username}")

        if data is None:
            st.warning(
                "Cannot connect to the backend API. "
                "Start the FastAPI server for full functionality."
            )
            stats = {
                "total": 0,
                "completed": 0,
                "pending": 0,
            }
            priority_counts = {
                "High": 0,
                "Medium": 0,
                "Low": 0,
            }

        elif data.get("status") == "success":
            stats = data.get("task_stats", {})
            priority_counts = data.get(
                "priority_counts",
                {"High": 0, "Medium": 0, "Low": 0},
            )

        else:
            stats = {
                "total": 0,
                "completed": 0,
                "pending": 0,
            }
            priority_counts = {
                "High": 0,
                "Medium": 0,
                "Low": 0,
            }

    projects = []

    # -- Stats Row --
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            '<div class="wp-stat-card wp-stat-card-total">'
            '<div class="wp-stat-label">TOTAL TASKS</div>'
            f'<div class="wp-stat-value">{stats.get("total", 0)}</div>'
            '<div class="wp-stat-desc">All tasks in your workspace</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            '<div class="wp-stat-card wp-stat-card-completed">'
            '<div class="wp-stat-label" style="color: var(--green-700)">COMPLETED</div>'
            f'<div class="wp-stat-value" style="color: var(--green-700)">{stats.get("completed", 0)}</div>'
            '<div class="wp-stat-desc">Tasks marked as done</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            '<div class="wp-stat-card wp-stat-card-pending">'
            '<div class="wp-stat-label" style="color: var(--yellow-700)">PENDING</div>'
            f'<div class="wp-stat-value" style="color: var(--yellow-700)">{stats.get("pending", 0)}</div>'
            '<div class="wp-stat-desc">Still waiting to be done</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    with c4:
        high_count = priority_counts.get("High", 0)
        st.markdown(
            '<div class="wp-stat-card wp-stat-card-high">'
            '<div class="wp-stat-label" style="color: var(--red-700)">HIGH PRIORITY</div>'
            f'<div class="wp-stat-value" style="color: var(--red-700)">{high_count}</div>'
            '<div class="wp-stat-desc">Urgent tasks needing attention</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div style="height: 20px"></div>', unsafe_allow_html=True)

    # -- AI Briefing --
    pending_tasks = []
    recent_tasks = (data or {}).get("recent_tasks", [])
    if recent_tasks:
        pending_tasks = [t for t in recent_tasks if not t.get("completed")]

    total_pending = stats.get("pending", 0)
    high_pending = priority_counts.get("High", 0)

    briefing_lines = []
    if total_pending > 0:
        briefing_lines.append(f"You have <b>{total_pending} pending tasks</b>")
        if high_pending > 0:
            briefing_lines[-1] += f" ({high_pending} high priority)"
    if total_pending == 0:
        briefing_lines.append("You're all caught up! No pending tasks.")

    briefing = ". ".join(briefing_lines) + "." if briefing_lines else "Welcome to WorkPilot!"

    # AI suggestions
    suggestions = []
    if high_pending > 0:
        suggestions.append(f"Your <b>{high_pending} high-priority tasks</b> need attention today.")
    if total_pending > high_pending:
        medium_low = total_pending - high_pending
        suggestions.append(f"You have <b>{medium_low} medium/low tasks</b> -- consider batching them.")
    if not suggestions:
        suggestions.append("Try asking WorkPilot to plan your day for an optimized schedule.")

    st.markdown(
        '<div style="display:flex;gap:12px;padding:18px 22px;border-radius:1.2rem;'
        'background:linear-gradient(135deg,#ede9fe,#f5f3ff);border:1px solid #e4daf7;'
        'margin-bottom:16px">'
        '<div style="font-size:22px;flex-shrink:0">✨</div>'
        '<div>'
        '<div style="font-size:11px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;'
        'color:#8f75ca;margin-bottom:6px">AI Briefing</div>'
        f'<div style="font-size:14px;color:var(--text-primary);line-height:1.6">{briefing}</div>'
        '</div></div>',
        unsafe_allow_html=True,
    )

    # -- Suggestions --
    if suggestions:
        for s in suggestions:
            st.markdown(
                f'<div style="display:flex;gap:10px;padding:10px 14px;'
                f'background:var(--bg-white,white);border:1px solid var(--border-light);'
                f'border-radius:12px;margin-bottom:6px;font-size:13px;color:var(--text-secondary)">'
                f'<span style="font-size:14px;flex-shrink:0">💡</span>'
                f'<span>{s}</span></div>',
                unsafe_allow_html=True,
            )

    st.markdown('<div style="height: 20px"></div>', unsafe_allow_html=True)

    # -- Today's Focus --
    st.markdown(
        '<div class="wp-section-title">🎯 TODAY\'S FOCUS</div>',
        unsafe_allow_html=True,
    )

    pending_all = [t for t in pending_tasks if not t.get("completed")]
    if not pending_all:
        all_pending = [t for t in recent_tasks if not t.get("completed")]
        if all_pending:
            pending_all = all_pending[:4]

    if pending_all:
        for t in pending_all[:5]:
            badge_val = _badge(t.get("priority", "Medium"))
            due = t.get("due_date", "")
            due_str = f'<span class="wp-task-due">Due {due}</span>' if due else ""
            st.markdown(
                f'<div class="wp-task-row">'
                f'<span class="wp-task-title">{t.get("title", "")}</span>'
                f'{due_str}'
                f'{badge_val}'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            '<div class="wp-card wp-empty">'
            '<div class="wp-empty-icon">✅</div>'
            'No pending tasks! You\'re all clear.'
            '</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div style="height: 20px"></div>', unsafe_allow_html=True)

    # -- Recent Activity --
    st.markdown('<div style="height: 20px"></div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="wp-section-title">\U0001f9e0 RECENT ACTIVITY</div>',
        unsafe_allow_html=True,
    )

    completed_tasks = [t for t in recent_tasks if t.get("completed")]
    if completed_tasks:
        for t in completed_tasks[:3]:
            updated = t.get("updated_at", "")
            date_str = updated[:10] if updated else ""
            st.markdown(
                f'<div style="display:flex;gap:10px;padding:8px 14px;'
                f'background:#f0fdf4;border-radius:10px;margin-bottom:6px;'
                f'font-size:13px;color:#166534">'
                f'<span>\u2705</span>'
                f'<span style="flex:1">{t.get("title", "")}</span>'
                f'<span style="color:#86efac;font-size:11px">{date_str}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        # Show pending as "in progress"
        if pending_all:
            for t in pending_all[:3]:
                priority = t.get("priority", "Medium")
                badge_color = {"High": "#ef4444", "Medium": "#f59e0b", "Low": "#3b82f6"}.get(priority, "#6b7280")
                st.markdown(
                    f'<div style="display:flex;gap:10px;padding:8px 14px;'
                    f'background:var(--purple-50, #f5f3ff);border-radius:10px;margin-bottom:6px;'
                    f'font-size:13px;color:var(--text-secondary)">'
                    f'<span style="width:8px;height:8px;border-radius:50%;background:{badge_color};'
                    f'margin-top:5px;flex-shrink:0"></span>'
                    f'<span style="flex:1">{t.get("title", "")}</span>'
                    f'<span style="font-size:11px;color:{badge_color};font-weight:600">{priority}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                '<div class="wp-card wp-empty">'
                '<div class="wp-empty-icon">\U0001f9e0</div>'
                'No activity yet. Start a conversation with WorkPilot!'
                '</div>',
                unsafe_allow_html=True,
            )
