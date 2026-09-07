"""
demo_data.py
============
WorkPilot AI — Demo Data Seeder

Populates the database with sample tasks and notes so the app
works without a live backend or existing data. Useful for
hackathon demos and testing.
"""

import work_manager


DEMO_TASKS = [
    {"title": "Prepare client proposal", "priority": "High", "due_date": None,
     "description": "Draft the Q3 client proposal using the latest project data and company templates."},
    {"title": "Review 8 unread emails", "priority": "Medium", "due_date": None,
     "description": "Check inbox for urgent replies from the project team."},
    {"title": "Complete project documentation", "priority": "Medium", "due_date": None,
     "description": "Finish the API docs and README for the internal tool."},
    {"title": "Follow up with HR", "priority": "Low", "due_date": None,
     "description": "Ask about the new onboarding process for next quarter."},
    {"title": "Organize GitHub repository", "priority": "Medium", "due_date": None,
     "description": "Clean up branches, update .gitignore, and tag releases."},
    {"title": "Test task edit functionality", "priority": "High", "due_date": None,
     "description": "Verify that task edit and delete work correctly in the new UI."},
    {"title": "Update dashboard styling", "priority": "Medium", "due_date": None,
     "description": "Apply the new light purple theme to the dashboard cards."},
    {"title": "Schedule team standup", "priority": "Low", "due_date": None,
     "description": "Set up a recurring daily standup meeting for the dev team."},
    {"title": "Prepare sprint review slides", "priority": "High", "due_date": None,
     "description": "Create presentation slides for Friday's sprint review."},
    {"title": "Review pull requests", "priority": "Medium", "due_date": None,
     "description": "Go through 3 pending PRs and provide feedback."},
]

DEMO_NOTES = [
    {"title": "Presentation Ideas", "content": "Focus on:\n- Full-stack architecture\n- Express API + Supabase integration\n- Team collaboration features\n- AI-powered task management"},
    {"title": "Meeting Notes - Sprint Planning", "content": "Discussed priorities for the next sprint:\n1. Complete the AI integration\n2. Fix the calendar event creation bug\n3. Add email notification support\n4. Improve dashboard performance"},
    {"title": "Bug Tracker", "content": "Known issues to investigate:\n- Missing buttons on mobile view\n- Calendar date picker not saving\n- Slow RAG queries on large documents\n- Chat input losing focus on rerun"},
    {"title": "Project Ideas", "content": "Future features to consider:\n- Voice input for task creation\n- Slack integration for notifications\n- Time tracking per task\n- AI-powered task prioritization"},
    {"title": "Quick Reminders", "content": "- Deploy to staging by Thursday\n- Send proposal to client by EOD Friday\n- Book flight for conference\n- Update LinkedIn profile"},
]


def seed_demo_data(user: str) -> dict:
    """
    Populate the database with demo tasks and notes.
    Skips if data already exists for this user.
    Returns: {"tasks_created": N, "notes_created": N}
    """
    # Check if user already has data
    existing_tasks = work_manager.get_tasks(user)
    existing_notes = work_manager.get_notes(user)

    if existing_tasks or existing_notes:
        return {"tasks_created": 0, "notes_created": 0, "skipped": True}

    from datetime import date, timedelta
    today = date.today()

    # Create tasks with staggered due dates
    tasks_created = 0
    for i, task in enumerate(DEMO_TASKS):
        # Set due dates spread across the next 7 days
        due = (today + timedelta(days=i % 7 + 1)).isoformat()
        try:
            work_manager.create_task(
                user=user,
                title=task["title"],
                description=task["description"],
                priority=task["priority"],
                due_date=due,
            )
            tasks_created += 1
        except Exception as e:
            print(f"[DemoData] Failed to create task: {e}")

    # Create notes
    notes_created = 0
    for note in DEMO_NOTES:
        try:
            work_manager.create_note(
                user=user,
                title=note["title"],
                content=note["content"],
            )
            notes_created += 1
        except Exception as e:
            print(f"[DemoData] Failed to create note: {e}")

    print(f"[DemoData] Seeded {tasks_created} tasks and {notes_created} notes for {user}")

    return {
        "tasks_created": tasks_created,
        "notes_created": notes_created,
        "skipped": False,
    }
