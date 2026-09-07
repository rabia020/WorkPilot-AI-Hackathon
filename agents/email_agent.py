# agents/email_agent.py

import json
import os
import re
from datetime import datetime, timedelta

from dotenv import load_dotenv
from langchain_groq import ChatGroq

from tools.n8n_client import (
    get_emails,
    get_recent_emails,
    send_email,
    get_calendar_events,
    get_calendar_events_by_date,
)
from agents.reporter import generate_report
from auth import get_all_users, get_user


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
    temperature=0
)


# ==========================================================
# HELPER — SENDER IDENTITY
# ==========================================================

def _get_sender_identity(username: str) -> dict:

    try:

        user = get_user(username)

        if user:

            return {

                "name": (

                    user.get("full_name")

                    or user.get("username", "Team")

                ),

                "role": (

                    (user.get("role") or "").capitalize()

                    or "Team Member"

                )

            }

    except Exception as e:

        print(
            f"[Email Agent] Sender lookup failed: {e}"
        )

    return {

        "name": "Team",

        "role": "Team Member"

    }


# ==========================================================
# HELPER — EMAIL VALIDATION
# ==========================================================

def is_valid_email(email: str) -> bool:
    """Validate email address format."""
    if not email:
        return False
    # Skip example.com emails as they're invalid
    if "example.com" in email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


# ==========================================================
# HELPER — EXTRACT EVENT DETAILS FROM QUERY
# ==========================================================

def _extract_event_details_from_query(query: str) -> dict:
    """
    Extract date and event name from user query.
    Returns: {"date": "sunday", "event_name": "weekly report sharing", "time": "9pm to 10pm"}
    """
    prompt = f"""
Extract the event details from this query:
"{query}"

Return ONLY valid JSON:
{{
    "date": "the day/date mentioned (e.g., 'sunday', 'tomorrow', '2026-08-09')",
    "event_name": "the event name or purpose mentioned",
    "time": "the time mentioned if any (e.g., '9pm to 10pm')"
}}

If a detail is not mentioned, use an empty string.
"""

    try:
        response = llm.invoke(prompt)
        content = response.content.strip()
        if content.startswith("```"):
            content = content.replace("```json", "").replace("```", "").strip()
        return json.loads(content)
    except Exception as e:
        print(f"[Email Agent] Event extraction error: {e}")
        return {"date": "", "event_name": "", "time": ""}


# ==========================================================
# HELPER — PARSE EVENTS FROM N8N MESSAGE 
# ==========================================================

def _parse_events_from_message(message: str) -> list:
    """
    Parse events from the n8n response message with improved patterns.
    """
    events = []
    
    if not message:
        return events
    
    # Try multiple patterns to extract event details
    
    # Pattern 1: Events with bullet points and bold text
    # Example: "- **Time:** 9:00 PM – 10:00 PM (PKT)\n- **Event:** Weekly Report Sharing"
    event_patterns = re.findall(
        r'(?:[-*]?\s*\*\*Time:\*\*\s*([^\n]+)\s*[-*]?\s*\*\*Event:\*\*\s*([^\n]+))',
        message,
        re.IGNORECASE
    )
    
    for match in event_patterns:
        events.append({
            "title": match[1].strip(),
            "start_time": match[0].strip(),
            "end_time": "",
            "date": ""
        })
    
    # Pattern 2: Events in the format from your logs
    # Example: "Weekly Report Sharing - Time: 9:00 PM – 10:00 PM (PKT)"
    if not events:
        pattern2 = r'([^\n]+?)\s*[-–]\s*Time:\s*([^\n]+?)(?:\s*[-–]\s*Description:\s*([^\n]+))?'
        matches = re.findall(pattern2, message, re.IGNORECASE)
        
        for match in matches:
            title = match[0].strip()
            time = match[1].strip()
            desc = match[2].strip() if len(match) > 2 and match[2] else ""
            
            events.append({
                "title": title,
                "start_time": time,
                "end_time": "",
                "description": desc,
                "date": ""
            })
    
    # Pattern 3: Events with time and title on separate lines
    if not events:
        lines = message.split('\n')
        current_event = {}
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Look for time patterns
            time_match = re.search(r'Time:\s*([^,]+)', line, re.IGNORECASE)
            if time_match:
                current_event['start_time'] = time_match.group(1).strip()
            
            # Look for event title
            event_match = re.search(r'Event:\s*(.+?)(?:\s*[-–]|\s*$)', line, re.IGNORECASE)
            if event_match:
                current_event['title'] = event_match.group(1).strip()
            
            # Look for description
            desc_match = re.search(r'Description:\s*(.+?)(?:\s*[-–]|\s*$)', line, re.IGNORECASE)
            if desc_match:
                current_event['description'] = desc_match.group(1).strip()
            
            # If we have both title and time, save the event
            if 'title' in current_event and 'start_time' in current_event:
                events.append(current_event.copy())
                current_event = {}
    
    # Pattern 4: Raw event details in the message
    if not events:
        # Look for the event title in the message
        title_match = re.search(r'\*\*([^*]+)\*\*', message)
        if title_match:
            title = title_match.group(1).strip()
            
            # Look for time
            time_match = re.search(r'(\d{1,2}:\d{2}\s*[AP]M\s*[-–]\s*\d{1,2}:\d{2}\s*[AP]M)', message, re.IGNORECASE)
            if not time_match:
                time_match = re.search(r'(\d{1,2}:\d{2}\s*[AP]M)', message, re.IGNORECASE)
            
            event = {"title": title}
            if time_match:
                event['start_time'] = time_match.group(1).strip()
            
            events.append(event)
    
    return events


