# supervisor.py

import os
import json
import operator
import re

from typing import (
    Annotated,
    TypedDict,
    List,
    Dict,
    Any,
    Optional
)

from dotenv import load_dotenv

from langchain_core.messages import (
    HumanMessage,
    SystemMessage
)

from langchain_groq import ChatGroq

from langgraph.graph import (
    StateGraph,
    END
)

from langgraph.checkpoint.memory import MemorySaver

from langgraph.types import (
    interrupt,
    Command
)


from agents.email_agent import (
    email_agent,
    prepare_new_email,
    list_recent_emails,
    prepare_broadcast_email,
    analyze_complaint_emails,
    send_email_replies,
    send_new_email,
    send_broadcast_emails
)

from agents.rag_agent import (
    rag_agent
)

from agents.reporter import (
    generate_report
)

from memory.memory_store import (
    get_memory_store
)

from tools.n8n_client import (
    send_slack_message,
    create_calendar_event,
    get_calendar_events,
    get_jira_issues,
    update_jira_issue,
    create_jira_ticket
)

import work_manager


# ==========================================================
# ENVIRONMENT
# ==========================================================

load_dotenv()


# ==========================================================
# MEMORY
# ==========================================================

memory_store = get_memory_store()


# ==========================================================
# STATE
# ==========================================================

class AgentState(TypedDict):

    query: str

    emails: List[
        Dict[str, Any]
    ]

    context: str

    report: str

    messages: Annotated[
        list,
        operator.add
    ]

    query_type: str

    plan: list

    user: str

    session_id: str

    memory_context: Optional[
        Dict
    ]

    approved: Optional[
        bool
    ]

    approval_comment: Optional[
        str
    ]

    proposed_actions: List[
        Dict[str, Any]
    ]

    # --------------------------------------------------
    # NEW: structured, per-action outcomes recorded during
    # execution (memory_save_node), consumed by responder_node
    # to build a final message that reflects what ACTUALLY
    # happened — instead of leaving the pre-approval proposal
    # text as the last thing the user sees. This is the piece
    # graph.py had (its `responder` step) that this pipeline
    # was missing.
    # --------------------------------------------------

    execution_results: List[
        Dict[str, Any]
    ]

    final_response: str

    # --------------------------------------------------
    # Declared because nodes already write them: LangGraph
    # silently discards writes to undeclared channels, so
    # "docs" (rag_agent) and "error" (email drafting) were
    # being dropped before reaching any consumer.
    # --------------------------------------------------

    docs: List[Any]

    error: Optional[str]

    # Structured per-recipient outcome of an approved email
    # send, so the summary reflects what n8n actually
    # confirmed rather than "the call did not raise".
    email_send_result: Optional[
        Dict[str, Any]
    ]

    status: Optional[str]


# ==========================================================
# LLM
# ==========================================================

llm = ChatGroq(

    model="openai/gpt-oss-120b",

    api_key=os.getenv(
        "GROQ_API_KEY"
    ),

    temperature=0.2

)


# ==========================================================
# DATE-PHRASE EXTRACTION
# (fix — human-review bypass. Any code that fetches calendar
# "context" to help draft a proposal must NEVER forward the raw
# user query to n8n: the raw query can contain action language
# ("send a message to slack") that n8n's execution-capable AI
# agent will act on immediately, bypassing human_review entirely.
# This isolates ONLY a bounded date/time phrase before anything
# is sent to n8n.)
# ==========================================================

_DATE_PHRASE_RE = re.compile(
    r'\b(today|tonight|tomorrow|yesterday|this week|next week|'
    r'this weekend|monday|tuesday|wednesday|thursday|friday|'
    r'saturday|sunday|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}(/\d{2,4})?)\b',
    re.IGNORECASE
)


def _extract_date_phrase(query: str) -> Optional[str]:
    """
    Pull out ONLY a bounded date/time reference from free text.
    Returns None if nothing date-like is found — callers should
    skip the calendar lookup entirely in that case rather than
    forwarding the raw sentence.
    """

    match = _DATE_PHRASE_RE.search(query or "")

    return match.group(0) if match else None


# ==========================================================
# MEMORY LOAD
# ==========================================================

def memory_load_node(
    state: AgentState
) -> AgentState:

    """
    Load past session memory AND inject current work context
    (tasks, notes) so agents are aware of the user's work state.
    """

    # Load past session memory from MemoryStore
    result = memory_store.memory_load_node(state)

    # Also inject work context (tasks + notes) into memory_context
    user = state.get("user", "default")
    try:
        work_ctx = work_manager.get_work_context(user)
    except Exception as e:
        print(f"[Memory Load] Work context fetch failed: {e}")
        work_ctx = ""

    # Merge work context into memory_context
    mem_ctx = result.get("memory_context") or {}
    mem_ctx["work_context"] = work_ctx

    return {**result, "memory_context": mem_ctx}


# ==========================================================
# MEMORY SAVE + APPROVED EXECUTION
# ==========================================================

