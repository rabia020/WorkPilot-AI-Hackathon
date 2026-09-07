# ==========================================================
# app.py
# WORKPILOT AI — AUTONOMOUS AI WORK ASSISTANT API
# ==========================================================
#
# Unified backend for WorkPilot:
#   - LangGraph supervisor (RAG, email, calendar, Slack, HITL)
#   - Work management (tasks, notes, projects, dashboard)
#   - Daily planning, work context, demo mode
#
# Endpoints:
#   /chat, /review, /rag, /emails, /health
#   /tasks, /notes, /projects, /dashboard, /plan-day,
#   /work-context, /demo
# ==========================================================

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langgraph.types import Command
from langchain_core.messages import HumanMessage
from typing import Optional

from supervisor import build_supervisor_graph
from rag.rag_chat import ask_rag
from tools.n8n_client import get_emails, get_calendar_events
import work_manager
import project_manager
from agents.daily_planner import plan_my_day
from demo_data import seed_demo_data
import re


# ==========================================================
# TASK AUTO-CREATION FROM AI RESPONSES
# ==========================================================

# Only auto-create tasks when the user explicitly asks for it
_TASK_CREATION_INTENT = re.compile(
    r'\b(create|add|make)\b.*\b(task|item|todo|to-do)\b',
    re.IGNORECASE
)


def _extract_and_create_tasks(report: str, user: str, query: str) -> list:
    """
    Only create tasks when the user explicitly asks for task creation.
    Returns list of created tasks.
    """
    if not report or not user:
        return []

    # Only trigger on explicit task-creation intent
    if not _TASK_CREATION_INTENT.search(query):
        return []

    created = []
    lines = report.split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Match markdown bullet items: - task name, * task name
        task_match = re.match(
            r'^[-*]\s+(.+)$|^(\d+)[.)]\s+(.+)$',
            line
        )
        if not task_match:
            continue

        task_text = (
            (task_match.group(1) or task_match.group(3) or "").strip()
        )

        if not task_text or len(task_text) < 5:
            continue

        # Skip section headers
        if task_text.startswith("#") or task_text.startswith("**"):
            continue

        skip_words = [
            "summary", "conclusion", "recommendation",
            "overview", "findings", "analysis",
            "approval required", "proposed actions",
            "what actually happened", "executive summary",
            "recipient", "subject", "message", "channel",
            "title", "date", "description", "break",
        ]
        if any(sw in task_text.lower() for sw in skip_words):
            continue

        # Determine priority from context
        priority = "Medium"
        query_lower = query.lower()
        if any(w in query_lower for w in ["urgent", "critical", "high priority", "asap"]):
            priority = "High"

        # Don't create duplicates
        existing_tasks = work_manager.get_tasks(user)
        text_lower = task_text.lower()
        is_duplicate = any(
            text_lower in t.get("title", "").lower()
            or t.get("title", "").lower() in text_lower
            for t in existing_tasks
        )
        if is_duplicate:
            continue

        try:
            task = work_manager.create_task(
                user=user,
                title=task_text[:200],
                priority=priority,
            )
            if task:
                created.append(task)
        except Exception as e:
            print(f"[TaskAutoCreate] Failed to create task: {e}")

    if created:
        print(f"[TaskAutoCreate] Created {len(created)} tasks for {user}")

    return created


# ==========================================================
# FASTAPI APPLICATION
# ==========================================================

app = FastAPI(
    title="WorkPilot AI — Autonomous AI Work Assistant",
    version="2.0.0",
    description=(
        "An AI employee that understands your work, plans your day, "
        "and executes tasks for you."
    )
)


# ==========================================================
# BUILD GRAPH ONCE
# ==========================================================

try:

    app_graph = build_supervisor_graph()

    print("[app] Supervisor graph initialized successfully")

except Exception:

    print("\n[app] ERROR INITIALIZING SUPERVISOR GRAPH")

    import traceback

    traceback.print_exc()

    app_graph = None


# ==========================================================
# STORE PAUSED SESSIONS
# ==========================================================

paused_sessions = {}


# ==========================================================
# ROOT ENDPOINT
# ==========================================================

@app.get("/")
def home():

    return {

        "status": "running",

        "service": "WorkPilot AI — Autonomous AI Work Assistant",

        "message": (
            "An AI employee that understands your work, plans your day, and executes tasks for you."
        )

    }


# ==========================================================
# REQUEST MODELS
# ==========================================================

class ChatRequest(BaseModel):

    query: str

    user: str = "default"

    session_id: str = "default"


class ReviewRequest(BaseModel):

    session_id: str

    decision: str

    comment: str = ""


class RagRequest(BaseModel):

    question: str


# ==========================================================
# HEALTH CHECK
# ==========================================================

