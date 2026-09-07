"""
pages/calendar_page.py
=======================
WorkPilot AI — Calendar View
"""

import calendar
import requests
import streamlit as st
from datetime import date, datetime, timedelta

from config import FASTAPI_BASE
from _pages._api import api_call
from tools.n8n_client import get_calendar_events as _n8n_get_calendar_events


def _fetch_calendar_events_for_month(year: int, month: int) -> list:
    """
    Fetch calendar events for a given month.
    Tries the backend /calendar-events endpoint first;
    falls back to calling n8n directly if the endpoint is unavailable.
    """
    # 1. Try backend endpoint
    cal_data, err = api_call("GET", "/calendar-events", "default", {"month": month, "year": year})
    if cal_data and cal_data.get("events"):
        return cal_data["events"]

    # 2. Fallback: call n8n directly (same pattern as Jira Issues tab)
    try:
        month_name = date(year, month, 1).strftime("%B")
        result = _n8n_get_calendar_events(f"events in {month_name} {year}")
        raw = result.get("raw", {})
        events = []
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict):
                    events.append(_normalize_event(item))
        elif isinstance(raw, dict):
            inner = raw.get("events", raw.get("items", []))
            if isinstance(inner, list):
                for item in inner:
                    if isinstance(item, dict):
                        events.append(_normalize_event(item))
            elif raw.get("title") or raw.get("summary"):
                events.append(_normalize_event(raw))
        return events
    except Exception as e:
        print(f"[Calendar] n8n fallback error: {e}")
        return []


def _normalize_event(item: dict) -> dict:
    """Normalize a raw n8n/Google Calendar event into a consistent dict."""
    title = item.get("title") or item.get("summary") or "Event"

    date_str = (
        item.get("date")
        or item.get("start_date")
        or item.get("start")
        or ""
    )
    if isinstance(date_str, dict):
        date_str = date_str.get("date") or date_str.get("dateTime") or ""

    time_str = item.get("time") or item.get("start_time") or ""
    if isinstance(item.get("start"), dict):
        dt = item["start"].get("dateTime", "")
        if "T" in str(dt):
            time_str = dt.split("T")[1][:5] if not time_str else time_str

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