def memory_save_node(
    state: AgentState
) -> AgentState:

    """
    Executes approved actions.

    Normal email:
        prepare email
        HITL approval
        send new email

    Calendar:
        prepare event
        HITL approval
        create calendar event

    Complaint:
        analyze complaints
        HITL approval
        send complaint replies
        notify Slack
        create follow-up calendar event

    Finally:
        save memory

    NEW: also records a structured outcome per action into
    execution_results, so responder_node can tell the user what
    actually happened rather than repeating the pre-approval
    proposal text.
    """


    query_type = state.get(
        "query_type"
    )


    approved = state.get(
        "approved"
    )


    execution_results: List[Dict[str, Any]] = []


    # ======================================================
    # APPROVED NORMAL EMAIL
    #
    # send_new_email returns a structured "email_send_result"
    # in state, so the outcome below reflects what n8n actually
    # reported per recipient rather than merely "did not raise".
    # ======================================================

    if (

        approved is True

        and query_type == "email"

    ):

        try:

            state = send_new_email(
                state
            )

            send_result = state.get(
                "email_send_result"
            )

            if send_result is None:

                execution_results.append({
                    "action": "Send email",
                    "success": False,
                    "detail": (
                        "Nothing was sent — no approved email draft "
                        "was found in state."
                    ),
                })

            else:

                execution_results.append({
                    "action": "Send email",
                    "success": bool(
                        send_result.get("success")
                    ),
                    "detail": (
                        f"{send_result.get('sent', 0)} sent, "
                        f"{send_result.get('failed', 0)} failed"
                    ),
                })

        except Exception as e:

            print(f"[memory_save] Email send error: {e}")

            execution_results.append({
                "action": "Send email",
                "success": False,
                "detail": str(e),
            })


    # ======================================================
    # APPROVED BROADCAST EMAIL
    # ======================================================

    if (

        approved is True

        and query_type == "email_broadcast"

    ):

        try:

            state = send_broadcast_emails(
                state
            )

            send_result = state.get(
                "email_send_result"
            )

            if send_result is None:

                execution_results.append({
                    "action": "Send broadcast email",
                    "success": False,
                    "detail": (
                        "Nothing was sent — no approved broadcast "
                        "draft was found in state."
                    ),
                })

            else:

                execution_results.append({
                    "action": "Send broadcast email",
                    "success": bool(
                        send_result.get("success")
                    ),
                    "detail": (
                        f"{send_result.get('sent', 0)} sent, "
                        f"{send_result.get('failed', 0)} failed"
                    ),
                })

        except Exception as e:

            print(f"[memory_save] Broadcast email error: {e}")

            execution_results.append({
                "action": "Send broadcast email",
                "success": False,
                "detail": str(e),
            })


    # ======================================================
    # APPROVED CALENDAR EVENT
    # (this branch did not exist before — calendar requests
    # were routed to research_agent and never actually
    # created an event, approved or not)
    # ======================================================

    if (

        approved is True

        and query_type == "calendar"

    ):

        proposed = state.get(
            "proposed_actions",
            []
        )

        if proposed:

            args = proposed[0].get(
                "args",
                {}
            )

            try:

                result = create_calendar_event(

                    title=args.get(
                        "title",
                        "Event"
                    ),

                    date=args.get(
                        "start",
                        ""
                    ),

                    duration=args.get(
                        "duration",
                        ""
                    ),

                    description=args.get(
                        "description",
                        ""
                    )

                )

                print(
                    f"[memory_save] Calendar event created: {result}"
                )

                state = {

                    **state,

                    "messages": (

                        state.get("messages", [])

                        + [f"[Calendar] Event created: {result}"]

                    )

                }

                execution_results.append({
                    "action": f"Create calendar event: {args.get('title', 'Event')}",
                    "success": bool(result.get("success", False)) if isinstance(result, dict) else False,
                    "detail": (
                        result.get("message", str(result))
                        if isinstance(result, dict)
                        else "Calendar creation was not confirmed by n8n"
                    ),
                })

            except Exception as e:

                print(
                    f"[memory_save] Calendar creation error: {e}"
                )

                execution_results.append({
                    "action": f"Create calendar event: {args.get('title', 'Event')}",
                    "success": False,
                    "detail": str(e),
                })

        else:

            print(
                "[memory_save] Calendar approved but no "
                "proposed_actions found — nothing to create."
            )

            execution_results.append({
                "action": "Create calendar event",
                "success": False,
                "detail": "No proposed_actions found — nothing to create.",
            })


    # ======================================================
    # APPROVED SLACK MESSAGE
    # (new — Slack requests previously had no execution path
    # at all since they never had a dedicated query_type)
    # ======================================================

    if (

        approved is True

        and query_type == "slack"

    ):

        proposed = state.get(
            "proposed_actions",
            []
        )

        if proposed:

            args = proposed[0].get(
                "args",
                {}
            )

            try:

                success = send_slack_message(

                    channel=args.get(
                        "channel",
                        "#general"
                    ),

                    message=args.get(
                        "message",
                        ""
                    )

                )

                print(
                    f"[memory_save] Slack message sent: {success}"
                )

                state = {

                    **state,

                    "messages": (

                        state.get("messages", [])

                        + [f"[Slack] Message sent: {success}"]

                    )

                }

                execution_results.append({
                    "action": f"Send Slack message to {args.get('channel', '#general')}",
                    "success": bool(success),
                    "detail": (
                        "Message sent successfully."
                        if success
                        else "n8n reported the send did not succeed."
                    ),
                })

            except Exception as e:

                print(
                    f"[memory_save] Slack send error: {e}"
                )

                execution_results.append({
                    "action": f"Send Slack message to {args.get('channel', '#general')}",
                    "success": False,
                    "detail": str(e),
                })

        else:

            print(
                "[memory_save] Slack approved but no "
                "proposed_actions found — nothing to send."
            )

            execution_results.append({
                "action": "Send Slack message",
                "success": False,
                "detail": "No proposed_actions found — nothing to send.",
            })


    # ======================================================
    # APPROVED COMPLAINT
    # ======================================================

    if (

        approved is True

        and query_type == "complaint"

    ):

        try:

            state = send_email_replies(
                state
            )

            send_result = state.get(
                "email_send_result"
            )

            if send_result is None:

                execution_results.append({
                    "action": "Send complaint email replies",
                    "success": False,
                    "detail": (
                        "Nothing was sent — no approved complaint "
                        "emails were found in state."
                    ),
                })

            else:

                execution_results.append({
                    "action": "Send complaint email replies",
                    "success": bool(
                        send_result.get("success")
                    ),
                    "detail": (
                        f"{send_result.get('sent', 0)} sent, "
                        f"{send_result.get('failed', 0)} failed"
                    ),
                })

        except Exception as e:

            print(f"[memory_save] Complaint reply error: {e}")

            execution_results.append({
                "action": "Send complaint email replies",
                "success": False,
                "detail": str(e),
            })


        # --------------------------------------------------
        # SLACK NOTIFICATION
        # --------------------------------------------------

        try:

            slack_success = send_slack_message(

                channel="#complaints",

                message=(

                    "Report approved:\n"

                    f"{state.get('report', '')[:200]}"

                )

            )


            print(
                "[memory_save] "
                "Slack notified"
            )

            execution_results.append({
                "action": "Notify #complaints on Slack",
                "success": bool(slack_success),
                "detail": (
                    "Notification sent."
                    if slack_success
                    else "n8n reported the notification did not succeed."
                ),
            })


        except Exception as e:

            print(
                f"[memory_save] "
                f"Slack error: {e}"
            )

            execution_results.append({
                "action": "Notify #complaints on Slack",
                "success": False,
                "detail": str(e),
            })


        # --------------------------------------------------
        # CALENDAR FOLLOW-UP
        # --------------------------------------------------

        try:

            cal_result = create_calendar_event(

                title=(
                    "Follow-up: complaint review"
                ),

                date="",

                description=(
                    state.get(
                        "query",
                        ""
                    )
                )

            )


            print(
                "[memory_save] "
                "Calendar event created"
            )

            execution_results.append({
                "action": "Create follow-up calendar event",
                "success": (
                    bool(cal_result.get("success", False))
                    if isinstance(cal_result, dict)
                    else False
                ),
                "detail": (
                    cal_result.get("message", str(cal_result))
                    if isinstance(cal_result, dict)
                    else "Calendar creation was not confirmed by n8n"
                ),
            })


        except Exception as e:

            print(
                f"[memory_save] "
                f"Calendar error: {e}"
            )

            execution_results.append({
                "action": "Create follow-up calendar event",
                "success": False,
                "detail": str(e),
            })


    # ======================================================
    # SAVE MEMORY
    # ======================================================

    state = {
        **state,
        "execution_results": execution_results,
    }

    return memory_store.memory_save_node(state)


