"""
pages/inbox_page.py
===================
WorkPilot AI — Inbox / Email Viewing
Displays recent emails fetched from Gmail via n8n.
"""

import streamlit as st
from config import FASTAPI_BASE
import requests


SEVERITY_COLORS = {
    "high": "#ef4444",
    "medium": "#f59e0b",
    "low": "#3b82f6",
}

CATEGORY_ICONS = {
    "billing": "💳",
    "shipping": "📦",
    "product": "🔧",
    "support": "🎧",
    "other": "📧",
}


def _fetch_emails():
    """Fetch recent emails from the n8n webhook via the backend.

    Returns (emails_list, error_string_or_None).
    """
    try:
        r = requests.get(f"{FASTAPI_BASE}/emails", timeout=30)
        if r.status_code == 200:
            data = r.json()
            emails = data.get("emails", [])
            # If backend returned empty, try n8n directly as fallback
            if not emails:
                emails, fallback_err = _fetch_emails_from_n8n()
                if emails:
                    return emails, None
                # Return the backend result (empty) but note n8n was tried
                return [], None
            return emails, None
        # Backend returned an error (e.g. n8n unreachable)
        detail = ""
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        return [], f"Backend error (HTTP {r.status_code}): {detail}"
    except requests.exceptions.ConnectionError:
        return [], (
            "Cannot connect to the backend API at "
            f"{FASTAPI_BASE}. Make sure the FastAPI server is running."
        )
    except requests.exceptions.Timeout:
        return [], "Backend request timed out. n8n may be slow or unreachable."
    except Exception as e:
        return [], f"Unexpected error fetching emails: {e}"


def _fetch_emails_from_n8n():
    """Fallback: fetch emails directly from n8n (same pattern as the backend)."""
    try:
        from tools.n8n_client import get_emails
        emails = get_emails(label="inbox", days=30)
        if not emails:
            # Try without label filter
            emails = get_emails(label="", days=30)
        return emails, None
    except Exception as e:
        return [], str(e)


def render(user: dict):
    username = user.get("username", "default")
    full_name = user.get("full_name") or username

    st.markdown(
        '<div class="wp-page-header"><div class="wp-greeting">📧 Inbox</div>'
        '<div class="wp-greeting-sub">Recent emails and AI-generated insights.</div></div>',
        unsafe_allow_html=True,
    )

    # ── Refresh button ──
    col_refresh, col_space = st.columns([1, 4])
    with col_refresh:
        if st.button("🔄 Refresh Emails", type="primary"):
            with st.spinner("Fetching emails from Gmail..."):
                emails, err = _fetch_emails()
                st.session_state["_inbox_emails"] = emails
                st.session_state["_inbox_error"] = err
            st.rerun()

    # ── Load emails ──
    emails = st.session_state.get("_inbox_emails")
    fetch_error = st.session_state.get("_inbox_error")

    if emails is None:
        with st.spinner("Loading emails..."):
            emails, fetch_error = _fetch_emails()
            st.session_state["_inbox_emails"] = emails
            st.session_state["_inbox_error"] = fetch_error

    # Show connection / n8n error prominently
    if fetch_error:
        st.error(f"⚠️ {fetch_error}")
        st.info(
            "Make sure **n8n** is running (default port 5678) and "
            "Gmail is connected as a channel in your n8n workflow."
        )

    if not emails:
        st.markdown(
            '<div class="wp-card wp-empty">'
            '<div class="wp-empty-icon">📬</div>'
            'No emails found. Make sure n8n and Gmail are connected.<br>'
            '<span style="font-size:12px;color:var(--text-muted)">Click Refresh to try again.</span>'
            '</div>',
            unsafe_allow_html=True,
        )

        st.markdown('<div style="height: 16px"></div>', unsafe_allow_html=True)

        # ── Quick actions ──
        st.markdown(
            '<div style="font-weight:700;font-size:15px;margin-bottom:10px;color:var(--text-primary)">'
            '💬 AI Email Actions</div>',
            unsafe_allow_html=True,
        )

        st.info(
            "You can ask the AI Agent to:\n\n"
            "- **Read emails**: \"Show me my recent emails\"\n"
            "- **Draft an email**: \"Send an email to john@company.com about...\"\n"
            "- **Analyze complaints**: \"Analyze customer complaints\"\n"
            "- **Broadcast**: \"Email all employees about...\""
        )
        return

    # ── Email Stats ──
    total = len(emails)
    high_sev = sum(1 for e in emails if e.get("severity", "").lower() == "high")
    categories = {}
    for e in emails:
        cat = e.get("category", "other")
        categories[cat] = categories.get(cat, 0) + 1

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total Emails", total)
    with c2:
        st.metric("High Severity", high_sev)
    with c3:
        top_cat = max(categories, key=categories.get) if categories else "none"
        st.metric("Top Category", top_cat.capitalize())

    st.markdown('<div style="height: 16px"></div>', unsafe_allow_html=True)

    # ── Email List ──
    for i, email in enumerate(emails):
        sender = email.get("sender", "Unknown")
        subject = email.get("subject", "No Subject")
        summary = email.get("summary", "")
        category = email.get("category", "other")
        severity = email.get("severity", "medium")
        sentiment = email.get("sentiment", "neutral")

        sev_color = SEVERITY_COLORS.get(severity.lower(), "#6b7280")
        cat_icon = CATEGORY_ICONS.get(category, "📧")
        sentiment_emoji = {"negative": "😞", "neutral": "😐", "positive": "😊"}.get(sentiment, "😐")

        st.markdown(
            f'<div style="display:flex;gap:14px;padding:14px 18px;margin-bottom:8px;'
            f'border:1px solid var(--border-light);border-radius:14px;'
            f'background:var(--bg-white, white);transition:all 0.2s">'
            f'<div style="width:40px;height:40px;border-radius:12px;'
            f'background:var(--purple-50, #f5f3ff);display:flex;align-items:center;'
            f'justify-content:center;font-size:18px;flex-shrink:0">{cat_icon}</div>'
            f'<div style="flex:1;min-width:0">'
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">'
            f'<span style="font-weight:700;font-size:14px;color:var(--text-primary);'
            f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{subject}</span>'
            f'<span style="width:8px;height:8px;border-radius:50%;background:{sev_color};'
            f'flex-shrink:0"></span>'
            f'</div>'
            f'<div style="font-size:12px;color:var(--text-muted);margin-bottom:4px">'
            f'From: {sender}</div>'
            f'<div style="font-size:13px;color:var(--text-secondary);line-height:1.5">'
            f'{summary[:200]}{"..." if len(summary) > 200 else ""}</div>'
            f'</div>'
            f'<div style="display:flex;flex-direction:column;align-items:flex-end;'
            f'gap:6px;flex-shrink:0">'
            f'<span style="font-size:11px;font-weight:700;padding:3px 8px;border-radius:6px;'
            f'background:{sev_color}20;color:{sev_color}">{severity.upper()}</span>'
            f'<span style="font-size:16px">{sentiment_emoji}</span>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── Ask AI about emails ──
    st.markdown('<div style="height: 16px"></div>', unsafe_allow_html=True)
    st.markdown(
        '<div style="font-weight:700;font-size:15px;margin-bottom:10px;color:var(--text-primary)">'
        '💬 Ask AI About Emails</div>',
        unsafe_allow_html=True,
    )
    st.info(
        "Switch to the **WorkPilot** page and try:\n\n"
        "- \"Analyze my complaint emails\"\n"
        "- \"Summarize my unread emails\"\n"
        "- \"Send a reply to the latest complaint\""
    )
