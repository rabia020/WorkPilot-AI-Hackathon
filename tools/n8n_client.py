import time
import requests
import uuid
import re
from datetime import datetime, timedelta

from config import N8N_ACTION_URL, N8N_AGENT_URL

# Retry configuration for n8n calls (n8n AI Agent can hit Mistral rate limits)
N8N_MAX_RETRIES = 3
N8N_BASE_DELAY = 5  # seconds


# ==========================================================
# EMAIL VALIDATION
# ==========================================================

def is_valid_email(email: str) -> bool:
    """
    Validate email address format.
    """
    if not email:
        return False
    invalid_domains = ['example.com', 'test.com', 'invalid.com', 'fake.com']
    for domain in invalid_domains:
        if domain in email.lower():
            return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


# ----------------------------
# INTERNAL POST HELPER
# ----------------------------
def _post(url: str, chat_input: str, timeout: int = 180):
    """
    Internal helper — sends a natural-language 'chatInput' to n8n.
    The AI Agent in n8n parses intent and picks the right tool.

    Retries on 429 (rate limit) and 5xx errors with exponential backoff,
    because the n8n AI Agent uses Mistral which has a tight free-tier limit.
    """
    payload = {
        "chatInput": chat_input,
        "request_id": str(uuid.uuid4()),
    }

    last_error = None
    for attempt in range(1, N8N_MAX_RETRIES + 1):
        try:
            print(f"[n8n_client] POST {url} (attempt {attempt}/{N8N_MAX_RETRIES})")
            print(f"[n8n_client] chatInput: {chat_input[:200]}")

            response = requests.post(url, json=payload, timeout=timeout)

            print(f"[n8n_client] Status Code: {response.status_code}")
            print(f"[n8n_client] Response: {response.text[:500]}")

            # Retry on rate-limit (429) or server errors (5xx)
            if response.status_code in (429, 500, 502, 503, 504) and attempt < N8N_MAX_RETRIES:
                delay = N8N_BASE_DELAY * (2 ** (attempt - 1))
                print(f"[n8n_client] Rate limit / server error, retrying in {delay}s...")
                time.sleep(delay)
                continue

            response.raise_for_status()

            try:
                return response.json()
            except Exception:
                text = response.text.strip()
                if text:
                    return {
                        "success": False,
                        "message": text,
                        "unverified": True,
                        "reason": (
                            "n8n returned a non-JSON response, so the outcome "
                            "could not be confirmed"
                        ),
                    }
                print("[n8n_client] Empty response body")
                return None

        except requests.exceptions.ConnectionError:
            print("[n8n_client] n8n not reachable (check port 5678)")
            return None
        except requests.exceptions.Timeout:
            print(f"[n8n_client] n8n request timed out (attempt {attempt}/{N8N_MAX_RETRIES})")
            last_error = "n8n request timed out"
            if attempt < N8N_MAX_RETRIES:
                time.sleep(N8N_BASE_DELAY)
                continue
        except requests.exceptions.HTTPError as e:
            print(f"[n8n_client] HTTP error {e.response.status_code}")
            if hasattr(e, 'response') and e.response:
                print(e.response.text[:300])
            last_error = f"HTTP {e.response.status_code}"
            if e.response.status_code in (429, 500, 502, 503, 504) and attempt < N8N_MAX_RETRIES:
                delay = N8N_BASE_DELAY * (2 ** (attempt - 1))
                time.sleep(delay)
                continue
        except Exception as e:
            print(f"[n8n_client] Unexpected error: {e}")
            last_error = str(e)
            if attempt < N8N_MAX_RETRIES:
                time.sleep(N8N_BASE_DELAY)
                continue

    print(f"[n8n_client] All {N8N_MAX_RETRIES} attempts failed. Last error: {last_error}")
    return None


def _extract(data, success_key="success"):
    """
    Common shape returned by the AI Agent's Respond to Webhook node:
    { "success": bool, "message": str, "raw": {...} }
    """
    if not isinstance(data, dict):
        return False, "", {}

    success = bool(data.get(success_key, False))
    message = data.get("message", "")
    raw = data.get("raw", data)

    return success, message, raw