# ==========================================================
# RESPONDER
# (new — this is the piece graph.py had and supervisor.py was
# missing. Runs after memory_save and builds a fresh message
# describing what ACTUALLY happened, using execution_results,
# instead of leaving the pre-approval proposal text — the one
# shown in the approval card — as the final thing returned to
# the user. Without this, approving an action just echoes the
# same card back, whether the action succeeded, failed, or
# silently did nothing.)
# ==========================================================

def responder_node(
    state: AgentState
) -> AgentState:

    print(
        "[Responder] Building final outcome summary..."
    )

    query_type = state.get("query_type", "")
    results = state.get("execution_results", [])
    approved = state.get("approved")
    query = state.get("query", "")

    if approved is False:

        comment = (
            state.get("approval_comment") or ""
        ).strip()

        final_text = (
            "Action rejected \u2014 nothing was executed."
        )

        if comment:

            final_text += f"\n\nYour note: {comment}"

    elif not results:

        # For read-only queries, the report already has the answer
        existing_report = state.get("report", "")
        if existing_report:
            final_text = existing_report
        else:
            final_text = (
                f"Your {query_type.replace('_', ' ')} request "
                f"completed successfully."
            )

    else:

        # Build a clear execution summary with verification
        succeeded = [r for r in results if r.get("success")]
        failed = [r for r in results if not r.get("success")]

        lines = ["## Execution Summary\n"]

        if succeeded:
            lines.append(f"**\u2705 {len(succeeded)} action(s) completed successfully:**\n")
            for r in succeeded:
                lines.append(
                    f"- \u2705 **{r.get('action', 'Action')}** \u2014 "
                    f"{r.get('detail', 'Done')}"
                )
            lines.append("")

        if failed:
            lines.append(f"**\u274c {len(failed)} action(s) failed:**\n")
            for r in failed:
                lines.append(
                    f"- \u274c **{r.get('action', 'Action')}** \u2014 "
                    f"{r.get('detail', 'Unknown error')}"
                )
            lines.append("")

        # Add a brief status line
        if not failed:
            lines.append("*All actions completed. Results saved to memory.*")
        elif not succeeded:
            lines.append("*No actions succeeded. Please review and try again.*")
        else:
            lines.append(f"*{len(succeeded)} succeeded, {len(failed)} failed. Check details above.*")

        final_text = "\n".join(lines)

    print(
        f"[Responder] {len(results)} outcome(s) summarized"
    )

    return {

        "report": final_text,

        "final_response": final_text,

    }


# ==========================================================
# AUTO-COMPLETE (no approval needed — pure info requests)
# ==========================================================
#
# Document/research queries have nothing to approve — there's
# no side effect to gate. Previously EVERY query type paused
# for human_review, so a plain question would sit waiting for
# an approval that had nothing behind it. This saves memory and
# skips the approval pause entirely.
#
# `approved` stays None here, which memory_save_node reads as
# "no approval was required" — distinct from an explicit
# rejection. These runs are persisted like any other.
# ==========================================================

def auto_complete_node(
    state: AgentState
) -> AgentState:

    return memory_store.memory_save_node(state)


# ==========================================================
# HUMAN REVIEW
# ==========================================================

def human_review(
    state: AgentState
) -> AgentState:

    decision = interrupt(

        {

            "message": (

                "Please review the prepared report "
                "and approve or reject the proposed action."

            ),

            "report": state.get(
                "report",
                ""
            ),

            "proposed_actions": state.get(
                "proposed_actions",
                []
            )

        }

    )


    # ------------------------------------------------------
    # SUPPORT BOTH STRING AND DICTIONARY RESUME
    # ------------------------------------------------------

    if isinstance(
        decision,
        dict
    ):

        decision_value = (

            decision.get(
                "decision",
                ""
            )

        )

        comment = (

            decision.get(
                "comment",
                ""
            )

        )

    else:

        decision_value = decision

        comment = ""

    decision_value = str(
        decision_value
    ).lower().strip()


    approved = (

        decision_value
        == "approve"

    )


    print(

        "[HumanReview] "
        f"Decision received: "
        f"{decision_value}"

    )


    return {

        "approved": approved,

        "approval_comment": (

            ""

            if approved

            else comment

        )

    }


# ==========================================================
# REVIEW ROUTER
# ==========================================================

# ==========================================================
# ROUTE AFTER SPECIALIST (only pause for approval when
# there's an actual action to approve)
# ==========================================================

def route_after_specialist(
    state: AgentState
):

    query_type = state.get(
        "query_type",
        "research"
    )

    if query_type in ("document", "research", "calendar_read", "email_read", "jira", "jira_update"):

        return "auto_complete"

    return "human_review"


# ==========================================================
# SUPERVISOR CLASSIFICATION
# ==========================================================

