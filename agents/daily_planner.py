"""
agents/daily_planner.py
=======================
Daily Planner Agent for WorkPilot AI.

Reads the user's full work context — tasks, notes, calendar events,
recent emails, and relevant company knowledge — then generates a
structured daily productivity plan.

Called via the /plan-day endpoint or the "Plan My Day" button.
"""

import os
import json
from datetime import datetime

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

import work_manager
from tools.n8n_client import get_calendar_events, get_recent_emails


# ==========================================================
# ENVIRONMENT
# ==========================================================

load_dotenv()


# ==========================================================
# LLM
# ==========================================================

llm = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.3,
)


# ==========================================================
# DAILY PLANNER
# ==========================================================

def plan_my_day(user: str) -> dict:
    """
    Generate a structured daily plan for the user.

    Returns:
        {
            "greeting": "☀️ Good morning, Name",
            "summary": "You have 6 hours of productive time...",
            "plan": {
                "high_priority": [...],
                "medium_priority": [...],
                "low_priority": [...],
                "breaks": [...],
                "recommendations": [...]
            },
            "raw_text": "...(formatted markdown)...",
            "context_used": {
                "tasks_count": N,
                "notes_count": N,
                "has_calendar": bool,
                "has_emails": bool
            }
        }
    """

    # ── 1. Gather work context ──────────────────────────────
    work_context = work_manager.get_work_context(user)
    task_stats   = work_manager.get_task_stats(user)
    tasks        = work_manager.get_tasks(user)
    notes        = work_manager.get_notes(user)

    # ── 2. Try to fetch calendar events ─────────────────────
    calendar_context = ""
    has_calendar = False
    try:
        cal_result = get_calendar_events("today and tomorrow")
        if cal_result and cal_result.get("message"):
            calendar_context = cal_result["message"]
            has_calendar = True
    except Exception as e:
        print(f"[DailyPlanner] Calendar fetch failed: {e}")

    # ── 3. Try to fetch recent emails ───────────────────────
    email_context = ""
    has_emails = False
    try:
        email_result = get_recent_emails("unread emails from today")
        if email_result and email_result.get("message"):
            email_context = email_result["message"]
            has_emails = True
    except Exception as e:
        print(f"[DailyPlanner] Email fetch failed: {e}")

    # ── 4. Build the prompt ─────────────────────────────────
    now = datetime.now()
    greeting_time = "morning" if now.hour < 12 else (
        "afternoon" if now.hour < 17 else "evening"
    )

    calendar_section = (
        f"\nCALENDAR EVENTS:\n{calendar_context}\n"
        if calendar_context
        else "\nCALENDAR EVENTS: (no events found or calendar unavailable)\n"
    )

    email_section = (
        f"\nRECENT EMAILS:\n{email_context}\n"
        if email_context
        else "\nRECENT EMAILS: (no recent emails or email service unavailable)\n"
    )

    prompt = f"""
You are WorkPilot AI, an intelligent daily planning assistant.

Today is {now.strftime('%A, %B %d, %Y')}.

The user is {user}.

Their current work context:
{work_context}
{calendar_section}
{email_section}

TASK STATS:
- Total tasks: {task_stats['total']}
- Completed: {task_stats['completed']}
- Pending: {task_stats['pending']}

YOUR JOB:
Create a structured daily productivity plan that helps the user
make the most of their day.

RULES:
1. Prioritize HIGH priority tasks first.
2. Schedule MEDIUM priority tasks after high priority.
3. Include LOW priority tasks only if there's time.
4. Suggest break times between tasks.
5. Consider calendar events when planning.
6. Reference email items that need attention.
7. Be specific about task ordering and time allocation.
8. Keep the tone warm, encouraging, and professional.
9. Do NOT invent tasks or details not present in the context.

OUTPUT FORMAT (valid JSON only, no markdown):
{{
    "greeting": "a warm greeting using the time of day and user name",
    "summary": "a 1-2 sentence overview of the day's workload",
    "plan": {{
        "high_priority": [
            {{"task": "task name", "estimated_time": "30 min", "reason": "why this is first"}}
        ],
        "medium_priority": [
            {{"task": "task name", "estimated_time": "20 min", "reason": "brief reason"}}
        ],
        "low_priority": [
            {{"task": "task name", "estimated_time": "15 min", "reason": "brief reason"}}
        ],
        "breaks": [
            {{"after": "task name", "duration": "5 min", "type": "short break"}}
        ],
        "recommendations": [
            "a specific recommendation for the user"
        ]
    }}
}}
"""

    # ── 5. Call LLM ─────────────────────────────────────────
    try:
        response = llm.invoke([
            SystemMessage(content="You are a helpful daily planning assistant. Return ONLY valid JSON."),
            HumanMessage(content=prompt),
        ])

        content = response.content.strip()

        # Strip markdown fences if present
        if content.startswith("```"):
            content = (
                content
                .replace("```json", "")
                .replace("```", "")
                .strip()
            )

        plan_data = json.loads(content)

    except json.JSONDecodeError as e:
        print(f"[DailyPlanner] JSON parse error: {e}")
        plan_data = _fallback_plan(user, tasks, task_stats, greeting_time)

    except Exception as e:
        print(f"[DailyPlanner] LLM error: {e}")
        plan_data = _fallback_plan(user, tasks, task_stats, greeting_time)

    # ── 6. Attach email summary data ────────────────────────
    if has_emails and email_context:
        plan_data["email_summary"] = email_context[:500]
    else:
        plan_data["email_summary"] = None

    # ── 7. Build raw markdown ───────────────────────────────
    raw_text = _build_markdown(plan_data)

    return {
        "greeting":     plan_data.get("greeting", f"Good {greeting_time}, {user}!"),
        "summary":      plan_data.get("summary", "Here's your plan for today."),
        "plan":         plan_data.get("plan", {}),
        "raw_text":     raw_text,
        "email_summary": plan_data.get("email_summary"),
        "context_used": {
            "tasks_count": len(tasks),
            "notes_count": len(notes),
            "has_calendar": has_calendar,
            "has_emails":   has_emails,
        },
    }