@app.get("/health")
def health():

    return {

        "status": "healthy",

        "graph_loaded": app_graph is not None,

        "paused_sessions": len(paused_sessions)

    }


# ==========================================================
# EMAIL ENDPOINT
# ==========================================================

@app.get("/emails")
def read_emails():

    try:

        emails = get_emails(

            label="complaints",

            days=30

        )

        return {

            "status": "success",

            "count": len(emails),

            "emails": emails

        }

    except Exception as e:

        import traceback

        traceback.print_exc()

        raise HTTPException(

            status_code=500,

            detail=str(e)

        )


# ==========================================================
# CHAT ENDPOINT
# ==========================================================

@app.post("/chat")
async def chat(req: ChatRequest):

    if app_graph is None:

        raise HTTPException(

            status_code=500,

            detail=(
                "Supervisor graph is not initialized. "
                "Check the FastAPI terminal."
            )

        )

    # ------------------------------------------------------
    # FIX: reject empty/missing session ids with a clear
    # error instead of the generic 422 the Streamlit 422 bug
    # produced (that root cause is fixed on the client side
    # in chat_panel.py / streamlit_app.py, this is a backstop).
    # ------------------------------------------------------

    if not req.session_id or not req.session_id.strip():

        raise HTTPException(

            status_code=422,

            detail="session_id must be a non-empty string."

        )

    try:

        print("\n" + "=" * 70)
        print("NEW ENTERPRISE AI REQUEST")
        print("=" * 70)
        print(f"User       : {req.user}")
        print(f"Session ID : {req.session_id}")
        print(f"Query      : {req.query}")
        print("=" * 70)

        # ==================================================
        # INITIAL STATE
        # ==================================================

        initial_state = {

            "query": req.query,

            "user": req.user,

            "session_id": req.session_id,

            "plan": [],

            "emails": [],

            "context": "",

            "report": "",

            "messages": [

                HumanMessage(
                    content=req.query
                )

            ],

            "approved": None,

            "approval_comment": "",

            "query_type": "",

            "memory_context": None,

            "proposed_actions": []

        }

        config = {

            "configurable": {

                "thread_id": req.session_id

            }

        }

        # ==================================================
        # RUN GRAPH
        # ==================================================

        result = app_graph.invoke(

            initial_state,

            config=config

        )

        snapshot = app_graph.get_state(config)

        current_state = snapshot.values or result or {}

        report = (

            current_state.get("report")

            or current_state.get("final_response")

            or ""

        )

        proposed_actions = current_state.get(

            "proposed_actions",

            []

        )

        # ==================================================
        # HUMAN REVIEW REQUIRED
        # ==================================================

        if snapshot.next:

            print("\n[app] GRAPH PAUSED FOR HUMAN APPROVAL")

            paused_sessions[req.session_id] = True

            return {

                "status": "awaiting_approval",

                "message": (

                    "The AI has prepared a response "
                    "and proposed actions for review."

                ),

                "session_id": req.session_id,

                "query": req.query,

                "report": report,

                "final_response": report,

                "proposed_actions": proposed_actions,

                "next": list(snapshot.next)

            }

        # ==================================================
        # COMPLETED WITHOUT REVIEW
        # (document / research queries — nothing to approve)
        # ==================================================

        print("\n[app] GRAPH COMPLETED")

        # Auto-create tasks from AI response
        auto_tasks = _extract_and_create_tasks(
            report, req.user, req.query
        )

        response_data = {

            "status": "completed",

            "session_id": req.session_id,

            "report": report,

            "final_response": report,

            "proposed_actions": proposed_actions,

            "emails": len(

                current_state.get("emails", [])

            ),

            "approved": current_state.get("approved"),

            "execution_status": current_state.get("status"),

            "error": current_state.get("error")

        }

        if auto_tasks:
            response_data["auto_created_tasks"] = [
                {"title": t.get("title"), "priority": t.get("priority")}
                for t in auto_tasks
            ]

        return response_data

    except Exception as e:

        print("\n[app] CHAT ENDPOINT ERROR")

        import traceback

        traceback.print_exc()

        raise HTTPException(

            status_code=500,

            detail=str(e)

        )


# ==========================================================
# HUMAN REVIEW ENDPOINT
# ==========================================================