def supervisor_node(
    state: AgentState
) -> AgentState:

    print(
        "[Supervisor] Classifying request..."
    )


    query = state.get(
        "query",
        ""
    )


    query_lower = query.lower()


    # ======================================================
    # EXPLICIT EMAIL READ PRIORITY
    #
    # FIX: added "get" / "fetch" / "pull" / "retrieve" — these
    # were missing, so "get the latest 3 emails from inbox"
    # fell through this check entirely and was misclassified
    # as compose-email downstream.
    # ======================================================

    email_read_verbs = [

        "list",

        "enlist",

        "show",

        "view",

        "check",

        "read",

        "get",

        "fetch",

        "pull",

        "retrieve",

        "what's in",

        "whats in"

    ]

    email_read_nouns = [

        "email",

        "emails",

        "inbox",

        "mail"

    ]

    has_email_read_verb = any(

        verb in query_lower

        for verb in email_read_verbs

    )

    has_email_read_noun = any(

        noun in query_lower

        for noun in email_read_nouns

    )

    if has_email_read_verb and has_email_read_noun:

        print(

            "[Supervisor] "
            "Explicit email READ (list/view inbox) detected"

        )


        return {

            "query_type": "email_read"

        }


        # ======================================================
    # EXPLICIT JIRA PRIORITY (read queries)
    # ======================================================

    jira_keywords = [
        "jira",
        "jira issue",
        "jira issues",
        "ticket",
        "tickets",
        "kanban",
        "pending jira",
        "open jira"
    ]

    if any(kw in query_lower for kw in jira_keywords):
        print(
            "[Supervisor] "
            "Explicit Jira keyword detected"
        )

        return {
            "query_type": "jira"
        }


    # ======================================================
    # EXPLICIT JIRA UPDATE/CREATE PRIORITY
    # (must run BEFORE Slack check because "update the status"
    #  contains words that can be misclassified by the LLM)
    # ======================================================

    jira_update_verbs = [
        "update",
        "change",
        "set",
        "move",
        "modify",
        "edit"
    ]

    jira_update_nouns = [
        "status",
        "priority",
        "summary",
        "description",
        "issue",
        "ticket",
        "jira"
    ]

    # Patterns like "update status of KAN 6 from X to Y"
    # or "set priority of ISSUE-123 to High"
    has_jira_update_verb = any(
        v in query_lower for v in jira_update_verbs
    )

    has_jira_update_noun = any(
        n in query_lower for n in jira_update_nouns
    )

    # Also match "from ... to ..." pattern (status change)
    has_from_to = " from " in query_lower and " to " in query_lower

    # Match issue key patterns like KAN-6, KAN 6, ISSUE-123
    import re as _re
    has_issue_key = bool(_re.search(
        r'\b[A-Z][A-Z0-9]+[\s-]?\d+\b', query
    ))

    if (
        (has_jira_update_verb and has_jira_update_noun)
        or (has_from_to and has_issue_key)
        or (has_jira_update_verb and has_issue_key)
    ):
        print(
            "[Supervisor] "
            "Explicit Jira UPDATE/CREATE detected"
        )

        return {
            "query_type": "jira_update"
        }

    # Catch direct "create jira" / "create ticket" requests
    jira_create_keywords = [
        "create jira",
        "create a jira",
        "new jira",
        "new ticket",
        "create ticket",
        "create a ticket",
        "add jira",
        "add a jira",
        "add ticket",
        "add a ticket"
    ]

    if any(kw in query_lower for kw in jira_create_keywords):
        print(
            "[Supervisor] "
            "Explicit Jira CREATE detected"
        )

        return {
            "query_type": "jira_update"
        }


# ======================================================
    # EXPLICIT SLACK PRIORITY
    # ======================================================

    if "slack" in query_lower:

        print(

            "[Supervisor] "
            "Explicit Slack message detected"

        )


        return {

            "query_type": "slack"

        }


    # ======================================================
    # EXPLICIT BROADCAST EMAIL PRIORITY
    # ======================================================

    broadcast_send_verbs = [

        "email",

        "notify",

        "send",

        "mail",

        "message"

    ]

    broadcast_target_phrases = [

        "all employees",

        "all staff",

        "everyone in the company",

        "entire company",

        "whole company",

        "the whole company",

        "whole team",

        "entire team",

        "all users",

        "everybody",

        "all members",

        "all my employees"

    ]

    has_broadcast_verb = any(

        verb in query_lower

        for verb in broadcast_send_verbs

    )

    has_broadcast_target = any(

        phrase in query_lower

        for phrase in broadcast_target_phrases

    )

    if has_broadcast_verb and has_broadcast_target:

        print(

            "[Supervisor] "
            "Broadcast email to all employees detected"

        )


        return {

            "query_type": "email_broadcast"

        }


    # ======================================================
    # EXPLICIT EMAIL PRIORITY
    # ======================================================

    email_keywords = [

        "send email",

        "send an email",

        "send mail",

        "send a mail",

        "write an email",

        "write to",

        "compose an email",

        "draft an email",

        "email to",

        "mail to",

        "reply to",

        "forward this email"

    ]


    if any(

        keyword in query_lower

        for keyword in email_keywords

    ):

        query_type = "email"


        print(

            "[Supervisor] "
            "Explicit email action detected"

        )


        return {

            "query_type": query_type

        }


    # ======================================================
    # EXPLICIT CALENDAR READ PRIORITY
    # ======================================================

    calendar_read_verbs = [

        "list",

        "enlist",

        "show",

        "view",

        "check",

        "what's on",

        "whats on",

        "upcoming"

    ]

    calendar_read_nouns = [

        "event",

        "events",

        "calendar",

        "schedule",

        "scheduled",

        "meeting",

        "meetings"

    ]

    has_read_verb = any(

        verb in query_lower

        for verb in calendar_read_verbs

    )

    has_calendar_noun = any(

        noun in query_lower

        for noun in calendar_read_nouns

    )

    if has_read_verb and has_calendar_noun:

        print(

            "[Supervisor] "
            "Explicit calendar READ (list/view) detected"

        )


        return {

            "query_type": "calendar_read"

        }


    # ======================================================
    # EXPLICIT CALENDAR PRIORITY
    # ======================================================

    calendar_keywords = [

        "create calendar",

        "create an event",

        "schedule a meeting",

        "schedule meeting",

        "add to calendar",

        "book a meeting",

        "set up a meeting",

        "create event"

    ]


    if any(

        keyword in query_lower

        for keyword in calendar_keywords

    ):

        print(

            "[Supervisor] "
            "Explicit calendar action detected"

        )


        return {

            "query_type": "calendar"

        }


    # ======================================================
    # LLM CLASSIFICATION
    #
    # FIX: added email_read and email_broadcast as real,
    # described categories, since the LLM previously had no
    # way to route a read-style phrasing anywhere but
    # compose-email once it reached the fallback.
    # ======================================================

    classify_prompt = SystemMessage(

        content="""

You are the Supervisor Agent.

Classify the user's PRIMARY INTENT.

Always prioritize the action
the user wants to perform.

Return exactly ONE word.

Allowed categories:

email
email_read
email_broadcast
document
research
complaint
calendar
calendar_read
slack


SLACK:

Use slack when the user wants to post/send a message to
Slack or a team channel.


EMAIL:

Use email when the user wants to:

- send an email
- write an email
- draft an email
- compose an email
- reply to an email
- forward an email

No existing email is being looked up — a NEW email is
being composed and sent.


EMAIL_READ:

Use email_read when the user wants to:

- read, list, view, check, get, fetch, or pull emails
- search emails
- summarize emails
- see what's in the inbox

This is a read-only lookup — no new email is sent.


EMAIL_BROADCAST:

Use email_broadcast when the user wants to send the same
email to a large group (e.g. "all employees", "the whole team").


JIRA:

Use jira when the user wants to:

- list, show, view, check, get, or fetch Jira issues
- see pending or open tickets
- check the kanban board
- review project issues

This is a read-only lookup of Jira data.


JIRA_UPDATE:

Use jira_update when the user wants to:

- update, change, set, or modify a Jira issue
- change the status or priority of an issue
- create a new Jira ticket or issue
- move an issue from one status to another


DOCUMENT:

Use document when the user wants
to search company documents
or uploaded knowledge.


RESEARCH:

Use research when the user explicitly
wants research, investigation,
comparison, or analysis of a topic.


COMPLAINT:

Use complaint when the user wants
to analyze customer complaints
or process complaint emails.


CALENDAR:

Use calendar ONLY when the user wants to
CREATE, schedule, or book a new meeting
or event.


CALENDAR_READ:

Use calendar_read when the user wants to
VIEW, list, show, or check existing
calendar events or their schedule —
no new event is being created.

Return ONLY ONE WORD.
"""

    )


    response = llm.invoke(

        [

            classify_prompt,

            HumanMessage(
                content=query
            )

        ]

    )


    raw = (

        response.content
        .strip()
        .lower()

    )


    print(

        f"[Supervisor] "
        f"Classifier response: {raw}"

    )


    # --------------------------------------------------------
    # FIX: "email_read" and "email_broadcast" both contain
    # "email" as a substring, so they MUST be checked before
    # the generic "email" branch.
    # --------------------------------------------------------

    if "calendar_read" in raw:

        query_type = "calendar_read"


    elif "calendar" in raw:

        query_type = "calendar"


    elif "jira_update" in raw:

        query_type = "jira_update"


    elif "jira" in raw:

        query_type = "jira"


    elif "email_broadcast" in raw:

        query_type = "email_broadcast"


    elif "email_read" in raw:

        query_type = "email_read"


    elif "slack" in raw:

        query_type = "slack"


    elif "complaint" in raw:

        query_type = "complaint"


    elif "document" in raw:

        query_type = "document"


    elif "email" in raw:

        query_type = "email"


    else:

        query_type = "research"


    print(

        f"[Supervisor] "
        f"Query type: {query_type}"

    )


    return {

        "query_type": query_type

    }


