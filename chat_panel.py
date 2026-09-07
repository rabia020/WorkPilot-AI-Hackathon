import uuid
import requests
import streamlit as st

from rag.rag_chat import ask_rag
from config import FASTAPI_BASE


# ==========================================================
# CONFIGURATION
# ==========================================================

FASTAPI_BASE_URL = FASTAPI_BASE


# ==========================================================
# INITIALIZE SESSION STATE
# ==========================================================

def initialize_chat_state():

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "pending_review" not in st.session_state:
        st.session_state.pending_review = None

    if not st.session_state.get("agent_session_id"):
        st.session_state.agent_session_id = str(uuid.uuid4())

    if "review_comment" not in st.session_state:
        st.session_state.review_comment = ""

    if st.session_state.get("_clear_review_comment"):
        st.session_state.review_comment = ""
        st.session_state["_clear_review_comment"] = False


# ==========================================================
# DISPLAY CHAT MESSAGE
# ==========================================================

def display_message(role, content):

    with st.chat_message(role):

        st.markdown(content)


# ==========================================================
# HUMAN REVIEW UI
# ==========================================================

def render_human_review():
    """Render a polished Action Review Card for HITL approval."""
    review_data = st.session_state.get("pending_review")
    if not review_data:
        return False

    # ── Action Review Card ──
    st.markdown(
        '<div style="border:2px solid #f59e0b;border-radius:1.5rem;overflow:hidden;margin-bottom:16px;'
        'background:white;box-shadow:0 8px 24px rgba(245,158,11,0.12)">'
        '<div style="background:linear-gradient(135deg,#fffbeb,#fef3c7);padding:16px 24px;'
        'border-bottom:1px solid #fde68a">'
        '<div style="display:flex;align-items:center;gap:10px">'
        '<span style="font-size:24px">\u26a0\ufe0f</span>'
        '<div>'
        '<div style="font-weight:800;font-size:16px;color:#92400e">Action Review Required</div>'
        '<div style="font-size:13px;color:#a16207;margin-top:2px">'
        'The AI wants to perform actions that need your approval.</div>'
        '</div></div></div>',
        unsafe_allow_html=True,
    )

    # Original request
    original_query = review_data.get("query") or ""
    if original_query:
        st.markdown(
            '<div style="padding:16px 24px;border-bottom:1px solid var(--border-light)">'
            '<div style="font-size:11px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;'
            'color:var(--text-muted);margin-bottom:6px">Your Request</div>'
            f'<div style="font-size:14px;color:var(--text-primary);font-weight:500">{original_query}</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    # Report / analysis
    report = (
        review_data.get("report")
        or review_data.get("final_response")
        or review_data.get("output")
        or ""
    )
    if report:
        st.markdown(
            '<div style="padding:16px 24px;border-bottom:1px solid var(--border-light)">'
            '<div style="font-size:11px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;'
            'color:var(--text-muted);margin-bottom:8px">AI Analysis</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown(report)

    # Proposed actions
    proposed_actions = (
        review_data.get("proposed_actions")
        or review_data.get("planned_actions")
        or []
    )
    if proposed_actions:
        st.markdown(
            '<div style="padding:16px 24px 8px;border-bottom:1px solid var(--border-light)">'
            '<div style="font-size:11px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;'
            'color:var(--text-muted);margin-bottom:8px">Proposed Actions</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        for index, action in enumerate(proposed_actions, start=1):
            if isinstance(action, dict):
                tool = action.get("tool", "Unknown Action")
                args = action.get("args", {})
                # Color-code by tool type
                tool_colors = {
                    "email": "#3b82f6",
                    "sendemail": "#3b82f6",
                    "broadcastemail": "#3b82f6",
                    "sendcomplaintreplies": "#3b82f6",
                    "calendar": "#8b5cf6",
                    "createcalendarevent_tool": "#8b5cf6",
                    "slack": "#10b981",
                    "task": "#f59e0b",
                }
                accent = tool_colors.get(tool.lower(), "#6b7280")

                # Friendly tool name
                friendly_names = {
                    "SendEmail_Tool": "Send Email",
                    "BroadcastEmail_Tool": "Broadcast Email to All Employees",
                    "SendComplaintReplies": "Send Complaint Replies",
                    "CreateCalendarEvent_Tool": "Create Calendar Event",
                }
                display_name = friendly_names.get(tool, tool.replace("_", " ").replace("Tool", "").strip())

                st.markdown(
                    f'<div style="display:flex;gap:12px;padding:12px 16px;margin:4px 24px;'
                    f'background:var(--bg-card);border:1px solid var(--border-light);'
                    f'border-left:4px solid {accent};border-radius:12px">'
                    f'<div style="font-weight:700;font-size:14px;color:var(--text-primary);'
                    f'min-width:24px">{index}.</div>'
                    f'<div style="flex:1">'
                    f'<div style="font-weight:700;font-size:14px;color:{accent}">{display_name}</div>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )
                if args:
                    st.json(args)
            else:
                st.markdown(f"**{index}. {action}**")

    # Comment + Decision
    st.markdown(
        '<div style="padding:16px 24px 0">'
        '<div style="font-size:11px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;'
        'color:var(--text-muted);margin-bottom:8px">Your Decision</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    col1, col2 = st.columns(2)
    with col1:
        if st.button("\u2705  Approve & Execute", use_container_width=True, type="primary"):
            submit_review(
                session_id=review_data.get("session_id"),
                decision="approve",
                comment="",
            )
    with col2:
        if st.button("\u274c  Reject", use_container_width=True):
            submit_review(
                session_id=review_data.get("session_id"),
                decision="reject",
                comment="",
            )

    st.markdown('</div>', unsafe_allow_html=True)
    return True


# ==========================================================
# CORE MESSAGE HANDLER
# ==========================================================

def process_user_message(user_message, assistant_mode):

    st.session_state.messages.append({
        "role": "user",
        "content": user_message
    })

    display_message("user", user_message)

    # ======================================================
    # RAG MODE
    # ======================================================

    if assistant_mode == "RAG":

        try:

            with st.spinner("Searching company knowledge..."):

                answer = ask_rag(user_message)

        except Exception as e:
            answer = (
                "❌ **RAG Error:** Could not reach the AI model. "
                f"Details: {e}"
            )

        st.session_state.messages.append({
            "role": "assistant",
            "content": answer
        })

        display_message("assistant", answer)

        return

    # ======================================================
    # AI AGENT MODE
    # ======================================================

    current_user = st.session_state.get("user", {}) or {}

    username = current_user.get("username", "default")

    session_id = (
        st.session_state.get("agent_session_id")
        or str(uuid.uuid4())
    )

    st.session_state.agent_session_id = session_id

    payload = {
        "query": user_message,
        "user": username,
        "session_id": session_id
    }

    try:

        with st.spinner("AI Agent is planning and executing..."):

            response = requests.post(
                f"{FASTAPI_BASE_URL}/chat",
                json=payload,
                timeout=300
            )

        if response.status_code != 200:

            error = (
                f"Backend Error: HTTP {response.status_code}\n\n"
                f"Details:\n{response.text}"
            )

            st.error(error)

            return

        try:

            data = response.json()

        except ValueError:

            st.error(f"FastAPI returned invalid JSON:\n\n{response.text}")

            return

        if data.get("status") == "awaiting_approval":

            st.session_state.pending_review = {
                "session_id": data.get("session_id") or session_id,
                "query": data.get("query", user_message),
                "report": data.get("report", ""),
                "final_response": data.get("final_response", ""),
                "output": data.get("output", ""),
                "proposed_actions": data.get(
                    "proposed_actions", data.get("planned_actions", [])
                ),
                "planned_actions": data.get("planned_actions", []),
                "next": data.get("next", [])
            }

            st.rerun()

        final_response = (
            data.get("final_response")
            or data.get("report")
            or data.get("output")
            or data.get("message")
            or data.get("response")
            or "The request was completed."
        )

        st.session_state.messages.append({
            "role": "assistant",
            "content": final_response
        })

        display_message("assistant", final_response)

    except requests.exceptions.Timeout:

        st.error(
            "The request timed out.\n\n"
            "The backend may still be processing your request."
        )

    except requests.exceptions.ConnectionError:

        st.error(
            "Cannot connect to FastAPI.\n\n"
            "Make sure Uvicorn is running:\n\n"
            "`uvicorn app:app --reload`"
        )

    except Exception as e:

        st.error(f"Unexpected error:\n\n{str(e)}")# ==========================================================
# MAIN CHAT PANEL
# ==========================================================

def show_chat_panel_content():
    """Render chat content (mode selector, messages, review). Call INSIDE the tab."""
    initialize_chat_state()

    # -- Mode selector --
    assistant_mode = st.radio(
        "Mode",
        ["AI Agent (Automation)", "Company Knowledge (RAG)"],
        horizontal=True,
        key="chat_mode",
        label_visibility="collapsed",
    )

    # Map display names to internal codes
    mode_code = "RAG" if "RAG" in assistant_mode else "Agent"
    st.session_state["_chat_mode_code"] = mode_code

    # Show messages
    for message in st.session_state.messages:
        display_message(
            message.get("role", "assistant"),
            message.get("content", ""),
        )

    # HITL review
    if render_human_review():
        return


def show_chat_panel_input():
    """Render the chat input box. Call OUTSIDE tabs so it sits at the viewport bottom."""
    mode_code = st.session_state.get("_chat_mode_code", "Agent")

    if mode_code == "RAG":
        placeholder = "Ask about company knowledge, policies, documents..."
    else:
        placeholder = "Ask WorkPilot anything -- tasks, emails, calendar, notes..."

    user_message = st.chat_input(placeholder)
    if not user_message:
        return

    process_user_message(user_message, assistant_mode=mode_code)


def show_chat_panel():
    """Legacy wrapper — call both content and input together."""
    show_chat_panel_content()
    show_chat_panel_input()


# ==========================================================
# SUBMIT HUMAN REVIEW
# ==========================================================

def submit_review(session_id, decision, comment=""):

    if not session_id:

        st.error("Missing session ID. Cannot submit review.")

        return

    try:

        with st.spinner("Processing your decision..."):

            response = requests.post(
                f"{FASTAPI_BASE_URL}/review",
                json={
                    "session_id": session_id,
                    "decision": decision,
                    "comment": comment
                },
                timeout=300
            )

        if response.status_code != 200:

            st.error(f"Review Error:\n\n{response.text}")

            return

        try:

            data = response.json()

        except ValueError:

            st.error("Invalid JSON returned by the review endpoint.")

            return

        if decision == "approve":
            st.success("Actions approved and executed.")
        else:
            st.warning("Actions rejected. Nothing was executed.")

        final_response = (
            data.get("final_response")
            or data.get("report")
            or data.get("output")
            or data.get("message")
            or ""
        )

        if final_response:
            st.session_state.messages.append({
                "role": "assistant",
                "content": final_response
            })

        st.session_state.pending_review = None
        st.session_state["_clear_review_comment"] = True

        st.rerun()

    except requests.exceptions.ConnectionError:

        st.error("Cannot connect to FastAPI.")

    except Exception as e:

        st.error(f"Review failed:\n\n{str(e)}")