# ==========================================================
# HELPER — EVENT DETAILS FOR EMAIL
# ==========================================================

def _format_event_details_for_email(events: list) -> str:
    """
    Format event details for inclusion in email body.
    """
    if not events:
        return ""
    
    details = "\n\n---\n\n**📅 EVENT DETAILS:**\n\n"
    
    for i, event in enumerate(events, 1):
        title = event.get('title', 'Untitled Event')
        details += f"**Event: {title}**\n"
        
        if event.get('date'):
            details += f"• Date: {event['date']}\n"
        
        if event.get('start_time'):
            details += f"• Time: {event['start_time']}"
            if event.get('end_time') and event['end_time'] != event['start_time']:
                details += f" - {event['end_time']}"
            details += "\n"
        
        if event.get('description'):
            details += f"• Description: {event['description']}\n"
        
        details += "\n"
    
    details += "Please mark your calendars and plan accordingly.\n"
    details += "\n---\n"
    
    return details


# ==========================================================
# HELPER — FORMAT EVENT DETAILS FOR SLACK
# ==========================================================

def _format_event_details_for_slack(events: list) -> str:
    """
    Format event details for Slack message.
    """
    if not events:
        return ""
    
    details = "\n\n*📅 EVENT DETAILS:*\n"
    
    for event in events:
        title = event.get('title', 'Untitled Event')
        details += f"• *{title}*\n"
        
        if event.get('date'):
            details += f"  • Date: {event['date']}\n"
        
        if event.get('start_time'):
            details += f"  • Time: {event['start_time']}"
            if event.get('end_time') and event['end_time'] != event['start_time']:
                details += f" - {event['end_time']}"
            details += "\n"
        
        if event.get('description'):
            details += f"  • Description: {event['description']}\n"
    
    return details


# ==========================================================
# HELPER — FETCH CALENDAR CONTEXT 
# ==========================================================

def _fetch_calendar_context(query: str, format_type: str = "email") -> str:
    """
    Fetch calendar event details for the query.
    format_type: "email" or "slack"
    """
    # First, extract event details from the query
    event_details = _extract_event_details_from_query(query)
    
    date_str = event_details.get("date", "")
    event_name = event_details.get("event_name", "")
    event_time = event_details.get("time", "")
    
    # If no date found, try to find any date reference
    if not date_str:
        # Look for day names in the query
        days = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "today", "tomorrow"]
        for day in days:
            if day in query.lower():
                date_str = day
                break
    
    # If we have a date, try to fetch events
    if date_str:
        try:
            print(f"[Email Agent] Fetching calendar events for: {date_str}")
            
            # First try with the specific date
            result = get_calendar_events_by_date(date_str, event_name if event_name else None)
            
            if result.get("success") and result.get("message"):
                message = result["message"]
                
                # Parse events from the message
                events = _parse_events_from_message(message)
                
                if events:
                    # Format events based on the target format
                    if format_type == "slack":
                        return _format_event_details_for_slack(events)
                    else:
                        return _format_event_details_for_email(events)
                
                # If we couldn't parse events but have a message with event info
                if "No events" not in message and "not found" not in message.lower():
                    # Try to extract event info directly from the message
                    return _extract_event_info_from_message(message, format_type)
            
        except Exception as e:
            print(f"[Email Agent] Calendar fetch error: {e}")
    
    # If we have event name but no date, try to find it in upcoming events
    if event_name and not date_str:
        try:
            print(f"[Email Agent] Searching for event: {event_name}")
            result = get_calendar_events(f"events about {event_name}")
            
            if result.get("success") and result.get("message"):
                message = result["message"]
                events = _parse_events_from_message(message)
                
                if events:
                    if format_type == "slack":
                        return _format_event_details_for_slack(events)
                    else:
                        return _format_event_details_for_email(events)
        except Exception as e:
            print(f"[Email Agent] Event search error: {e}")
    
    return ""


