"""
pages/settings_page.py
======================
WorkPilot AI — Settings
Profile, password, integrations, preferences.
"""

import streamlit as st
import requests

from config import FASTAPI_BASE


def _check_backend():
    """Check if the FastAPI backend is reachable."""
    try:
        r = requests.get(f"{FASTAPI_BASE}/health", timeout=5)
        if r.status_code == 200:
            return True
    except Exception:
        pass
    return False


def render(user: dict):
    username = user.get("username", "")
    full_name = user.get("full_name") or username
    role = (user.get("role") or "").capitalize()
    email = user.get("email") or ""
    created_at = user.get("created_at", "")
    last_login = user.get("last_login", "")

    st.markdown(
        '<div class="wp-page-header"><div class="wp-greeting">⚙️ Settings</div>'
        '<div class="wp-greeting-sub">Manage your profile, preferences, and integrations.</div></div>',
        unsafe_allow_html=True,
    )

    tab_profile, tab_security, tab_integrations, tab_about = st.tabs(
        ["👤 Profile", "🔒 Security", "🔗 Integrations", "ℹ️ About"]
    )

    # =====================================================
    # TAB: Profile
    # =====================================================
    with tab_profile:
        st.markdown("### Your Profile")

        st.markdown(
            f'<div style="display:flex;gap:16px;align-items:center;padding:20px;'
            f'background:linear-gradient(135deg,#f5f3ff,#ede9fe);border-radius:16px;margin-bottom:20px">'
            f'<div style="width:64px;height:64px;border-radius:50%;'
            f'background:linear-gradient(135deg,#8f75ca,#b596e5);'
            f'display:flex;align-items:center;justify-content:center;'
            f'color:white;font-size:24px;font-weight:700;'
            f'box-shadow:0 8px 16px rgba(143,117,202,0.25)">'
            f'{full_name[0].upper()}</div>'
            f'<div>'
            f'<div style="font-size:18px;font-weight:700;color:var(--text-primary)">{full_name}</div>'
            f'<div style="font-size:13px;color:var(--text-muted)">@{username} · {role}</div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)
        with c1:
            st.text_input("Username", value=username, disabled=True)
            st.text_input("Role", value=role, disabled=True)
        with c2:
            st.text_input("Full Name", value=full_name, disabled=True)
            st.text_input("Email", value=email, disabled=True)

        if created_at:
            st.caption(f"Account created: {created_at[:10] if len(created_at) > 10 else created_at}")
        if last_login:
            st.caption(f"Last login: {last_login[:10] if len(last_login) > 10 else last_login}")

        st.success("Account Status: Active")

    # =====================================================
    # TAB: Security
    # =====================================================
    with tab_security:
        st.markdown("### Change Password")

        with st.form("change_password_form"):
            new_password = st.text_input("New Password", type="password", placeholder="Enter new password")
            confirm_password = st.text_input("Confirm Password", type="password", placeholder="Confirm new password")
            submitted = st.form_submit_button("Update Password", type="primary")

            if submitted:
                if not new_password or not new_password.strip():
                    st.warning("Please enter a new password.")
                elif new_password != confirm_password:
                    st.error("Passwords do not match.")
                elif len(new_password) < 4:
                    st.warning("Password must be at least 4 characters.")
                else:
                    try:
                        from auth import change_password
                        change_password(username, new_password)
                        st.success("Password updated successfully.")
                    except Exception as e:
                        st.error(f"Failed to update password: {e}")

    # =====================================================
    # TAB: Integrations
    # =====================================================
    with tab_integrations:
        st.markdown("### Connected Services")

        backend_ok = _check_backend()

        integrations = [
            ("FastAPI Backend", backend_ok, "Core API server"),
            ("PostgreSQL", True, "Database for tasks, notes, memory"),
            ("ChromaDB", True, "Vector store for RAG knowledge base"),
            ("Gmail (via n8n)", False, "Email read/send via n8n workflow"),
            ("Google Calendar (via n8n)", False, "Calendar events via n8n workflow"),
            ("Slack (via n8n)", False, "Team notifications via n8n workflow"),
            ("n8n Automation", False, "Workflow automation engine"),
            ("Groq LLM", True, "AI reasoning (openai/gpt-oss-120b)"),
            ("Mistral AI", True, "RAG answer generation"),
        ]

        for name, connected, description in integrations:
            status_color = "var(--green-700)" if connected else "var(--text-muted)"
            status_text = "Connected" if connected else "Not connected"
            icon = "🟢" if connected else "⚪"

            st.markdown(
                f'<div style="display:flex;justify-content:space-between;align-items:center;'
                f'padding:12px 16px;border:1px solid var(--border-light);border-radius:12px;'
                f'margin-bottom:8px;background:var(--bg-white, white)">'
                f'<div style="display:flex;align-items:center;gap:10px">'
                f'<span style="font-size:16px">{icon}</span>'
                f'<div>'
                f'<div style="font-weight:600;font-size:14px;color:var(--text-primary)">{name}</div>'
                f'<div style="font-size:12px;color:var(--text-muted)">{description}</div>'
                f'</div></div>'
                f'<span style="font-size:12px;font-weight:700;color:{status_color}">{status_text}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)
        st.info(
            "To connect Gmail, Calendar, or Slack, set up n8n workflows and configure "
            "the webhook URLs in your `.env` file:\n\n"
            "```\n"
            "N8N_ACTION_URL=http://localhost:5678/webhook/copilot-actions\n"
            "N8N_AGENT_URL=http://localhost:5678/webhook/copilot\n"
            "```"
        )

    # =====================================================
    # TAB: About
    # =====================================================
    with tab_about:
        st.markdown("### WorkPilot AI")

        st.markdown(
            f'<div style="padding:24px;background:linear-gradient(135deg,#f5f3ff,#ede9fe);'
            f'border-radius:16px;text-align:center;margin-bottom:20px">'
            f'<div style="width:56px;height:56px;border-radius:16px;'
            f'background:linear-gradient(135deg,#8f75ca,#b596e5);'
            f'display:inline-flex;align-items:center;justify-content:center;'
            f'font-size:28px;margin-bottom:12px">🤖</div>'
            f'<div style="font-size:20px;font-weight:800;color:#1e293b">WorkPilot AI</div>'
            f'<div style="font-size:13px;color:#64748b;margin-top:4px">'
            f'Autonomous AI Work Assistant</div>'
            f'<div style="font-size:11px;color:#94a3b8;margin-top:8px">Version 2.0.0</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            "**An AI employee that understands your work, plans your day, "
            "and executes tasks for you.**"
        )

        st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)

        features = [
            ("AI Chat", "Natural language work management"),
            ("Company Knowledge", "RAG-powered document search"),
            ("Email Assistant", "Read, draft, and send emails"),
            ("Calendar", "Schedule and manage events"),
            ("Task Management", "Prioritized work tracking"),
            ("Daily Planner", "AI-generated daily plans"),
            ("Projects", "Organize work around goals"),
            ("Multi-Agent AI", "Supervisor, planner, specialist agents"),
            ("Human-in-the-Loop", "Approval before external actions"),
        ]

        for name, desc in features:
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;align-items:center;'
                f'padding:8px 0;border-bottom:1px solid var(--border-light);font-size:14px">'
                f'<span style="font-weight:600;color:var(--text-primary)">{name}</span>'
                f'<span style="color:var(--text-muted);font-size:12px">{desc}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
