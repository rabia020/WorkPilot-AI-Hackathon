"""
pages/account.py
================
WorkPilot AI — Account / Profile
"""

import streamlit as st


def render(user: dict):
    st.markdown(
        '<div style="border-radius:2rem;border:1px solid rgba(255,255,255,0.7);'
        'background:rgba(255,255,255,0.8);padding:28px 32px;'
        'box-shadow:0 24px 60px rgba(123,92,173,0.10);backdrop-filter:blur(12px);margin-bottom:24px">'
        '<div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:flex-start;gap:20px">'
        '<div>'
        '<p style="font-size:12px;font-weight:700;letter-spacing:0.22em;text-transform:uppercase;'
        'color:#8f75ca;margin:0">Account</p>'
        '<h1 style="font-size:32px;font-weight:700;color:#1e293b;margin:6px 0 0 0">Profile</h1>'
        '<p style="font-size:14px;color:#64748b;margin:8px 0 0 0;line-height:1.6">'
        'Manage your personal details and keep your workspace identity in sync.</p>'
        '</div>'
        '<div style="display:flex;gap:12px;flex-wrap:wrap">'
        f'<div style="border-radius:1rem;border:1px solid #e4daf7;background:#fbfaff;padding:12px 16px">'
        '<p style="font-size:11px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;'
        'color:#8f75ca;margin:0">Signed in as</p>'
        f'<p style="font-size:13px;font-weight:600;color:#1e293b;margin:4px 0 0 0">{user.get("full_name") or user.get("username", "User")}</p>'
        '</div>'
        '<div style="border-radius:1rem;border:1px solid #e4daf7;background:#fbfaff;padding:12px 16px">'
        '<p style="font-size:11px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;'
        'color:#8f75ca;margin:0">Role</p>'
        f'<p style="font-size:13px;font-weight:600;color:#1e293b;margin:4px 0 0 0">{(user.get("role") or "").capitalize()}</p>'
        '</div>'
        '</div></div></div>',
        unsafe_allow_html=True,
    )

    # ── User Info Card ────────────────────────────────────
    st.markdown('<div class="wp-card">', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.text_input("Username", value=user.get("username", ""), disabled=True)
        st.text_input("Role", value=(user.get("role") or "").capitalize(), disabled=True)
    with c2:
        st.text_input("Full Name", value=user.get("full_name", ""), disabled=True)
        st.text_input("Email", value=user.get("email", ""), disabled=True)

    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div style="height: 14px"></div>', unsafe_allow_html=True)
    st.success("✅ Account Status: Active")

    st.markdown('<div style="height: 14px"></div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="wp-section-title">Available Features</div>',
        unsafe_allow_html=True,
    )

    features = [
        ("✅", "AI Chat Assistant", True),
        ("✅", "Company Knowledge Search (RAG)", True),
        ("✅", "Task Management", True),
        ("✅", "Notes", True),
        ("✅", "Calendar View", True),
        ("✅", "Daily Planner (AI)", True),
        ("✅", "Email Assistant", True),
        ("✅", "Calendar Automation", True),
        ("✅", "Report Generation", True),
        ("✅", "Slack Notifications", True),
    ]

    for icon, label, live in features:
        status = "Available" if live else "Coming soon"
        color = "var(--green-700)" if live else "var(--text-muted)"
        st.markdown(
            f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'padding:8px 0;border-bottom:1px solid var(--border-light);font-size:14px">'
            f'<span>{icon}&nbsp;&nbsp;{label}</span>'
            f'<span style="color:{color};font-weight:700;font-size:12px">{status}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div style="height: 14px"></div>', unsafe_allow_html=True)
    st.info("If you require additional permissions, please contact your manager.")