def _extract_event_info_from_message(message: str, format_type: str = "email") -> str:
    """
    Extract event information from a message and format it.
    """
    # Look for event details in the message
    event_info = ""
    
    # Try to find the event title
    title_match = re.search(r'\*\*([^*]+)\*\*', message)
    if title_match:
        event_info += f"Event: {title_match.group(1)}\n"
    
    # Try to find time
    time_match = re.search(r'(\d{1,2}:\d{2}\s*[AP]M)', message, re.IGNORECASE)
    if time_match:
        event_info += f"Time: {time_match.group(1)}\n"
    
    # Try to find date
    date_match = re.search(r'(\w+day|\d{1,2}/\d{1,2}/\d{4})', message)
    if date_match:
        event_info += f"Date: {date_match.group(1)}\n"
    
    if event_info:
        if format_type == "slack":
            return f"\n📅 *Event Details:*\n{event_info}"
        else:
            return f"\n\n📅 Event Details:\n{event_info}\n"
    
    return message


# ==========================================================
# EMAIL AGENT
# ==========================================================

def email_agent(state: dict) -> dict:

    print(
        f"[TRACE] email_agent received keys = {sorted(state.keys())}"
    )

    print(
        f"[TRACE] email_agent: 'query_type' in state = "
        f"{'query_type' in state} | raw value = "
        f"{state.get('query_type', '<<MISSING>>')!r}"
    )

    query_type = state.get(
        "query_type",
        "email"
    )

    print(
        f"[Email Agent] Processing query type: {query_type}"
    )


    # ======================================================
    # WORKFLOW 1 — NORMAL EMAIL REQUEST
    # ======================================================

    if query_type == "email":

        return prepare_new_email(
            state
        )


    # ======================================================
    # WORKFLOW 2 — COMPLAINT EMAIL ANALYSIS
    # ======================================================

    if query_type == "complaint":

        return analyze_complaint_emails(
            state
        )


    # ======================================================
    # WORKFLOW 3 — READ-ONLY INBOX LISTING
    # ======================================================

    if query_type == "email_read":

        return list_recent_emails(
            state
        )


    # ======================================================
    # WORKFLOW 4 — BROADCAST TO ALL EMPLOYEES
    # ======================================================

    if query_type == "email_broadcast":

        return prepare_broadcast_email(
            state
        )


    # ======================================================
    # FALLBACK
    # ======================================================

    print(
        "[Email Agent] Unknown email workflow."
    )


    return {

        "emails": [],

        "messages": [

            "[Email Agent] No supported email workflow."

        ]

    }


# ==========================================================
# WORKFLOW 1
# PREPARE NEW EMAIL
# ==========================================================