@app.post("/review")
async def review(req: ReviewRequest):

    decision = req.decision.strip().lower()

    if decision not in ("approve", "reject"):

        raise HTTPException(

            status_code=400,

            detail="Decision must be either 'approve' or 'reject'."

        )

    if req.session_id not in paused_sessions:

        raise HTTPException(

            status_code=404,

            detail=f"No paused session found for {req.session_id}"

        )

    config = {

        "configurable": {

            "thread_id": req.session_id

        }

    }

    try:

        print("\n" + "=" * 70)
        print("HUMAN REVIEW")
        print("=" * 70)
        print(f"Session : {req.session_id}")
        print(f"Decision: {decision}")
        print(f"Comment : {req.comment}")
        print("=" * 70)

        # ==================================================
        # RESUME GRAPH
        # ==================================================

        final_state = app_graph.invoke(

            Command(

                resume={

                    "decision": decision,

                    "comment": req.comment

                }

            ),

            config=config

        )

        paused_sessions.pop(req.session_id, None)

        final_report = (

            final_state.get("report")

            or final_state.get("final_response")

            or ""

        )

        return {

            "status": "approved" if decision == "approve" else "rejected",

            "approved": decision == "approve",

            "session_id": req.session_id,

            "report": final_report,

            "final_response": final_report,

            "proposed_actions": final_state.get("proposed_actions", []),

            "execution_status": final_state.get("status"),

            "error": final_state.get("error")

        }

    except Exception as e:

        print("\n[app] REVIEW ERROR")

        import traceback

        traceback.print_exc()

        raise HTTPException(

            status_code=500,

            detail=str(e)

        )


# ==========================================================
# RAG ENDPOINT
# ==========================================================

@app.post("/rag")
async def rag(req: RagRequest):

    try:

        answer = ask_rag(req.question)

        return {

            "status": "success",

            "answer": answer

        }

    except Exception as e:

        print("\n[app] RAG ERROR")

        import traceback

        traceback.print_exc()

        raise HTTPException(

            status_code=500,

            detail=str(e)

        )


# ==========================================================
# WORKPILOT — TASK MANAGEMENT
# ==========================================================

class TaskCreate(BaseModel):
    title: str
    description: str = ""
    due_date: Optional[str] = None
    priority: str = "Medium"

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[str] = None
    priority: Optional[str] = None
    completed: Optional[bool] = None


@app.get("/tasks")
def list_tasks(user: str = "default"):
    try:
        return {"status": "success", "tasks": work_manager.get_tasks(user)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tasks")
def create_task_endpoint(req: TaskCreate, user: str = "default"):
    try:
        task = work_manager.create_task(
            user=user,
            title=req.title,
            description=req.description,
            due_date=req.due_date,
            priority=req.priority,
        )
        return {"status": "success", "task": task}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/tasks/{task_id}")
def update_task_endpoint(task_id: str, req: TaskUpdate, user: str = "default"):
    try:
        updates = {k: v for k, v in req.dict().items() if v is not None}
        task = work_manager.update_task(task_id, user, **updates)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"status": "success", "task": task}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/tasks/{task_id}")
def delete_task_endpoint(task_id: str, user: str = "default"):
    try:
        deleted = work_manager.delete_task(task_id, user)
        if not deleted:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"status": "success", "deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tasks/{task_id}/toggle")
def toggle_task_endpoint(task_id: str, user: str = "default"):
    try:
        task = work_manager.toggle_task(task_id, user)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"status": "success", "task": task}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================================
# WORKPILOT — NOTES
# ==========================================================

class NoteCreate(BaseModel):
    title: str
    content: str = ""

class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None