# =========================================================
# 1. GET EMAILS
# =========================================================
def get_emails(label: str = "complaints", days: int = 30) -> list:
    """
    Get emails from Gmail via natural language request.
    """
    parts = [f"Get emails labeled '{label}'"]
    if days:
        after_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        parts.append(f"from after {after_date}")

    chat_input = " ".join(parts)

    data = _post(N8N_ACTION_URL, chat_input)

    if data is None:
        return []

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        if "emails" in data:
            return data.get("emails", [])
        if "messages" in data:
            return data.get("messages", [])
        raw = data.get("raw", {})
        if isinstance(raw, dict):
            return raw.get("messages", raw.get("emails", []))
        if isinstance(raw, list):
            return raw

    return []


# =========================================================
# 1b. GET RECENT EMAILS
# =========================================================
def get_recent_emails(query: str) -> dict:
    """
    Get recent emails using a natural language Gmail search query.
    """
    chat_input = f"Search my emails for: {query}"

    data = _post(N8N_ACTION_URL, chat_input)

    if data is None:
        return {"success": False, "message": "No response from n8n", "raw": {}}

    success, message, raw = _extract(data)

    return {
        "success": success,
        "message": message,
        "raw": raw,
    }


# =========================================================
# 2. SEND EMAIL
# =========================================================
def send_email(to: str, subject: str, body: str) -> bool:
    """
    Send email via the AI Agent, using a natural language instruction.
    """
    if not is_valid_email(to):
        print(f"[n8n_client] Invalid email: {to}")
        return False

    chat_input = (
        f"Send an email to {to} with subject '{subject}' "
        f"and message: {body}"
    )

    data = _post(N8N_ACTION_URL, chat_input)

    if data is None:
        return False

    success, message, _ = _extract(data)

    if success:
        print(f"[n8n_client] Email sent to {to}")
    else:
        print(f"[n8n_client] Failed to send to {to}: {message}")

    return success


def send_email_verbose(to: str, subject: str, body: str) -> dict:
    """
    Send email and return full response.
    """
    if not is_valid_email(to):
        return {"success": False, "message": f"Invalid email: {to}", "raw": {}}

    chat_input = (
        f"Send an email to {to} with subject '{subject}' "
        f"and message: {body}"
    )

    data = _post(N8N_ACTION_URL, chat_input)

    if data is None:
        return {"success": False, "message": "No response from n8n", "raw": {}}

    success, message, raw = _extract(data)

    return {"success": success, "message": message, "raw": raw}


# =========================================================
# 2b. SEND BATCH EMAILS (FOR BROADCAST)
# =========================================================
def send_email_batch(recipients: list, subject: str, body: str) -> dict:
    """
    Send email to multiple recipients.

    The AI Agent tool is built around a single 'send_email' action, so
    a batch is sent as one call per recipient rather than a single
    structured batch payload.
    """
    valid_recipients = [r for r in recipients if is_valid_email(r)]
    invalid_recipients = [r for r in recipients if not is_valid_email(r)]

    if invalid_recipients:
        print(f"[n8n_client] Skipping invalid emails: {invalid_recipients}")

    if not valid_recipients:
        return {
            "success": False,
            "sent": 0,
            "failed": len(recipients),
            "invalid": invalid_recipients,
        }

    sent = 0
    failed = 0
    last_message = ""

    for recipient in valid_recipients:
        chat_input = (
            f"Send an email to {recipient} with subject '{subject}' "
            f"and message: {body}"
        )
        data = _post(N8N_ACTION_URL, chat_input)

        if data is None:
            failed += 1
            continue

        success, message, _ = _extract(data)
        last_message = message

        if success:
            sent += 1
        else:
            failed += 1

    return {
        "success": failed == 0,
        "sent": sent,
        "failed": failed,
        "invalid": invalid_recipients,
        "message": last_message,
    }