def prepare_new_email(
    state: dict
) -> dict:

    query = state.get(
        "query",
        ""
    )


    print(
        "[Email Agent] Preparing new email draft..."
    )

    sender = _get_sender_identity(

        state.get("user", "default")

    )

    calendar_context = _fetch_calendar_context(query, "email")

    calendar_section = (

        f"\nCALENDAR CONTEXT (real event data — use this to fill "
        f"in any event details the user refers to):\n"
        f"{calendar_context}\n"

        if calendar_context

        else ""

    )


    prompt = f"""
You are an email drafting assistant.

The user wants to send an email.

Extract the recipient and create a professional email draft.

USER REQUEST:
{query}

SENDER NAME:
{sender['name']}

SENDER ROLE:
{sender['role']}
{calendar_section}

IMPORTANT RULES:

1. Extract the recipient email address from the request.

2. Create an appropriate subject.

3. Write a professional email body.

4. Use ONLY information provided in the user request and, if
   present above, the CALENDAR CONTEXT — do not invent details
   beyond those two sources.

5. Do NOT invent:
   - deadlines
   - links
   - exam portals
   - contact email addresses
   - phone numbers
   - policies
   - fees
   - passing scores
   - organization details

6. If a detail is not provided and not in CALENDAR CONTEXT,
   do not add it.

7. Sign the email using SENDER NAME and SENDER ROLE above,
   exactly as given. Do NOT use placeholder text like
   "[Your Name]" or "[Your Position]".

8. Output ONLY valid JSON.

OUTPUT FORMAT:

{{
    "to": "recipient email",
    "subject": "email subject",
    "body": "complete email body"
}}
"""


    try:

        response = llm.invoke(
            prompt
        )


        content = response.content.strip()


        if content.startswith(
            "```"
        ):

            content = (

                content
                .replace(
                    "```json",
                    ""
                )
                .replace(
                    "```",
                    ""
                )
                .strip()

            )


        email_data = json.loads(
            content
        )


        recipient = email_data.get(
            "to",
            ""
        )

        subject = email_data.get(
            "subject",
            ""
        )

        body = email_data.get(
            "body",
            ""
        )


        if not recipient:

            raise ValueError(
                "No recipient email found."
            )


        print(
            f"[Email Agent] Draft prepared for {recipient}"
        )

        proposed_actions = [

            {

                "tool": "SendEmail_Tool",

                "args": {

                    "to": recipient,

                    "subject": subject,

                    "message": body

                }

            }

        ]

        emails = [

            {

                "to": recipient,

                "subject": subject,

                "body": body,

                "email_type": "new_email"

            }

        ]

        report_text = generate_report(

            query=query,

            query_type="email",

            emails=emails

        )

        return {

            "emails": emails,

            "proposed_actions": proposed_actions,

            "report": report_text,

            "messages": [

                (

                    "[Email Agent] "
                    f"Email draft prepared for {recipient}"

                )

            ]

        }


    except Exception as e:

        print(
            f"[Email Agent] Draft generation error: {e}"
        )

        report_text = (

            "# Email Draft Failed\n\n"

            f"I couldn't prepare this email: {e}\n\n"

            "This usually means no single literal email address "

            "was found in the request. If you're trying to email "

            "a group (e.g. \"all employees\"), that's not "

            "supported yet — see the note below."

        )

        return {

            "emails": [],

            "proposed_actions": [],

            "report": report_text,

            "error": str(e),

            "messages": [

                (

                    "[Email Agent] "
                    "Failed to prepare email draft."

                )

            ]

        }


# ==========================================================
# WORKFLOW 2
# FETCH AND ANALYZE COMPLAINT EMAILS
# ==========================================================