# ==========================================================
# ROUTER
# ==========================================================

def supervisor_router(
    state: AgentState
):

    query_type = state.get(
        "query_type",
        "research"
    )


    return {

        "email": "email_agent",

        "email_read": "email_read_agent",

        "email_broadcast": "email_broadcast_agent",

        "complaint": "complaint_agent",

        "document": "rag_agent",

        "research": "research_agent",

        "calendar": "calendar_agent",

        "calendar_read": "calendar_read_agent",

        "slack": "slack_agent",

        "jira": "jira_agent",
        "jira_update": "jira_update_agent"

    }.get(

        query_type,

        "research_agent"

    )


# ==========================================================
# PLANNER
# ==========================================================

def planner_node(
    state: AgentState
) -> AgentState:

    print(
        f"[TRACE] planner_node received query_type = "
        f"{state.get('query_type', '<<MISSING>>')!r}"
    )

    # ── Build work context summary for the planner ──
    work_ctx = ""
    mem_ctx = state.get("memory_context") or {}
    if mem_ctx.get("work_context"):
        work_ctx = mem_ctx["work_context"]

    work_section = ""
    if work_ctx:
        work_section = f"\n\nUSER'S CURRENT WORK CONTEXT:\n{work_ctx}"

    plan_prompt = SystemMessage(

        content=f"""

You are a planning agent for WorkPilot AI.

You have access to the user's current work context including their
tasks, notes, and projects. Use this context to create a more
relevant and actionable plan.

Create a concise plan for the specialist agent.
Do not execute actions.
Return 3-5 concise numbered steps.

IMPORTANT:
- Reference specific tasks, notes, or projects by name when relevant.
- Consider task priorities and deadlines.
- If the request relates to existing work, connect it to the right context.
{work_section}
"""

    )


    response = llm.invoke(

        [

            plan_prompt,

            HumanMessage(

                content=(

                    f"Query: "
                    f"{state['query']}\n"

                    f"Type: "
                    f"{state.get('query_type', '')}"

                )

            )

        ]

    )


    plan_steps = [

        line.strip()

        for line in response.content.strip().split(
            "\n"
        )

        if line.strip()

    ]


    print(

        f"[Planner] "
        f"{len(plan_steps)}-step plan created"

    )


    return {

        "plan": plan_steps

    }


# ==========================================================
# RESEARCH AGENT
# ==========================================================

def research_agent_node(
    state: AgentState
) -> AgentState:

    # ── Inject work context so the research agent is work-aware ──
    work_ctx = ""
    mem_ctx = state.get("memory_context") or {}
    if mem_ctx.get("work_context"):
        work_ctx = mem_ctx["work_context"]

    context_section = ""
    if work_ctx:
        context_section = f"\n\nUSER'S CURRENT WORK CONTEXT (tasks, notes, projects):\n{work_ctx}\n\nUse this context when relevant to give a more personalized answer."

    research_prompt = SystemMessage(

        content=f"""

You are a research assistant for WorkPilot AI.

Provide a thorough, helpful answer
based on the user's request.

Do not invent unsupported details.

When the user asks about their tasks, notes, projects, or work status,
reference the work context provided below.
{context_section}
"""

    )


    response = llm.invoke(

        [

            research_prompt,

            HumanMessage(

                content=state["query"]

            )

        ]

    )

    return {

        "report": response.content

    }


# ==========================================================
# CALENDAR AGENT
# ==========================================================