# ==========================================================
# FALLBACK (if LLM fails)
# ==========================================================

def _fallback_plan(
    user: str,
    tasks: list,
    stats: dict,
    greeting_time: str,
) -> dict:
    """Build a simple plan from DB data when the LLM is unavailable."""

    pending = [t for t in tasks if not t.get("completed")]

    high   = [{"task": t["title"], "estimated_time": "30 min", "reason": "High priority"}
              for t in pending if t.get("priority") == "High"]
    medium = [{"task": t["title"], "estimated_time": "20 min", "reason": "Medium priority"}
              for t in pending if t.get("priority") == "Medium"]
    low    = [{"task": t["title"], "estimated_time": "15 min", "reason": "Low priority"}
              for t in pending if t.get("priority") == "Low"]

    return {
        "greeting": f"Good {greeting_time}, {user}! 👋",
        "summary":  f"You have {stats['pending']} pending tasks today.",
        "plan": {
            "high_priority":   high,
            "medium_priority": medium,
            "low_priority":    low,
            "breaks": [
                {"after": "every 2 tasks", "duration": "5 min", "type": "stretch break"}
            ],
            "recommendations": [
                "Complete high priority tasks first for maximum impact.",
                "Take regular breaks to maintain focus.",
                "Check your emails for urgent items that need a response.",
            ],
        },
        "email_summary": None,
    }


# ==========================================================
# MARKDOWN RENDERER
# ==========================================================

def _build_markdown(plan_data: dict) -> str:
    """Convert the plan dict to a readable markdown string."""

    lines = []

    greeting = plan_data.get("greeting", "")
    if greeting:
        lines.append(f"### {greeting}\n")

    summary = plan_data.get("summary", "")
    if summary:
        lines.append(f"{summary}\n")

    plan = plan_data.get("plan", {})

    # High priority
    hp = plan.get("high_priority", [])
    if hp:
        lines.append("**🔴 High Priority Tasks**")
        for item in hp:
            task = item.get("task", "")
            time = item.get("estimated_time", "")
            lines.append(f"- {task} *({time})*")
        lines.append("")

    # Medium priority
    mp = plan.get("medium_priority", [])
    if mp:
        lines.append("**🟡 Medium Priority Tasks**")
        for item in mp:
            task = item.get("task", "")
            time = item.get("estimated_time", "")
            lines.append(f"- {task} *({time})*")
        lines.append("")

    # Low priority
    lp = plan.get("low_priority", [])
    if lp:
        lines.append("**🔵 Low Priority Tasks**")
        for item in lp:
            task = item.get("task", "")
            time = item.get("estimated_time", "")
            lines.append(f"- {task} *({time})*")
        lines.append("")

    # Email summary
    email_summary = plan_data.get("email_summary")
    if email_summary:
        lines.append("**📧 Email Summary**")
        lines.append(email_summary[:400])
        lines.append("")

    # Breaks
    breaks = plan.get("breaks", [])
    if breaks:
        lines.append("**☕ Break Schedule**")
        for b in breaks:
            after = b.get("after", "")
            dur   = b.get("duration", "")
            btype = b.get("type", "break")
            lines.append(f"- {btype} after {after} — {dur}")
        lines.append("")

    # Recommendations
    recs = plan.get("recommendations", [])
    if recs:
        lines.append("**💡 Recommendations**")
        for r in recs:
            lines.append(f"- {r}")

    return "\n".join(lines)
