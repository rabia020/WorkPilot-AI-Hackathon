"""
pages/ask_ai.py
================
WorkPilot AI — AI Assistant with Plan My Day
"""

import uuid
import requests
import streamlit as st

from config import FASTAPI_BASE


def _init_state():
    if "ai_messages" not in st.session_state:
        st.session_state.ai_messages = []
    if "ai_session_id" not in st.session_state:
        st.session_state.ai_session_id = str(uuid.uuid4())
    if "ai_pending_review" not in st.session_state:
        st.session_state.ai_pending_review = None


def _send_chat(query: str, user: str):
    """Send a message to the AI agent via /chat."""
    session_id = st.session_state.ai_session_id

    payload = {
        "query": query,
        "user": user,
        "session_id": session_id,
    }

    try:
        with st.spinner("AI Agent is thinking..."):
            response = requests.post(
                f"{FASTAPI_BASE}/chat",
                json=payload,
                timeout=300,
            )

        if response.status_code != 200:
            return f"❌ Backend error: HTTP {response.status_code}"

        data = response.json()

        if data.get("status") == "awaiting_approval":
            st.session_state.ai_pending_review = {
                "session_id": data.get("session_id") or session_id,
                "query": data.get("query", query),
                "report": data.get("report", ""),
                "final_response": data.get("final_response", ""),
                "proposed_actions": data.get("proposed_actions", []),
            }
            return "⏳ Your request requires approval. Please review below."

        final = (
            data.get("final_response")
            or data.get("report")
            or data.get("message")
            or "The request was completed."
        )
        return final

    except requests.exceptions.ConnectionError:
        return "❌ Cannot connect to the AI backend. Make sure Uvicorn is running."
    except Exception as e:
        return f"❌ Error: {str(e)}"


def _submit_review(session_id: str, decision: str, comment: str = ""):
    """Submit an approval decision."""
    try:
        with st.spinner("Processing your decision..."):
            response = requests.post(
                f"{FASTAPI_BASE}/review",
                json={
                    "session_id": session_id,
                    "decision": decision,
                    "comment": comment,
                },
                timeout=300,
            )

        if response.status_code == 200:
            data = response.json()
            st.session_state.ai_pending_review = None
            final = data.get("final_response") or data.get("report") or "Done."
            return final
        else:
            return f"❌ Review error: {response.text}"
    except Exception as e:
        return f"❌ Review failed: {str(e)}"


def _plan_my_day(user: str):
    """Call the /plan-day endpoint."""
    try:
        with st.spinner("AI is planning your day..."):
            response = requests.post(
                f"{FASTAPI_BASE}/plan-day",
                json={"user": user},
                timeout=120,
            )

        if response.status_code == 200:
            data = response.json()
            return data.get("raw_text", "Plan generated successfully.")
        else:
            return f"❌ Plan error: HTTP {response.status_code}"
    except requests.exceptions.ConnectionError:
        return "❌ Cannot connect to the AI backend."
    except Exception as e:
        return f"❌ Error: {str(e)}"


def render(user: dict):
    username = user.get("username", "default")
    _init_state()

    st.markdown(
        '<div style="overflow:hidden;border-radius:2rem;border:1px solid rgba(255,255,255,0.7);'
        'background:white;box-shadow:0 24px 60px rgba(123,92,173,0.08);margin-bottom:24px">'
        '<div style="background:radial-gradient(circle at top left, rgba(225,216,247,0.7), transparent 30%),'
        'linear-gradient(135deg, #fcfbff 0%, #f6f1ff 100%);padding:28px 32px">'
        '<p style="font-size:12px;font-weight:700;letter-spacing:0.22em;text-transform:uppercase;'
        'color:#8f75ca;margin:0">AI</p>'
        '<h1 style="font-size:32px;font-weight:700;color:#1e293b;margin:6px 0 0 0">🤖 AI Assistant</h1>'
        '<p style="font-size:14px;color:#64748b;margin:8px 0 0 0;line-height:1.6">'
        'Ask anything about your work, or let AI plan your day.</p>'
        '</div></div>',
        unsafe_allow_html=True,
    )

    # ── Mode Selector ─────────────────────────────────────
    assistant_mode = st.radio(
        "Mode",
        ["🤖 AI Agent (Automation)", "📚 Company Knowledge (RAG)"],
        horizontal=True,
        key="ai_mode",
    )

    st.markdown("---")

    # ── Pending Review ────────────────────────────────────
    review = st.session_state.ai_pending_review
    if review:
        st.warning("⚠️ Human Approval Required")
        st.markdown("**📋 Review AI-Generated Actions**")
        st.info("The AI has prepared actions. Nothing will be executed until you approve.")

        report = review.get("report") or review.get("final_response") or ""
        if report:
            st.markdown(report)

        proposed = review.get("proposed_actions", [])
        if proposed:
            st.markdown("**⚙️ Proposed Actions**")
            for i, action in enumerate(proposed, 1):
                if isinstance(action, dict):
                    st.markdown(f"**{i}. {action.get('tool', 'Action')}**")
                    st.json(action.get("args", {}))

        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ Approve", type="primary", use_container_width=True):
                result = _submit_review(review["session_id"], "approve", "")
                st.session_state.ai_messages.append({"role": "assistant", "content": result})
                st.rerun()
        with c2:
            if st.button("❌ Reject", use_container_width=True):
                result = _submit_review(review["session_id"], "reject", "")
                st.session_state.ai_messages.append({"role": "assistant", "content": result})
                st.rerun()

        return

    # ── Chat History ──────────────────────────────────────
    for msg in st.session_state.ai_messages:
        role = msg.get("role", "assistant")
        with st.chat_message(role):
            st.markdown(msg.get("content", ""))

    # ── Quick Action Buttons ──────────────────────────────
    if not st.session_state.ai_messages:
        st.markdown(
            '<div style="display:flex;gap:12px;margin-bottom:16px">',
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🤖  Ask AI", use_container_width=True, type="primary"):
                pass  # Just show the chat input
        with c2:
            if st.button("📅  Plan My Day", use_container_width=True):
                result = _plan_my_day(username)
                st.session_state.ai_messages.append({"role": "assistant", "content": result})
                st.rerun()

    # ── Handle auto-plan from dashboard ───────────────────
    if st.session_state.get("_auto_plan"):
        del st.session_state["_auto_plan"]
        result = _plan_my_day(username)
        st.session_state.ai_messages.append({"role": "assistant", "content": result})
        st.rerun()

    # ── Chat Input ────────────────────────────────────────
    user_input = st.chat_input("Ask AI anything...")

    if user_input:
        # Add user message
        st.session_state.ai_messages.append({"role": "user", "content": user_input})

        # Process
        if "Company Knowledge" in assistant_mode or "RAG" in assistant_mode:
            try:
                from rag.rag_chat import ask_rag
                with st.spinner("Searching company knowledge..."):
                    answer = ask_rag(user_input)
            except Exception as e:
                answer = (
                    "❌ **RAG Error:** Could not reach the AI model. "
                    f"This may be a temporary rate limit — try again in a moment. "
                    f"Details: {e}"
                )
        else:
            answer = _send_chat(user_input, username)

        st.session_state.ai_messages.append({"role": "assistant", "content": answer})
        st.rerun()
