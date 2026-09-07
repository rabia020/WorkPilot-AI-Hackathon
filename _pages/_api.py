"""
Pages API Helper
================
Shared HTTP helper for communicating with the FastAPI backend.
Every page module imports this instead of defining its own copy.
"""

import requests
from config import FASTAPI_BASE


def api_call(method: str, path: str, user: str, json_data: dict = None):
    """
    Make an API call to the FastAPI backend.

    Returns:
        (data, error) — data is the JSON response on success, error is a string on failure.
    """
    url = f"{FASTAPI_BASE}{path}"
    params = {"user": user}

    # For GET requests with json_data, treat it as extra query params
    if method == "GET" and isinstance(json_data, dict):
        params.update(json_data)

    try:
        if method == "GET":
            r = requests.get(url, params=params, timeout=10)
        elif method == "POST":
            r = requests.post(url, json=json_data, params=params, timeout=10)
        elif method == "PUT":
            r = requests.put(url, json=json_data, params=params, timeout=10)
        elif method == "DELETE":
            r = requests.delete(url, params=params, timeout=10)
        else:
            return None, "Unsupported method"

        if r.status_code == 200:
            return r.json(), None
        else:
            return None, f"Server returned status {r.status_code}: {r.text[:200]}"

    except requests.exceptions.ConnectionError:
        return None, "Cannot connect to backend. Is the FastAPI server running on port 8001?"
    except requests.exceptions.Timeout:
        return None, "Request timed out."
    except Exception as e:
        return None, str(e)


def api_get(path: str, user: str):
    """Convenience GET helper."""
    return api_call("GET", path, user)


def api_post(path: str, user: str, json_data: dict = None):
    """Convenience POST helper."""
    return api_call("POST", path, user, json_data)


def api_put(path: str, user: str, json_data: dict = None):
    """Convenience PUT helper."""
    return api_call("PUT", path, user, json_data)


def api_delete(path: str, user: str):
    """Convenience DELETE helper."""
    return api_call("DELETE", path, user)


def badge_html(priority: str) -> str:
    """Return styled badge HTML for a task priority."""
    cls = {
        "High": "wp-badge-high",
        "Medium": "wp-badge-medium",
        "Low": "wp-badge-low",
    }.get(priority, "wp-badge-medium")
    return f'<span class="wp-badge {cls}">{priority}</span>'