# =========================================================
# 3. CREATE CALENDAR EVENT
# =========================================================
def create_calendar_event(
    title: str = None,
    date: str = None,
    duration: str = None,
    description: str = None
) -> dict:
    """
    Create calendar event via the AI Agent, using a natural language
    instruction built from whatever fields are provided.
    """
    query_parts = []
    if title:
        query_parts.append(f"Create a calendar event titled '{title}'")
    else:
        query_parts.append("Create a calendar event")
    if date:
        query_parts.append(f"scheduled for {date}")
    if duration:
        query_parts.append(f"with duration {duration}")
    if description:
        query_parts.append(f"with description: {description}")

    chat_input = " ".join(query_parts)

    data = _post(N8N_ACTION_URL, chat_input)

    if data is None:
        return {"success": False, "error": "No response from n8n", "message": "No response"}

    if isinstance(data, dict) and "success" in data:
        success, message, raw = _extract(data)
        return {"success": success, "message": message, "raw": raw}

    # n8n gave no explicit success signal, so the event is not confirmed.
    message = ""
    if isinstance(data, dict):
        message = data.get("output") or data.get("message") or ""

    return {
        "success": False,
        "message": message or "n8n did not confirm the event was created",
        "raw": data,
        "unverified": True,
        "reason": (
            "n8n response contained no explicit success flag, so calendar "
            "creation could not be confirmed"
        ),
    }


# =========================================================
# 3b. GET CALENDAR EVENTS
# =========================================================
def get_calendar_events(query: str) -> dict:
    """
    Get calendar events via a natural language request.
    """
    # If `query` already reads like a full sentence/question, pass it
    # through as-is; otherwise wrap it into a clear instruction.
    if query and query.strip().lower().startswith(
        ("give me", "get", "show", "what", "list", "find")
    ):
        chat_input = query
    else:
        chat_input = f"Get my calendar events for {query}"

    data = _post(N8N_ACTION_URL, chat_input)

    if data is None:
        return {"success": False, "message": "No response from n8n", "raw": {}}

    success, message, raw = _extract(data)

    return {
        "success": success,
        "message": message,
        "raw": raw,
    }


# =========================================================
# 3c. GET CALENDAR EVENTS BY DATE
# =========================================================
def get_calendar_events_by_date(date_str: str, event_title: str = None) -> dict:
    """
    Get calendar events for a specific date via natural language.
    """
    actual_date = _parse_date_string(date_str)
    target = actual_date or date_str

    chat_input = f"Get my calendar events on {target}"
    if event_title:
        chat_input += f" for an event titled '{event_title}'"

    data = _post(N8N_ACTION_URL, chat_input)

    if data is None:
        return {"success": False, "message": "No response from n8n", "raw": {}}

    success, message, raw = _extract(data)

    return {
        "success": success,
        "message": message,
        "raw": raw,
        "date": target,
    }


def _parse_date_string(date_str: str) -> str:
    """
    Parse natural language date to YYYY-MM-DD.
    """
    if not date_str:
        return None

    date_str = date_str.lower().strip()

    day_map = {
        "sunday": 6,
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
    }

    today = datetime.now()

    if date_str in ["today", "todays"]:
        return today.strftime("%Y-%m-%d")

    if date_str in ["tomorrow", "tomorrows"]:
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")

    if date_str in ["yesterday"]:
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")

    for day_name, day_num in day_map.items():
        if day_name in date_str:
            days_ahead = day_num - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            target_date = today + timedelta(days=days_ahead)
            return target_date.strftime("%Y-%m-%d")

    match = re.search(r'(\d{4})-(\d{2})-(\d{2})', date_str)
    if match:
        return match.group(0)

    match = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', date_str)
    if match:
        return f"{match.group(3)}-{match.group(1).zfill(2)}-{match.group(2).zfill(2)}"

    return None


# =========================================================
# 4. SEND SLACK MESSAGE
# =========================================================
def send_slack_message(channel: str, message: str) -> bool:
    """
    Send Slack message via the AI Agent, using natural language.
    """
    if not channel.startswith('#'):
        channel = f"#{channel}"

    chat_input = f"Send a Slack message to {channel} saying: {message}"

    data = _post(N8N_ACTION_URL, chat_input)

    if data is None:
        return False

    success, _, _ = _extract(data)

    if success:
        print(f"[n8n_client] Slack message sent to {channel}")
    else:
        print(f"[n8n_client] Failed to send Slack message")

    return success


def send_slack_message_verbose(channel: str, message: str) -> dict:
    """
    Send Slack message and return full response.
    """
    if not channel.startswith('#'):
        channel = f"#{channel}"

    chat_input = f"Send a Slack message to {channel} saying: {message}"

    data = _post(N8N_ACTION_URL, chat_input)

    if data is None:
        return {"success": False, "message": "No response from n8n", "raw": {}}

    success, msg, raw = _extract(data)

    return {"success": success, "message": msg, "raw": raw}