def calendar_agent_node(
    state: AgentState
) -> AgentState:

    print(
        "[Calendar Agent] Preparing calendar event proposal..."
    )

    print(
        f"[TRACE] calendar_agent_node received query_type = "
        f"{state.get('query_type', '<<MISSING>>')!r}"
    )

    query = state.get(
        "query",
        ""
    )

    prompt = f"""
You are a calendar-event drafting assistant.

The user wants to create a calendar event.

Extract the event details from the request.

USER REQUEST:
{query}

RULES:

1. Extract a concise event title.
2. Extract the date/time exactly as given. If no date/time is
   mentioned, leave it as an empty string — do not invent one.
3. Extract the duration/end time if mentioned (e.g. "for 1
   hour", "until 6pm", "for 30 minutes"). If not mentioned,
   leave it as an empty string — do not invent one.
4. Extract a description only if explicitly present. Do not
   invent details, locations, attendees, or times.
5. Output ONLY valid JSON.

OUTPUT FORMAT:

{{
    "title": "event title",
    "date": "date or datetime as given, or empty string",
    "duration": "duration/end time as given, or empty string",
    "description": "event description or empty string"
}}
"""

    try:

        response = llm.invoke(prompt)

        content = response.content.strip()

        if content.startswith("```"):

            content = (
                content
                .replace("```json", "")
                .replace("```", "")
                .strip()
            )

        event_data = json.loads(content)

    except Exception as e:

        print(
            f"[Calendar Agent] Extraction error: {e}"
        )

        event_data = {

            "title": query[:60] if query else "Event",

            "date": "",

            "duration": "",

            "description": query

        }

    proposed_actions = [

        {

            "tool": "CreateCalendarEvent_Tool",

            "args": {

                "title": event_data.get(
                    "title",
                    "Event"
                ),

                "start": event_data.get(
                    "date",
                    ""
                ),

                "duration": event_data.get(
                    "duration",
                    ""
                ),

                "description": event_data.get(
                    "description",
                    ""
                )

            }

        }

    ]

    print(
        f"[Calendar Agent] Proposed event: "
        f"{proposed_actions[0]['args']}"
    )

    outgoing = {

        "proposed_actions": proposed_actions

    }

    outgoing["report"] = generate_report(

        query=state.get("query", ""),

        query_type="calendar",

        proposed_actions=proposed_actions

    )

    print(
        f"[TRACE] calendar_agent_node returning keys = "
        f"{sorted(outgoing.keys())}"
    )

    return outgoing


# ==========================================================
# SLACK AGENT
# ==========================================================

def slack_agent_node(
    state: AgentState
) -> AgentState:

    print(
        "[Slack Agent] Preparing Slack message proposal..."
    )

    query = state.get(
        "query",
        ""
    )

    # --------------------------------------------------------
    # FIX (human-review bypass): this used to call
    # get_calendar_events(query) with the FULL raw user
    # sentence. That sentence still contains the user's
    # original action language ("send a message to slack to
    # notify the team..."), and it was being forwarded verbatim
    # to n8n's execution-capable AI agent — which has the
    # SendSlackMessage tool attached. n8n's agent read the whole
    # sentence and autonomously sent the Slack message itself,
    # DURING proposal drafting, before human_review ever ran.
    #
    # Fix: extract ONLY a bounded date/time phrase before calling
    # get_calendar_events. If nothing date-like is found, skip
    # the lookup entirely rather than forwarding the raw query.
    # --------------------------------------------------------

    calendar_context = ""

    event_words = [
        "event", "meeting", "schedule", "scheduled", "appointment"
    ]

    if any(word in query.lower() for word in event_words):

        date_phrase = _extract_date_phrase(query)

        if date_phrase:

            try:

                cal_result = get_calendar_events(date_phrase)

                calendar_context = cal_result.get("message", "") or ""

            except Exception as e:

                print(
                    f"[Slack Agent] Calendar context lookup failed: {e}"
                )

        else:

            print(
                "[Slack Agent] No date phrase found in query — "
                "skipping calendar context lookup rather than "
                "forwarding the full query to n8n."
            )

    calendar_section = (

        f"\nCALENDAR CONTEXT (real event data — use this to fill "
        f"in the actual title/date/time; do not invent anything "
        f"beyond what's here):\n{calendar_context}\n"

        if calendar_context

        else ""

    )

    prompt = f"""
You are a Slack message drafting assistant.

The user wants to send a Slack message.

Extract the target channel and the message text.

USER REQUEST:
{query}
{calendar_section}

RULES:

1. Extract the channel if mentioned (e.g. "#general"). If no
   channel is mentioned, use "#general" as the default.
2. If CALENDAR CONTEXT is present above and the user refers to
   an event, use those real details (title/date/time) in the
   message instead of generic phrasing.
3. Do not invent details beyond the user request and, if
   present, CALENDAR CONTEXT.
4. Output ONLY valid JSON.

OUTPUT FORMAT:

{{
    "channel": "#channel-name",
    "message": "the message text"
}}
"""

    try:

        response = llm.invoke(prompt)

        content = response.content.strip()

        if content.startswith("```"):

            content = (
                content
                .replace("```json", "")
                .replace("```", "")
                .strip()
            )

        slack_data = json.loads(content)

    except Exception as e:

        print(
            f"[Slack Agent] Extraction error: {e}"
        )

        slack_data = {

            "channel": "#general",

            "message": query

        }

    proposed_actions = [

        {

            "tool": "Send_Slack",

            "args": {

                "channel": slack_data.get("channel", "#general"),

                "message": slack_data.get("message", query)

            }

        }

    ]

    print(
        f"[Slack Agent] Proposed message: {proposed_actions[0]['args']}"
    )

    report_text = generate_report(

        query=query,

        query_type="slack",

        proposed_actions=proposed_actions

    )

    return {

        "proposed_actions": proposed_actions,

        "report": report_text

    }



# ==========================================================
# JIRA AGENT
# ==========================================================