def analyze_complaint_emails(
    state: dict
) -> dict:

    print(
        "[Email Agent] Fetching complaint emails from n8n..."
    )


    raw_emails = get_emails(

        label="complaints",

        days=30

    )


    if not raw_emails:

        print(
            "[Email Agent] No complaint emails returned."
        )


        return {

            "emails": [],

            "proposed_actions": [],

            "messages": [

                "[Email Agent] No complaint emails found."

            ]

        }


    print(
        f"[Email Agent] Got "
        f"{len(raw_emails)} complaint emails"
    )


    structured = []


    for email in raw_emails[:10]:

        try:

            response = llm.invoke(

                f"""
Analyze this customer complaint email.

Return ONLY valid JSON:

{{
    "sender": "email address",
    "subject": "original subject line",
    "summary": "one sentence summary",
    "category": "billing|shipping|product|support|other",
    "sentiment": "negative|neutral|positive",
    "severity": "low|medium|high"
}}

Subject:
{email.get('subject', '')}

Body:
{email.get('body', '')[:600]}

JSON only.
"""

            )


            content = (

                response.content
                .strip()
                .replace(
                    "```json",
                    ""
                )
                .replace(
                    "```",
                    ""
                )

            )


            parsed = json.loads(
                content
            )


            parsed["original_body"] = (

                email.get(
                    "body",
                    ""
                )[:600]

            )


            structured.append(
                parsed
            )


        except Exception as e:

            print(
                f"[Email Agent] "
                f"Parse error: {e}"
            )


            structured.append(

                {

                    "sender": email.get(
                        "sender",
                        "unknown"
                    ),

                    "subject": email.get(
                        "subject",
                        "Complaint"
                    ),

                    "summary": email.get(
                        "subject",
                        "Complaint"
                    ),

                    "category": "other",

                    "sentiment": "negative",

                    "severity": "medium",

                    "original_body": email.get(
                        "body",
                        ""
                    )[:600]

                }

            )


    log = "\n".join(

        [

            (

                f"- {e.get('sender')}: "
                f"{e.get('summary')} "
                f"[{e.get('severity', '').upper()}]"

            )

            for e in structured

        ]

    )

    query = state.get("query", "")

    report_text = generate_report(

        query=query,

        query_type="complaint",

        emails=structured

    )

    return {

        "emails": structured,

        "proposed_actions": [

            {

                "tool": "SendComplaintReplies",

                "args": {

                    "count": len(structured)

                }

            }

        ],

        "report": report_text,

        "messages": [

            (

                f"[Email Agent] "
                f"{len(structured)} complaint emails analyzed:\n"
                f"{log}"

            )

        ]

    }


# ==========================================================
# WORKFLOW 3
# LIST RECENT INBOX EMAILS 
# ==========================================================

def list_recent_emails(
    state: dict
) -> dict:

    query = state.get(
        "query",
        ""
    )

    print(
        "[Email Agent] Fetching recent inbox emails..."
    )

    try:

        result = get_recent_emails(query)

        message = result.get("message", "")

        if not message:

            message = "No emails were found for this request."

    except Exception as e:

        print(
            f"[Email Agent] Error fetching inbox emails: {e}"
        )

        message = (
            "Sorry, I couldn't retrieve inbox emails right now — "
            "the email service may be unavailable."
        )

    report_text = f"# Recent Emails\n\n{message}"

    print(
        f"[Email Agent] Done — {len(report_text)} chars"
    )

    return {

        "report": report_text,

        "proposed_actions": [],

        "emails": [],

        "messages": [

            "[Email Agent] Recent inbox emails fetched"

        ]

    }


# ==========================================================
# HELPER — ACTIVE RECIPIENT EMAILS FROM THE USERS TABLE
# ==========================================================

def get_active_recipient_emails(
    include_managers: bool = True,
    include_employees: bool = True
) -> list:
    """
    Reads directly from the same `users` table auth.py's
    Manage Users screen displays. Only ACTIVE users with a
    real email address are included — deactivated accounts
    are skipped on purpose.
    """

    users = get_all_users()

    # get_all_users() column order:
    # id, full_name, username, email, role, active,
    # created_at, last_login, created_by

    recipients = []

    for row in users:

        full_name = row[1]
        username = row[2]
        email = row[3]
        role = row[4]
        active = row[5]

        if not active:
            continue

        if not email or not is_valid_email(email):
            print(f"[Email Agent] Skipping invalid email: {email}")
            continue

        if role == "employee" and not include_employees:
            continue

        if role == "manager" and not include_managers:
            continue

        recipients.append(

            {

                "name": full_name or username,

                "email": email

            }

        )

    return recipients


# ==========================================================
# WORKFLOW 4
# PREPARE BROADCAST EMAIL (all active employees)
# ==========================================================