def render(user: dict):
    username = user.get("username", "default")

    st.markdown(
        '<div class="wp-page-header"><div class="wp-greeting">📅 Calendar</div>'
        '<div class="wp-greeting-sub">View your tasks and schedule at a glance.</div></div>',
        unsafe_allow_html=True,
    )

    # ── Month Navigation ──────────────────────────────────
    today = date.today()

    if "cal_year" not in st.session_state:
        st.session_state.cal_year = today.year
    if "cal_month" not in st.session_state:
        st.session_state.cal_month = today.month

    year = st.session_state.cal_year
    month = st.session_state.cal_month

    col_prev, col_title, col_next = st.columns([1, 4, 1])
    with col_prev:
        if st.button("◀", key="cal_prev"):
            if month == 1:
                st.session_state.cal_month = 12
                st.session_state.cal_year -= 1
            else:
                st.session_state.cal_month -= 1
            st.rerun()
    with col_title:
        month_name = calendar.month_name[month]
        st.markdown(
            f'<div class="wp-calendar-header"><div class="wp-calendar-month">{month_name} {year}</div></div>',
            unsafe_allow_html=True,
        )
    with col_next:
        if st.button("▶", key="cal_next"):
            if month == 12:
                st.session_state.cal_month = 1
                st.session_state.cal_year += 1
            else:
                st.session_state.cal_month += 1
            st.rerun()

    # ── Load tasks for this month ─────────────────────────
    data, _ = api_call("GET", "/tasks", username)
    tasks = data.get("tasks", []) if data else []

    tasks_by_date = {}
    for t in tasks:
        due = t.get("due_date")
        if due:
            try:
                d = date.fromisoformat(due)
                if d.year == year and d.month == month:
                    key = d.day
                    if key not in tasks_by_date:
                        tasks_by_date[key] = []
                    tasks_by_date[key].append(t)
            except (ValueError, TypeError):
                pass

    # ── Load calendar events for this month ────────────────
    # Use a cached refresh key so the user can force-reload
    cal_refresh_key = f"_cal_events_{year}_{month}"
    if cal_refresh_key not in st.session_state:
        st.session_state[cal_refresh_key] = _fetch_calendar_events_for_month(year, month)
    cal_events = st.session_state[cal_refresh_key]

    # Refresh button
    col_refresh, _ = st.columns([1, 5])
    with col_refresh:
        if st.button("\U0001f504 Refresh Events", key="cal_refresh_events"):
            st.session_state[cal_refresh_key] = _fetch_calendar_events_for_month(year, month)
            st.rerun()

    events_by_date = {}
    for ev in cal_events:
        ev_date = ev.get("date", "")
        if ev_date:
            try:
                d = date.fromisoformat(ev_date)
                if d.year == year and d.month == month:
                    key = d.day
                    if key not in events_by_date:
                        events_by_date[key] = []
                    events_by_date[key].append(ev)
            except (ValueError, TypeError):
                pass

    # ── Calendar Grid ─────────────────────────────────────
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    html_parts = ['<div class="wp-calendar-grid">']

    # Day headers
    for d in day_names:
        html_parts.append(f'<div class="wp-calendar-day-header">{d}</div>')

    # Get calendar data
    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdayscalendar(year, month)

    for week in month_days:
        for day in week:
            if day == 0:
                html_parts.append('<div class="wp-calendar-day empty"></div>')
            else:
                is_today = (year == today.year and month == today.month and day == today.day)
                today_class = " today" if is_today else ""

                events_html = ""
                day_tasks = tasks_by_date.get(day, [])
                day_cal_events = events_by_date.get(day, [])
                all_items = day_cal_events + day_tasks  # Calendar events first
                for t in all_items[:5]:
                    # Determine if this is a calendar event or a task
                    is_cal = "date" in t and "due_date" not in t and t.get("date")
                    if is_cal:
                        # Calendar event — green accent
                        time_label = f" 🕐 {t['time']}" if t.get("time") else ""
                        events_html += f'<div class="wp-calendar-event" style="background:#dcfce7;color:#166534">📅 {t["title"]}{time_label}</div>'
                    else:
                        # Task — original styling
                        priority_color = {"High": "var(--red-100);color:var(--red-700)",
                                          "Low": "var(--blue-100);color:var(--blue-700)"}.get(
                            t.get("priority"), "var(--purple-100);color:var(--purple-700)")
                        events_html += f'<div class="wp-calendar-event" style="background:{priority_color.split(";")[0]};color:{priority_color.split(";")[1]}">{t["title"]}</div>'

                html_parts.append(
                    f'<div class="wp-calendar-day{today_class}">'
                    f'<div class="wp-calendar-day-num">{day}</div>'
                    f'{events_html}'
                    f'</div>'
                )

    html_parts.append('</div>')
    st.markdown("\n".join(html_parts), unsafe_allow_html=True)

    # ── Tasks due this month ──────────────────────────────
    month_tasks = [t for t in tasks if t.get("due_date")]
    month_tasks_filtered = []
    for t in month_tasks:
        try:
            d = date.fromisoformat(t["due_date"])
            if d.year == year and d.month == month:
                month_tasks_filtered.append(t)
        except (ValueError, TypeError):
            pass

    if month_tasks_filtered:
        from _pages._api import badge_html
        st.markdown('<div class="wp-section-title">Tasks due this month</div>', unsafe_allow_html=True)
        for t in month_tasks_filtered:
            completed = t.get("completed", False)
            style = "text-decoration:line-through;opacity:0.5" if completed else ""
            priority = t.get("priority", "Medium")
            st.markdown(
                f'<div class="wp-task-row">'
                f'<span class="wp-task-title" style="{style}">{t["title"]}</span>'
                f'<span class="wp-task-due">Due {t["due_date"]}</span>'
                f'{badge_html(priority)}'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ── Calendar events this month ────────────────────────
    if cal_events:
        st.markdown('<div class="wp-section-title">📅 Calendar Events this month</div>', unsafe_allow_html=True)
        for ev in cal_events:
            ev_date = ev.get("date", "")
            time_label = f" at {ev['time']}" if ev.get("time") else ""
            desc = f" — {ev['description']}" if ev.get("description") else ""
            st.markdown(
                f'<div class="wp-task-row">'
                f'<span class="wp-task-title" style="color:#166534">📅 {ev["title"]}</span>'
                f'<span class="wp-task-due">{ev_date}{time_label}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