def jira_agent_node(
    state: AgentState
) -> AgentState:

    print("[Jira Agent] Fetching Jira issues...")

    query = state.get("query", "")

    query_lower = query.lower()
    project = "KAN"
    status = None
    assignee = None

    # Try to extract project key
    project_match = re.search(r'project\s+([A-Z][A-Z0-9]+)', query, re.IGNORECASE)
    if project_match:
        project = project_match.group(1).upper()
    else:
        standalone = re.findall(r'\b([A-Z][A-Z0-9]{1,10})\b', query)
        if standalone:
            project = standalone[0]

    # Try to extract status
    status_keywords = ['pending', 'open', 'in progress', 'done', 'closed', 'to do', 'in review']
    for s in status_keywords:
        if s in query_lower:
            status = s.title()
            break

    # Try to extract assignee
    assignee_match = re.search(r'assigned to\s+([^,]+)', query, re.IGNORECASE)
    if assignee_match:
        assignee = assignee_match.group(1).strip()

    try:
        result = get_jira_issues(
            project=project,
            status=status,
            assignee=assignee,
            max_results=5
        )

        message = result.get("message", "")
        issues = result.get("issues", [])

        if not message and not issues:
            message = "No Jira issues were found for this request."

    except Exception as e:
        print(f"[Jira Agent] Error fetching issues: {e}")
        message = "Sorry, I could not retrieve Jira issues right now - the Jira service may be unavailable."
        issues = []

    report_lines = ["# Jira Issues\n"]
    if message:
        report_lines.append(message)

    if issues:
        report_lines.append(f"\n**Found {len(issues)} issue(s):**\n")
        for issue in issues[:5]:
            key = issue.get("key", "UNKNOWN")
            fields = issue.get("fields", {})
            summary = fields.get("summary", issue.get("summary", "No summary"))
            status_obj = fields.get("status", {})
            if isinstance(status_obj, dict):
                status_name = status_obj.get("name", issue.get("status", "Unknown"))
            else:
                status_name = str(status_obj) if status_obj else "Unknown"
            priority_obj = fields.get("priority", {})
            if isinstance(priority_obj, dict):
                priority_name = priority_obj.get("name", issue.get("priority", "Medium"))
            else:
                priority_name = str(priority_obj) if priority_obj else "Medium"
            assignee_obj = fields.get("assignee", {})
            if isinstance(assignee_obj, dict):
                assignee_name = assignee_obj.get("displayName", "Unassigned")
            else:
                assignee_name = str(assignee_obj) if assignee_obj else "Unassigned"

            report_lines.append(
                f"- **{key}**: {summary}\n"
                f"  Status: {status_name} | Priority: {priority_name} | Assignee: {assignee_name}"
            )

    report_text = "\n".join(report_lines)
    print(f"[Jira Agent] Done - {len(report_text)} chars")

    return {
        "report": report_text,
        "proposed_actions": []
    }


# ==========================================================
# CALENDAR READ AGENT
# ==========================================================

def calendar_read_agent_node(
    state: AgentState
) -> AgentState:

    print(
        "[Calendar Read Agent] Fetching calendar events..."
    )

    query = state.get(
        "query",
        ""
    )

    # --------------------------------------------------------
    # FIX (human-review bypass): same fix as slack_agent —
    # extract ONLY a bounded date/time phrase before calling
    # get_calendar_events. Never forward the raw user query
    # to n8n, as it could contain action language that
    # bypasses human_review.
    # --------------------------------------------------------

    date_phrase = _extract_date_phrase(query)

    if date_phrase:

        calendar_query = date_phrase

    else:

        # No date reference found — use a safe generic lookup
        # rather than forwarding the raw query to n8n.
        calendar_query = "upcoming"

        print(
            "[Calendar Read Agent] No date phrase found — "
            "using safe generic lookup rather than forwarding raw query."
        )

    try:

        result = get_calendar_events(calendar_query)

        message = result.get("message", "")

        if not message:

            message = "No calendar events were found for this request."

    except Exception as e:

        print(
            f"[Calendar Read Agent] Error fetching events: {e}"
        )

        message = (
            "Sorry, I couldn't retrieve calendar events "
            "right now — the calendar service may be unavailable."
        )

    report_text = f"# Calendar Events\n\n{message}"

    print(
        f"[Calendar Read Agent] Done — {len(report_text)} chars"
    )

    return {

        "report": report_text,

        "proposed_actions": []

    }




# ==========================================================
# JIRA UPDATE/CREATE AGENT
# ==========================================================

def jira_update_agent_node(
    state: AgentState
) -> AgentState:

    print("[Jira Update Agent] Processing Jira update/create...")

    query = state.get("query", "")
    query_lower = query.lower()

    # Determine if this is an update or create
    create_keywords = [
        "create", "new", "add a", "add ticket",
        "create ticket", "create jira", "new ticket", "new jira"
    ]
    is_create = any(kw in query_lower for kw in create_keywords)

    if is_create:
        # Use LLM to extract ticket details
        extract_prompt = f"""Extract Jira ticket details from this request.
Return ONLY valid JSON.

REQUEST: {query}

OUTPUT FORMAT:
{{
    "summary": "ticket title",
    "description": "ticket description",
    "priority": "High|Medium|Low"
}}"""

        try:
            response = llm.invoke(extract_prompt)
            content = response.content.strip()
            if content.startswith("```"):
                content = content.replace("```json", "").replace("```", "").strip()
            data = json.loads(content)
        except Exception as e:
            print(f"[Jira Update Agent] Extraction error: {e}")
            data = {
                "summary": query[:80],
                "description": query,
                "priority": "Medium"
            }

        proposed_actions = [{
            "tool": "CreateJiraTicket_Tool",
            "args": {
                "summary": data.get("summary", "New Ticket"),
                "description": data.get("description", ""),
                "priority": data.get("priority", "Medium")
            }
        }]

        report_text = generate_report(
            query=query,
            query_type="jira_update",
            proposed_actions=proposed_actions
        )

        return {
            "proposed_actions": proposed_actions,
            "report": report_text
        }

    else:
        # UPDATE - extract issue key and changes
        # Try to extract issue key (e.g. KAN-6, KAN 6)
        issue_match = re.search(
            r'\b([A-Z][A-Z0-9]+)[\s-](\d+)\b', query, re.IGNORECASE
        )
        if issue_match:
            issue_key = f"{issue_match.group(1).upper()}-{issue_match.group(2)}"
        else:
            issue_match2 = re.search(
                r'\b([A-Z][A-Z0-9]+\d+)\b', query
            )
            issue_key = issue_match2.group(1).upper() if issue_match2 else "UNKNOWN"

        # Determine what field to update
        new_status = None
        new_priority = None

        # Extract status from "from X to Y" or "to X"
        from_to_match = re.search(r'from\s+(.+?)\s+to\s+(.+?)$', query_lower)
        to_match = re.search(r'to\s+(done|completed|closed|in progress|in review|open|to do|pending)', query_lower)

        if from_to_match:
            new_status = from_to_match.group(2).strip().title()
        elif to_match:
            new_status = to_match.group(1).strip().title()

        # Check for priority change
        priority_match = re.search(r'priority\s+to\s+(high|medium|low|critical|highest|lowest)', query_lower)
        if priority_match:
            new_priority = priority_match.group(1).strip().title()

        proposed_actions = [{
            "tool": "UpdateJiraIssue_Tool",
            "args": {
                "issue_key": issue_key,
                "status": new_status,
                "priority": new_priority
            }
        }]

        # Build the report
        change_parts = []
        if new_status:
            change_parts.append(f"Status -> {new_status}")
        if new_priority:
            change_parts.append(f"Priority -> {new_priority}")

        change_desc = ", ".join(change_parts) if change_parts else "Update requested"

        report_text = (
            f"## Jira Issue Update\n\n"
            f"**Issue:** {issue_key}\n\n"
            f"**Changes:** {change_desc}\n"
        )

        print(f"[Jira Update Agent] Issue: {issue_key}, Changes: {change_desc}")

        return {
            "proposed_actions": proposed_actions,
            "report": report_text
        }