def prepare_broadcast_email(
    state: dict
) -> dict:

    query = state.get(
        "query",
        ""
    )

    print(
        "[Email Agent] Preparing broadcast email to all employees..."
    )

    # Fetch calendar context for the broadcast
    calendar_context = _fetch_calendar_context(query, "email")

    calendar_section = (

        f"\nCALENDAR CONTEXT (real event data — use this to fill "
        f"in any event details the user refers to):\n"
        f"{calendar_context}\n"

        if calendar_context

        else ""

    )

    try:

        recipients = get_active_recipient_emails()

    except Exception as e:

        print(
            f"[Email Agent] Failed to load recipient list: {e}"
        )

        return {

            "emails": [],

            "proposed_actions": [],

            "report": (
                "# Broadcast Email Failed\n\n"
                f"Couldn't load the employee list: {e}"
            ),

            "error": str(e),

            "messages": [
                "[Email Agent] Failed to load recipient list."
            ]

        }

    if not recipients:

        return {

            "emails": [],

            "proposed_actions": [],

            "report": (
                "# Broadcast Email\n\n"
                "No active users were found to notify."
            ),

            "messages": [
                "[Email Agent] No active recipients found."
            ]

        }

    sender = _get_sender_identity(

        state.get("user", "default")

    )

    prompt = f"""
You are an email drafting assistant.

The user wants to send an email to ALL active employees/users
of the company. You do NOT need to determine the recipient —
that has already been resolved separately. Your only job is
the subject and body.

USER REQUEST:
{query}

SENDER NAME:
{sender['name']}

SENDER ROLE:
{sender['role']}
{calendar_section}

RULES:

1. Create an appropriate subject that mentions the event details.
2. Write a professional email body that includes the event details
   from the CALENDAR CONTEXT above.
3. Use ONLY information provided in the user request and, if
   present above, the CALENDAR CONTEXT.
4. Do NOT invent deadlines, links, policies, or any detail
   not present in those two sources.
5. Sign the email using SENDER NAME and SENDER ROLE above,
   exactly as given.
6. Output ONLY valid JSON.

OUTPUT FORMAT:

{{
    "subject": "email subject",
    "body": "complete email body"
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

        draft = json.loads(content)

        subject = draft.get("subject", "Company Notification")

        body = draft.get("body", query)

    except Exception as e:

        print(
            f"[Email Agent] Broadcast draft generation error: {e}"
        )

        subject = "Company Notification"

        body = query

    # Filter out invalid emails
    valid_recipients = [r for r in recipients if is_valid_email(r["email"])]
    
    if not valid_recipients:
        return {
            "emails": [],
            "proposed_actions": [],
            "report": "# Broadcast Email Failed\n\nNo valid email addresses found.",
            "messages": ["[Email Agent] No valid recipients found."]
        }

    emails_list = [

        {

            "to": r["email"],

            "subject": subject,

            "body": body,

            "email_type": "broadcast"

        }

        for r in valid_recipients

    ]

    proposed_actions = [

        {

            "tool": "BroadcastEmail_Tool",

            "args": {

                "recipient_count": len(valid_recipients),

                "recipients": [r["email"] for r in valid_recipients],

                "subject": subject,

                "message": body

            }

        }

    ]

    report_text = generate_report(

        query=query,

        query_type="email_broadcast",

        emails=emails_list,

        proposed_actions=proposed_actions

    )

    print(
        f"[Email Agent] Broadcast draft prepared for "
        f"{len(valid_recipients)} recipients"
    )

    return {

        "emails": emails_list,

        "proposed_actions": proposed_actions,

        "report": report_text,

        "messages": [

            (

                "[Email Agent] "
                f"Broadcast draft prepared for {len(valid_recipients)} recipients"

            )

        ]

    }


# ==========================================================
# SEND NEW EMAIL AFTER APPROVAL
# ==========================================================

def send_new_email(
    state: dict
) -> dict:

    emails = state.get(
        "emails",
        []
    )


    if not emails:

        print(
            "[Email Agent] No email draft found."
        )


        return state


    if state.get(
        "approved"
    ) is not True:

        print(
            "[Email Agent] "
            "Email not approved. Skipping send."
        )


        return state


    sent = 0

    failed = 0


    for email in emails:

        if email.get(
            "email_type"
        ) != "new_email":

            continue


        recipient = email.get(
            "to",
            ""
        )

        subject = email.get(
            "subject",
            ""
        )

        body = email.get(
            "body",
            ""
        )


        if not recipient:

            print(
                "[Email Agent] "
                "Missing recipient."
            )


            failed += 1

            continue

        # Validate email before sending
        if not is_valid_email(recipient):
            print(
                f"[Email Agent] Invalid email address: {recipient}"
            )
            failed += 1
            continue


        success = send_email(

            to=recipient,

            subject=subject,

            body=body

        )


        if success:

            print(
                f"[Email Agent] "
                f"Email sent to {recipient}"
            )

            sent += 1


        else:

            print(
                f"[Email Agent] "
                f"Failed to send email to {recipient}"
            )

            failed += 1


    return {

        **state,

        "email_send_result": {
            "kind": "new_email",
            "sent": sent,
            "failed": failed,
            "attempted": sent + failed,
            "success": sent > 0 and failed == 0,
        },

        "messages": (

            state.get(
                "messages",
                []
            )

            + [

                (

                    "[Email Agent] "
                    f"New emails: {sent} sent, "
                    f"{failed} failed"

                )

            ]

        )

    }


# ==========================================================
# SEND BROADCAST EMAILS AFTER APPROVAL
# ==========================================================

def send_broadcast_emails(
    state: dict
) -> dict:

    emails = state.get(
        "emails",
        []
    )

    if not emails:

        print(
            "[Email Agent] No broadcast draft found."
        )

        return state

    if state.get(
        "approved"
    ) is not True:

        print(
            "[Email Agent] "
            "Broadcast not approved. Skipping send."
        )

        return state

    sent = 0

    failed = 0

    for email in emails:

        if email.get(
            "email_type"
        ) != "broadcast":

            continue

        recipient = email.get(
            "to",
            ""
        )

        if not recipient or not is_valid_email(recipient):
            print(
                f"[Email Agent] Invalid or missing email: {recipient}"
            )
            failed += 1
            continue

        success = send_email(

            to=recipient,

            subject=email.get("subject", ""),

            body=email.get("body", "")

        )

        if success:

            sent += 1

        else:

            failed += 1

    print(

        f"[Email Agent] "
        f"Broadcast: {sent} sent, {failed} failed"

    )

    return {

        **state,

        "email_send_result": {
            "kind": "broadcast",
            "sent": sent,
            "failed": failed,
            "attempted": sent + failed,
            "success": sent > 0 and failed == 0,
        },

        "messages": (

            state.get(
                "messages",
                []
            )

            + [

                (

                    "[Email Agent] "
                    f"Broadcast: {sent} sent, "
                    f"{failed} failed"

                )

            ]

        )

    }


# ==========================================================
# SEND COMPLAINT REPLIES AFTER APPROVAL
# ==========================================================

def send_email_replies(
    state: dict
) -> dict:

    emails = state.get(
        "emails",
        []
    )


    if not emails:

        print(
            "[Email Agent] "
            "No complaint emails to reply to."
        )


        return state


    if state.get(
        "approved"
    ) is not True:

        print(
            "[Email Agent] "
            "Not approved — skipping replies."
        )


        return state


    print(
        f"[Email Agent] "
        f"Sending replies to {len(emails)} emails..."
    )


    sent = 0

    failed = 0


    for email in emails:

        if email.get(
            "email_type"
        ) == "new_email":

            continue


        sender = email.get(
            "sender",
            ""
        )


        subject = email.get(
            "subject",
            "Your complaint"
        )


        if not sender or not is_valid_email(sender):
            print(
                f"[Email Agent] Invalid sender email: {sender}"
            )
            failed += 1
            continue


        try:

            response = llm.invoke(

                f"""
