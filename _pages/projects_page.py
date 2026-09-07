"""
pages/projects_page.py
======================
WorkPilot AI -- Projects Management + Jira Issues
"""

import requests
import streamlit as st

from config import FASTAPI_BASE
from _pages._api import api_call
from tools.n8n_client import get_jira_issues


# ------------------------------------------------------------------
# Jira Issues Tab
# ------------------------------------------------------------------
def _render_jira_tab(username):
    """Fetch and display Jira issues from n8n."""

    st.markdown(
        '<div style="font-weight:700;font-size:15px;margin-bottom:12px;color:var(--text-primary)">'
        'Jira Issues</div>',
        unsafe_allow_html=True,
    )

    # Filters
    fc1, fc2, fc3 = st.columns([2, 2, 1])
    with fc1:
        project_key = st.text_input(
            "Project Key", value="KAN", key="jira_proj_key",
            placeholder="e.g. KAN",
        )
    with fc2:
        status_filter = st.selectbox(
            "Status", ["All", "To Do", "In Progress", "Pending", "Done"],
            key="jira_status",
        )
    with fc3:
        st.markdown('<div style="height: 28px"></div>', unsafe_allow_html=True)
        fetch_btn = st.button("\U0001f504 Fetch Issues", type="primary", key="jira_fetch")

    # Fetch on button click or first load
    if fetch_btn or "_jira_issues" not in st.session_state:
        with st.spinner("Fetching Jira issues from n8n..."):
            try:
                status_val = None if status_filter == "All" else status_filter
                result = get_jira_issues(
                    project=project_key or "KAN",
                    status=status_val,
                    max_results=25,
                )
                issues = result.get("issues", [])
                st.session_state["_jira_issues"] = issues
                st.session_state["_jira_error"] = (
                    None if result.get("success") else result.get("message", "")
                )
            except Exception as e:
                st.session_state["_jira_issues"] = []
                st.session_state["_jira_error"] = str(e)

    issues = st.session_state.get("_jira_issues", [])
    jira_err = st.session_state.get("_jira_error")

    if jira_err:
        st.error(f"\u26a0\ufe0f {jira_err}")
        st.info(
            "Make sure **n8n** is running and the Jira integration "
            "is connected in your n8n workflow."
        )

    if not issues:
        st.markdown(
            '<div class="wp-card wp-empty">'
            '<div class="wp-empty-icon">\U0001f4cb</div>'
            'No Jira issues found. Adjust filters and click Fetch, or '
            'make sure Jira is connected in n8n.'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    # Status color map
    status_colors = {
        "To Do": "#6b7280",
        "In Progress": "#3b82f6",
        "Pending": "#f59e0b",
        "Done": "#10b981",
    }

    st.markdown(
        f'<div style="font-size:13px;color:var(--text-muted);margin-bottom:10px">'
        f'Found <b>{len(issues)}</b> issues in project <b>{project_key or "KAN"}</b></div>',
        unsafe_allow_html=True,
    )

    for issue in issues:
        key = issue.get("key", issue.get("issue_key", ""))
        summary = issue.get("summary", issue.get("fields", {}).get("summary", "No summary"))
        status = issue.get("status", issue.get("fields", {}).get("status", "Unknown"))
        if isinstance(status, dict):
            status = status.get("name", "Unknown")
        priority = issue.get("priority", issue.get("fields", {}).get("priority", ""))
        if isinstance(priority, dict):
            priority = priority.get("name", "")
        assignee = issue.get("assignee", issue.get("fields", {}).get("assignee", ""))
        if isinstance(assignee, dict):
            assignee = assignee.get("displayName", assignee.get("name", ""))

        sev_color = status_colors.get(str(status), "#6b7280")

        st.markdown(
            f'<div style="display:flex;gap:12px;padding:12px 16px;margin-bottom:8px;'
            f'border:1px solid var(--border-light);border-radius:12px;'
            f'background:var(--bg-white,white)">'
            f'<div style="display:flex;flex-direction:column;align-items:center;'
            f'gap:4px;min-width:80px">'
            f'<span style="font-size:12px;font-weight:700;color:var(--purple-700,#6d28d9)">{key}</span>'
            f'<span style="width:8px;height:8px;border-radius:50%;background:{sev_color}"></span>'
            f'</div>'
            f'<div style="flex:1;min-width:0">'
            f'<div style="font-weight:600;font-size:14px;color:var(--text-primary);'
            f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{summary}</div>'
            f'<div style="font-size:12px;color:var(--text-muted);margin-top:4px">'
            f'{"Status: " + str(status)}{" | Assignee: " + str(assignee) if assignee else ""}{" | Priority: " + str(priority) if priority else ""}'
            f'</div></div>'
            f'<div style="display:flex;align-items:center;flex-shrink:0">'
            f'<span style="font-size:11px;font-weight:700;padding:3px 8px;border-radius:6px;'
            f'background:{sev_color}20;color:{sev_color}">{status}</span>'
            f'</div></div>',
            unsafe_allow_html=True,
        )


# ------------------------------------------------------------------
# Main render
# ------------------------------------------------------------------
def render(user):
    username = user.get("username", "default")

    st.markdown(
        '<div class="wp-page-header"><div class="wp-greeting">\U0001f4c1 Projects</div>'
        '<div class="wp-greeting-sub">Organize your work around meaningful goals.</div></div>',
        unsafe_allow_html=True,
    )

    # -- Tabs: Projects | Jira Issues --
    tab_projects, tab_jira = st.tabs(["\U0001f4c1 Projects", "\U0001f4cb Jira Issues"])

    with tab_projects:
        _render_projects_tab(username)

    with tab_jira:
        _render_jira_tab(username)


def _render_projects_tab(username):
    """Render the internal projects management section."""

    # -- Flash messages --
    if "_proj_ok" in st.session_state:
        st.success(st.session_state.pop("_proj_ok"))
    if "_proj_err" in st.session_state:
        st.error(st.session_state.pop("_proj_err"))

    # -- New Project Form --
    with st.form("add_project_form", clear_on_submit=False):
        st.markdown('<div style="font-weight:700;font-size:14px;margin-bottom:8px">New project</div>', unsafe_allow_html=True)
        col1, col2 = st.columns([2, 1])
        with col1:
            name = st.text_input("Project name", placeholder="e.g. Client Proposal")
        with col2:
            color = st.color_picker("Color", value="#8f75ca")
        description = st.text_area("Description (optional)", placeholder="What is this project about?", height=80)
        submitted = st.form_submit_button("Create project", type="primary", use_container_width=True)

        if submitted:
            if not name or not name.strip():
                st.warning("Please enter a project name.")
            else:
                result, err = api_call("POST", "/projects", username, {
                    "name": name.strip(),
                    "description": description.strip() if description else "",
                    "color": color,
                })
                if err:
                    st.error(err)
                elif result and result.get("status") == "success":
                    st.session_state["_proj_ok"] = f"Project created: {name.strip()}"
                    st.rerun()
                else:
                    st.error("Unexpected response from backend.")

    st.markdown('<div style="height: 16px"></div>', unsafe_allow_html=True)

    # -- Projects List --
    data, err = api_call("GET", "/projects", username)
    if err:
        st.warning(f"Could not load projects: {err}")
        projects = []
    else:
        projects = data.get("projects", []) if data else []

    if not projects:
        st.markdown(
            '<div class="wp-card wp-empty">'
            '<div class="wp-empty-icon">\U0001f4c1</div>'
            'No projects yet. Create your first project above!'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    # Display projects as cards
    for proj in projects:
        pid = proj["id"]
        pname = proj.get("name", "Untitled")
        pdesc = proj.get("description", "")
        pcolor = proj.get("color", "#8f75ca")
        pstatus = proj.get("status", "active")

        status_badge = "\U0001f7e2 Active" if pstatus == "active" else "\U0001f4e6 Archived"

        st.markdown(
            f'<div class="wp-card" style="border-left: 4px solid {pcolor}; padding: 16px 20px; margin-bottom: 12px;">'
            f'<div style="display:flex; justify-content:space-between; align-items:center;">'
            f'<div>'
            f'<div style="font-weight:700; font-size:16px; color:var(--text-primary);">{pname}</div>'
            f'<div style="font-size:13px; color:var(--text-secondary); margin-top:4px;">{pdesc[:120] if pdesc else "No description"}</div>'
            f'</div>'
            f'<div style="font-size:12px; color:var(--text-muted);">{status_badge}</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Action buttons
        bc1, bc2, bc3 = st.columns([1, 1, 1])
        with bc1:
            if st.button("\U0001f4c2 View Details", key=f"pview_{pid}", use_container_width=True):
                st.session_state[f"viewing_project_{pid}"] = not st.session_state.get(f"viewing_project_{pid}", False)
                st.rerun()
        with bc2:
            if st.button("\U0001f5d1\ufe0f Delete", key=f"pdel_{pid}", use_container_width=True):
                api_call("DELETE", f"/projects/{pid}", username)
                st.session_state["_proj_ok"] = f"Project deleted: {pname}"
                st.rerun()

        # -- Project details expansion --
        if st.session_state.get(f"viewing_project_{pid}"):
            ctx, ctx_err = api_call("GET", f"/projects/{pid}", username)
            if ctx_err:
                st.warning(f"Could not load project details: {ctx_err}")
            elif ctx:
                tasks = ctx.get("tasks", [])
                notes = ctx.get("notes", [])
                pending = ctx.get("pending_tasks", 0)
                total = ctx.get("task_count", 0)
                completed = ctx.get("completed_tasks", 0)

                st.markdown(f'<div style="padding: 12px 16px; background: var(--bg-light, #f8f7ff); border-radius: 12px; margin-bottom: 12px;">', unsafe_allow_html=True)

                sm1, sm2, sm3 = st.columns(3)
                with sm1:
                    st.metric("Total Tasks", total)
                with sm2:
                    st.metric("Completed", completed)
                with sm3:
                    st.metric("Pending", pending)

                if tasks:
                    st.markdown("**Tasks:**")
                    for t in tasks[:8]:
                        done = "~~" if t.get("completed") else ""
                        st.markdown(f"- {done}{t['title']}")

                if notes:
                    st.markdown("**Notes:**")
                    for n in notes[:5]:
                        st.markdown(f"- **{n['title']}**: {(n.get('content') or '')[:80]}")

                st.markdown('</div>', unsafe_allow_html=True)