@app.get("/notes")
def list_notes(user: str = "default"):
    try:
        return {"status": "success", "notes": work_manager.get_notes(user)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/notes")
def create_note_endpoint(req: NoteCreate, user: str = "default"):
    try:
        note = work_manager.create_note(user=user, title=req.title, content=req.content)
        return {"status": "success", "note": note}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/notes/{note_id}")
def update_note_endpoint(note_id: str, req: NoteUpdate, user: str = "default"):
    try:
        updates = {k: v for k, v in req.dict().items() if v is not None}
        note = work_manager.update_note(note_id, user, **updates)
        if not note:
            raise HTTPException(status_code=404, detail="Note not found")
        return {"status": "success", "note": note}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/notes/{note_id}")
def delete_note_endpoint(note_id: str, user: str = "default"):
    try:
        deleted = work_manager.delete_note(note_id, user)
        if not deleted:
            raise HTTPException(status_code=404, detail="Note not found")
        return {"status": "success", "deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================================
# WORKPILOT — DASHBOARD
# ==========================================================

@app.get("/dashboard/{user}")
def get_dashboard(user: str):
    try:
        stats = work_manager.get_dashboard_stats(user)
        return {"status": "success", **stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================================
# WORKPILOT — DAILY PLANNER
# ==========================================================

class PlanDayRequest(BaseModel):
    user: str = "default"


@app.post("/plan-day")
def plan_day_endpoint(req: PlanDayRequest):
    try:
        result = plan_my_day(req.user)
        return {"status": "success", **result}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================================
# WORKPILOT — WORK CONTEXT (for AI chat injection)
# ==========================================================

@app.get("/work-context/{user}")
def get_work_context_endpoint(user: str):
    try:
        context = work_manager.get_work_context(user)
        return {"status": "success", "context": context}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================================
# WORKPILOT — DEMO MODE
# ==========================================================

@app.post("/demo/{user}")
def seed_demo(user: str):
    """Populate demo tasks and notes for the given user."""
    try:
        result = seed_demo_data(user)
        return {"status": "success", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================================
# WORKPILOT — PROJECTS
# ==========================================================

class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    color: str = "#8f75ca"

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    status: Optional[str] = None


@app.get("/projects")
def list_projects(user: str = "default", status: Optional[str] = None):
    try:
        projects = project_manager.get_projects(user, status=status)
        return {"status": "success", "projects": projects}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/projects")
def create_project_endpoint(req: ProjectCreate, user: str = "default"):
    try:
        project = project_manager.create_project(
            user=user,
            name=req.name,
            description=req.description,
            color=req.color,
        )
        return {"status": "success", "project": project}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/projects/{project_id}")
def get_project_context_endpoint(project_id: str, user: str = "default"):
    try:
        context = project_manager.get_project_context(project_id, user)
        if not context:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"status": "success", **context}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/projects/{project_id}")
def update_project_endpoint(project_id: str, req: ProjectUpdate, user: str = "default"):
    try:
        updates = {k: v for k, v in req.dict().items() if v is not None}
        project = project_manager.update_project(project_id, user, **updates)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"status": "success", "project": project}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/projects/{project_id}")
def delete_project_endpoint(project_id: str, user: str = "default"):
    try:
        deleted = project_manager.delete_project(project_id, user)
        if not deleted:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"status": "success", "deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/calendar-events")
def get_calendar_events_endpoint(user: str = "default", month: Optional[int] = None, year: Optional[int] = None):
    """
    Fetch calendar events from Google Calendar via n8n.
    Optional month/year filters; if omitted, fetches events for this month.
    """
    from datetime import date as _date
    try:
        today = _date.today()
        m = month or today.month
        y = year or today.year

        # Build a natural-language query scoped to the requested month
        month_name = _date(y, m, 1).strftime("%B")
        query = f"events in {month_name} {y}"

        result = get_calendar_events(query)

        events = []
        raw = result.get("raw", {})

        # Normalize the raw response into a flat list of event dicts
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict):
                    events.append(_normalize_event(item))
        elif isinstance(raw, dict):
            # Could be nested under "events" key
            inner = raw.get("events", raw.get("items", []))
            if isinstance(inner, list):
                for item in inner:
                    if isinstance(item, dict):
                        events.append(_normalize_event(item))
            # Or a single event
            elif raw.get("title") or raw.get("summary"):
                events.append(_normalize_event(raw))

        return {"events": events, "raw_message": result.get("message", "")}

    except Exception as e:
        return {"events": [], "error": str(e)}


def _normalize_event(item: dict) -> dict:
    """Normalize a raw n8n/Google Calendar event into a consistent dict."""
    # Google Calendar uses 'summary' for title, n8n may use 'title'
    title = item.get("title") or item.get("summary") or "Event"

    # Try to extract a date (YYYY-MM-DD) from various field names
    date_str = (
        item.get("date")
        or item.get("start_date")
        or item.get("start")
        or ""
    )
    if isinstance(date_str, dict):
        # Google Calendar format: {"date": "2026-09-05"} or {"dateTime": "..."}
        date_str = date_str.get("date") or date_str.get("dateTime") or ""

    # Extract time
    time_str = item.get("time") or item.get("start_time") or ""
    if isinstance(item.get("start"), dict):
        dt = item["start"].get("dateTime", "")
        if "T" in str(dt):
            time_str = dt.split("T")[1][:5] if not time_str else time_str

    # Extract end time
    end_time = item.get("end_time") or ""
    if isinstance(item.get("end"), dict):
        dt = item["end"].get("dateTime", "")
        if "T" in str(dt):
            end_time = dt.split("T")[1][:5] if not end_time else end_time

    return {
        "title": title,
        "date": str(date_str)[:10] if date_str else "",
        "time": time_str,
        "end_time": end_time,
        "description": item.get("description", ""),
    }


@app.post("/projects/{project_id}/link-task/{task_id}")
def link_task_endpoint(project_id: str, task_id: str, user: str = "default"):
    try:
        linked = project_manager.link_task_to_project(task_id, project_id, user)
        if not linked:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"status": "success", "linked": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/projects/{project_id}/link-note/{note_id}")
def link_note_endpoint(project_id: str, note_id: str, user: str = "default"):
    try:
        linked = project_manager.link_note_to_project(note_id, project_id, user)
        if not linked:
            raise HTTPException(status_code=404, detail="Note not found")
        return {"status": "success", "linked": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


print("\n========== REGISTERED ROUTES ==========")

for route in app.routes:
    print(route.path, getattr(route, "methods", None))

print("=======================================\n")