You are a professional customer support agent.

Write a polite and helpful reply to this customer complaint.

Be empathetic, acknowledge the issue,
and provide next steps.

Keep the reply under 150 words.

Customer email:

Subject:
{subject}

Body:
{email.get(
    'original_body',
    email.get(
        'summary',
        ''
    )
)}

Write ONLY the email body.
"""

            )


            reply_body = response.content.strip()


        except Exception as e:

            print(
                f"[Email Agent] "
                f"Reply generation error: {e}"
            )


            reply_body = (

                "Thank you for contacting us. "
                "We have received your complaint "
                "and our team will review it."

            )


        success = send_email(

            to=sender,

            subject=f"Re: {subject}",

            body=reply_body

        )


        if success:

            sent += 1

            print(
                f"[Email Agent] "
                f"Reply sent to {sender}"
            )


        else:

            failed += 1

            print(
                f"[Email Agent] "
                f"Reply failed for {sender}"
            )


    return {

        **state,

        "email_send_result": {
            "kind": "complaint_replies",
            "sent": sent,
            "failed": failed,
            "attempted": sent + failed,
            "success": sent > 0 and failed == 0,
        },

        "messages": (

            state.get(
                "messages",
                []
            )

            + [

                (

                    "[Email Agent] "
                    f"Replies: {sent} sent, "
                    f"{failed} failed"

                )

            ]

        )

    }