# =========================================================
# 5. CREATE JIRA TICKET
# =========================================================
def create_jira_ticket(summary: str, description: str, priority: str = "Medium") -> dict:
    """
    Create Jira ticket via the AI Agent, using natural language.
    """
    chat_input = (
        f"Create a Jira task titled '{summary}' with description "
        f"'{description}' and priority {priority}"
    )

    data = _post(N8N_ACTION_URL, chat_input)

    if data is None:
        return {"success": False, "error": "No response from n8n"}

    success, message, raw = _extract(data)

    return {
        "success": success,
        "message": message,
        "raw": raw,
    }


# =========================================================
# 5b. GET JIRA ISSUES
# =========================================================
def get_jira_issues(project: str = "KAN", status: str = None, assignee: str = None, max_results: int = 5) -> dict:
    """
    Get Jira issues via natural language.
    """
    parts = [f"Get up to {max_results} Jira issues from project {project}"]
    if status:
        parts.append(f"with status {status}")
    if assignee:
        parts.append(f"assigned to {assignee}")

    chat_input = " ".join(parts)

    data = _post(N8N_ACTION_URL, chat_input)

    if data is None:
        return {"success": False, "message": "No response from n8n", "issues": []}

    success, message, raw = _extract(data)

    return {
        "success": success,
        "message": message,
        "raw": raw,
        "issues": raw.get("issues", []) if isinstance(raw, dict) else [],
    }


# =========================================================
# 5c. UPDATE JIRA ISSUE
# =========================================================
def update_jira_issue(issue_key: str, summary: str = None, description: str = None, status: str = None, priority: str = None) -> dict:
    """
    Update a Jira issue via natural language.
    """
    parts = [f"Update Jira issue {issue_key}"]
    if summary:
        parts.append(f"with new summary '{summary}'")
    if description:
        parts.append(f"with new description '{description}'")
    if status:
        parts.append(f"set status to {status}")
    if priority:
        parts.append(f"set priority to {priority}")

    chat_input = " ".join(parts)

    data = _post(N8N_ACTION_URL, chat_input)

    if data is None:
        return {"success": False, "error": "No response from n8n"}

    success, message, raw = _extract(data)

    return {
        "success": success,
        "message": message,
        "raw": raw,
    }


# =========================================================
# 6. RAG QUERY (USES AI AGENT - KEEP THIS)
# =========================================================
def send_rag_query(query: str):
    """
    RAG queries go through the AI Agent workflow.
    """
    data = _post(N8N_AGENT_URL, query)

    if data is None:
        return {"status": "failed", "error": "No response from n8n"}

    return data


# =========================================================
# 7. CONNECTION TEST
# =========================================================
def test_connection() -> bool:
    """
    Test connection to n8n.
    """
    try:
        response = requests.get(
            "http://localhost:5678/healthz",
            timeout=5
        )

        ok = response.status_code == 200
        status_label = "✅ OK" if ok else "❌ FAIL"
        print(f"[n8n_client] n8n health check: {status_label}")

        return ok

    except Exception:
        print("[n8n_client] n8n not reachable")
        return False


# =========================================================
# MANUAL TEST BLOCK
# =========================================================
if __name__ == "__main__":

    print("=" * 60)
    print("Testing n8n Direct Actions Client (Option A - chatInput only)")
    print("=" * 60)

    print("\n1. Testing connection...")
    test_connection()

    print("\n2. Testing email validation...")
    print(f"   test@gmail.com: {is_valid_email('test@gmail.com')}")
    print(f"   test@example.com: {is_valid_email('test@example.com')}")

    print("\n3. Testing date parsing...")
    print(f"   'friday': {_parse_date_string('friday')}")
    print(f"   'today': {_parse_date_string('today')}")

    print("\n4. Testing Slack...")
    print(send_slack_message_verbose("#general", "Hello from system test"))

    print("\n5. Testing Calendar Events By Date...")
    print(get_calendar_events_by_date("today"))

    print("\n6. Testing Jira Create...")
    print(create_jira_ticket("Test Task from Python", "This is a test task"))

    print("\n7. Testing Email (verbose)...")
    print(send_email_verbose("test@gmail.com", "Hello", "Test email"))