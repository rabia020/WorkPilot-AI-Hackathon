"""
pages/tasks_page.py
====================
WorkPilot AI — Tasks Management
"""

import requests
import streamlit as st
from datetime import date, datetime

from config import FASTAPI_BASE
from _pages._api import api_call, badge_html


def render(user: dict):
    username = user.get("username", "default")

    st.markdown(
        '<div class="wp-page-header"><div class="wp-greeting">✅ Tasks</div>'
        '<div class="wp-greeting-sub">Keep track of what needs doing.</div></div>',
        unsafe_allow_html=True,
    )

    # ── Track form submission error outside the form ──────
    if "_task_submit_error" in st.session_state:
        err = st.session_state.pop("_task_submit_error")
        st.error(err)
    if "_task_submit_ok" in st.session_state:
        msg = st.session_state.pop("_task_submit_ok")
        st.success(msg)

    # ── Add Task Form ─────────────────────────────────────
    with st.form("add_task_form", clear_on_submit=False):
        st.markdown('<div style="font-weight:700;font-size:14px;margin-bottom:8px">New Task</div>', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns([3, 1.5, 1, 1])
        with c1:
            title = st.text_input("Task", placeholder="e.g. Draft training plan", label_visibility="collapsed")
        with c2:
            due_date = st.date_input("Due", value=None, label_visibility="collapsed")
        with c3:
            priority = st.selectbox("Priority", ["Medium", "High", "Low"], label_visibility="collapsed")
        with c4:
            submitted = st.form_submit_button("Add task", type="primary", use_container_width=True)

        if submitted:
            if not title or not title.strip():
                st.warning("Please enter a task title.")
            else:
                due_str = due_date.isoformat() if due_date else None
                result, err = api_call("POST", "/tasks", username, {
                    "title": title.strip(),
                    "due_date": due_str,
                    "priority": priority,
                })
                if err:
                    st.error(err)
                elif result and result.get("status") == "success":
                    st.session_state["_task_submit_ok"] = f"Task added: {title.strip()}"
                    st.rerun()
                else:
                    st.error("Unexpected response from backend.")

    st.markdown('<div style="height: 12px"></div>', unsafe_allow_html=True)

    # ── Task List ─────────────────────────────────────────
    data, err = api_call("GET", "/tasks", username)
    if err:
        st.warning(f"Could not load tasks: {err}")
        tasks = []
    else:
        tasks = data.get("tasks", []) if data else []

    if not tasks:
        st.markdown(
            '<div class="wp-card wp-empty">'
            '<div class="wp-empty-icon">📋</div>'
            'No tasks yet. Add your first task above!'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    for t in tasks:
        tid = t["id"]
        completed = t.get("completed", False)
        title = t.get("title", "")
        due = t.get("due_date", "")
        priority_val = t.get("priority", "Medium")

        # Row layout using columns
        col_check, col_title, col_due, col_priority, col_actions = st.columns([0.5, 3, 1.2, 0.8, 1])

        with col_check:
            new_val = st.checkbox("", value=completed, key=f"chk_{tid}", label_visibility="collapsed")
            if new_val != completed:
                api_call("POST", f"/tasks/{tid}/toggle", username)
                st.rerun()

        with col_title:
            style = "text-decoration:line-through;color:var(--text-muted)" if completed else ""
            st.markdown(f'<span style="{style};font-weight:600;font-size:14px">{title}</span>', unsafe_allow_html=True)

        with col_due:
            if due:
                st.markdown(f'<span class="wp-task-due">Due {due}</span>', unsafe_allow_html=True)

        with col_priority:
            st.markdown(badge_html(priority_val), unsafe_allow_html=True)

        with col_actions:
            ac1, ac2 = st.columns(2)
            with ac1:
                if st.button("✏️", key=f"edit_{tid}", help="Edit"):
                    st.session_state[f"editing_{tid}"] = True
                    st.rerun()
            with ac2:
                if st.button("🗑️", key=f"del_{tid}", help="Delete"):
                    api_call("DELETE", f"/tasks/{tid}", username)
                    st.rerun()

        # ── Edit form (inline) ────────────────────────────
        if st.session_state.get(f"editing_{tid}"):
            with st.expander(f"Edit: {title}", expanded=True):
                new_title = st.text_input("Title", value=title, key=f"etitle_{tid}")
                new_due = st.date_input(
                    "Due date",
                    value=date.fromisoformat(due) if due else None,
                    key=f"edue_{tid}",
                )
                new_priority = st.selectbox(
                    "Priority",
                    ["Medium", "High", "Low"],
                    index=["Medium", "High", "Low"].index(priority_val) if priority_val in ["Medium", "High", "Low"] else 0,
                    key=f"epri_{tid}",
                )
                ec1, ec2 = st.columns(2)
                with ec1:
                    if st.button("Save", key=f"esave_{tid}", type="primary"):
                        due_str = new_due.isoformat() if new_due else None
                        api_call("PUT", f"/tasks/{tid}", username, {
                            "title": new_title.strip() or title,
                            "due_date": due_str,
                            "priority": new_priority,
                        })
                        del st.session_state[f"editing_{tid}"]
                        st.rerun()
                with ec2:
                    if st.button("Cancel", key=f"ecancel_{tid}"):
                        del st.session_state[f"editing_{tid}"]
                        st.rerun()