# ==========================================================
# BUILD GRAPH
# ==========================================================

def build_supervisor_graph():

    graph = StateGraph(
        AgentState
    )


    # ======================================================
    # NODES
    # ======================================================

    graph.add_node("memory_load", memory_load_node)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("planner", planner_node)
    graph.add_node("email_agent", prepare_new_email)
    graph.add_node("email_read_agent", list_recent_emails)
    graph.add_node("email_broadcast_agent", prepare_broadcast_email)
    graph.add_node("complaint_agent", analyze_complaint_emails)
    graph.add_node("rag_agent", rag_agent)
    graph.add_node("research_agent", research_agent_node)
    graph.add_node("calendar_agent", calendar_agent_node)
    graph.add_node("calendar_read_agent", calendar_read_agent_node)
    graph.add_node("jira_agent", jira_agent_node)
    graph.add_node("jira_update_agent", jira_update_agent_node)
    graph.add_node("slack_agent", slack_agent_node)
    graph.add_node("human_review", human_review)
    graph.add_node("memory_save", memory_save_node)
    graph.add_node("auto_complete", auto_complete_node)

    # NEW — the missing "tell the user what actually happened" step
    graph.add_node("responder", responder_node)


    # ======================================================
    # ENTRY
    # ======================================================

    graph.set_entry_point("memory_load")

    graph.add_edge("memory_load", "supervisor")


    # ======================================================
    # SUPERVISOR → PLANNER
    # ======================================================

    graph.add_conditional_edges(

        "supervisor",

        supervisor_router,

        {

            "email_agent": "planner",

            "email_read_agent": "planner",

            "email_broadcast_agent": "planner",

            "complaint_agent": "planner",

            "rag_agent": "planner",

            "research_agent": "planner",

            "calendar_agent": "planner",

            "calendar_read_agent": "planner",

            "slack_agent": "planner",

            "jira_agent": "planner",
            "jira_update_agent": "planner"

        }

    )


    # ======================================================
    # PLANNER → SPECIALIST
    # ======================================================

    graph.add_conditional_edges(

        "planner",

        supervisor_router,

        {

            "email_agent": "email_agent",

            "email_read_agent": "email_read_agent",

            "email_broadcast_agent": "email_broadcast_agent",

            "complaint_agent": "complaint_agent",

            "rag_agent": "rag_agent",

            "research_agent": "research_agent",

            "calendar_agent": "calendar_agent",

            "calendar_read_agent": "calendar_read_agent",

            "slack_agent": "slack_agent",

            "jira_agent": "jira_agent",
            "jira_update_agent": "jira_update_agent"

        }

    )


    # ======================================================
    # SPECIALIST → (HITL only if there's something to approve)
    # ======================================================

    for specialist_node in (
        "email_agent",
        "email_read_agent",
        "email_broadcast_agent",
        "complaint_agent",
        "rag_agent",
        "research_agent",
        "calendar_agent",
        "calendar_read_agent",
        "slack_agent",
        "jira_agent",
        "jira_update_agent"
    ):

        graph.add_conditional_edges(

            specialist_node,

            route_after_specialist,

            {

                "human_review": "human_review",

                "auto_complete": "auto_complete"

            }

        )


    # ======================================================
    # HITL ROUTING
    # ======================================================

    graph.add_edge(

        "human_review",

        "memory_save"

    )


    # ======================================================
    # SAVE → RESPONDER → END
    #
    # CHANGED: memory_save used to go straight to END, leaving
    # the pre-approval proposal text (state["report"]) as the
    # final thing returned to the user regardless of what
    # actually happened during execution. Now it routes through
    # responder_node first, which overwrites report/final_response
    # with a real outcome summary built from execution_results.
    #
    # auto_complete still goes straight to END — there's nothing
    # to report on for read-only queries; the existing report
    # text (the answer itself) is already the right final output.
    # ======================================================

    graph.add_edge("memory_save", "responder")
    graph.add_edge("responder", END)

    graph.add_edge("auto_complete", END)


    # ======================================================
    # CHECKPOINT
    # ======================================================

    return graph.compile(
        checkpointer=MemorySaver()
    )


# ==========================================================
# RUN AGENT (manual/CLI testing)
# ==========================================================

def run_agent(

    query: str,

    user: str = "default",

    session_id: str = "default"

) -> str:


    app = build_supervisor_graph()


    initial_state: AgentState = {

        "query": query,

        "emails": [],

        "context": "",

        "report": "",

        "messages": [

            HumanMessage(

                content=query

            )

        ],

        "query_type": "",

        "plan": [],

        "user": user,

        "session_id": session_id,

        "memory_context": None,

        "approved": None,

        "approval_comment": "",

        "proposed_actions": [],

        "execution_results": [],

        "final_response": ""

    }


    config = {

        "configurable": {

            "thread_id": session_id

        }

    }


    print(

        f"\n{'=' * 60}\n"

        f"Query : {query}\n"

        f"User  : {user}\n"

        f"Session: {session_id}\n"

        f"{'=' * 60}"

    )


    result = app.invoke(

        initial_state,

        config=config

    )


    snapshot = app.get_state(config)


    if not snapshot.next:

        print(

            "\nCompleted without requiring approval."

        )

        return result.get("report", "")


    print(

        "\nREPORT GENERATED — "
        "AWAITING APPROVAL"

    )


    print(

        result.get(

            "report",

            "No report generated."

        )

    )


    while True:

        decision = input(

            "Approve this report? "
            "(approve / reject): "

        ).strip().lower()


        if decision in (

            "approve",

            "reject"

        ):

            break


        print(

            "Please type exactly "
            "'approve' or 'reject'."

        )


    final_result = app.invoke(

        Command(

            resume={

                "decision": decision,

                "comment": ""

            }

        ),

        config=config

    )


    if final_result.get("approved"):

        print(

            "\nReport approved — "
            "approved actions executed."

        )

        print(

            final_result.get(
                "final_response",
                final_result.get("report", "")
            )

        )

    else:

        print(

            "\nReport rejected — "
            "nothing executed."

        )


    return final_result.get(
        "final_response",
        final_result.get("report", "")
    )