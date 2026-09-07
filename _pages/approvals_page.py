"""
pages/approvals_page.py
=======================
WorkPilot AI — Pending Approvals & Action History
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
        '<div class="wp-page-header"><div class="wp-greeting">⚡ Approvals</div>'
        '<div class="wp-greeting-sub">Review AI actions and see completed workflows.</div></div>',
        unsafe_allow_html=True,
    )

    # ── Pending Approvals ──
    st.markdown(
        '<div style="font-weight:700;font-size:15px;margin-bottom:10px;color:var(--text-primary)">'
        '🔔 Pending Approvals</div>',
        unsafe_allow_html=True,
    )

    pending = st.session_state.get("pending_review")

    if pending:
        st.warning("⚠️ There is an action awaiting your approval.")

        report = (
            pending.get("report")
            or pending.get("final_response")
            or ""
        )
        if report:
            st.markdown(report)

        proposed = pending.get("proposed_actions", [])
        if proposed:
            st.markdown("**Proposed Actions:**")
            for i, action in enumerate(proposed, 1):
                if isinstance(action, dict):
                    tool = action.get("tool", "Unknown")
                    args = action.get("args", {})
                    st.markdown(f"**{i}. {tool}**")
                    st.json(args)

        st.info("Go to the **WorkPilot** chat to approve or reject this action.")
    else:
        st.markdown(
            '<div class="wp-card wp-empty">'
            '<div class="wp-empty-icon">✅</div>'
            'No pending approvals. You\'re all clear!'
            '</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div style="height: 24px"></div>', unsafe_allow_html=True)

    # ── Recent AI Activity ──
    st.markdown(
        '<div style="font-weight:700;font-size:15px;margin-bottom:10px;color:var(--text-primary)">'
        '📋 Recent AI Actions</div>',
        unsafe_allow_html=True,
    )

    # Fetch action log from health endpoint (basic info)
    health = _get(username, "/health")
    if health:
        paused = health.get("paused_sessions", 0)
        st.markdown(
            f'<div style="font-size:13px;color:var(--text-secondary);margin-bottom:12px">'
            f'Active sessions: {paused} paused for review</div>',
            unsafe_allow_html=True,
        )

    # Show recent chat messages as activity
    messages = st.session_state.get("messages", [])
    if messages:
        for msg in messages[-10:]:
            role = msg.get("role", "assistant")
            content = msg.get("content", "")
            icon = "👤" if role == "user" else "🤖"
            st.markdown(
                f'<div style="display:flex;gap:10px;padding:10px 14px;'
                f'background:var(--purple-50, #f5f3ff);border-radius:10px;margin-bottom:6px;'
                f'font-size:13px;color:var(--text-secondary)">'
                f'<span style="font-size:16px">{icon}</span>'
                f'<span>{content[:200]}{"..." if len(content) > 200 else ""}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            '<div class="wp-card wp-empty">'
            '<div class="wp-empty-icon">🧠</div>'
            'No AI activity yet. Start a conversation in WorkPilot!'
            '</div>',
            unsafe_allow_html=True,
        )
