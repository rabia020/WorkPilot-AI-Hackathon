"""
Small inline-SVG icon set used across the redesigned frontend.
Kept in one place so every page references the same visual language.
All icons are 24x24 viewBox, stroke=currentColor, so they inherit color via CSS.
"""

def _svg(paths, viewbox="0 0 24 24"):
    return (
        f'<svg viewBox="{viewbox}" fill="none" stroke="currentColor" '
        f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{paths}</svg>'
    )

ICON_ROBOT = _svg(
    '<rect x="4" y="8" width="16" height="11" rx="3"/>'
    '<circle cx="9" cy="13.5" r="1.2" fill="currentColor" stroke="none"/>'
    '<circle cx="15" cy="13.5" r="1.2" fill="currentColor" stroke="none"/>'
    '<path d="M12 8V4"/><circle cx="12" cy="3" r="1" fill="currentColor" stroke="none"/>'
    '<path d="M8 19v2M16 19v2"/>'
)

ICON_MANAGER = _svg(
    '<circle cx="9" cy="8" r="3"/><path d="M4 20c0-3 2.5-5 5-5s5 2 5 5"/>'
    '<circle cx="18" cy="7" r="1.6"/><path d="M18 10v2M16.8 16h2.4M18 13.5v0"/>'
)

ICON_EMPLOYEE = _svg(
    '<circle cx="8" cy="8" r="3"/><path d="M3 20c0-3 2.2-5 5-5s5 2 5 5"/>'
    '<circle cx="17" cy="8" r="3"/><path d="M12.5 20c.3-2.6 2.3-4.4 4.5-4.4s4.2 1.8 4.5 4.4"/>'
)

ICON_MAIL = _svg('<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>')

ICON_DOC = _svg(
    '<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4"/>'
    '<path d="M9.5 12h5M9.5 15h5M9.5 9h2"/>'
)

ICON_CHART = _svg('<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>')

ICON_CALENDAR = _svg(
    '<rect x="3.5" y="5" width="17" height="16" rx="2"/><path d="M3.5 10h17"/>'
    '<path d="M8 3v4M16 3v4"/><path d="M8 14h.01M12 14h.01M16 14h.01M8 17h.01M12 17h.01"/>'
)

ICON_TASKS = _svg('<circle cx="7" cy="8" r="3"/><path d="M2 20c0-3 2.2-5 5-5s5 2 5 5"/><path d="M14 8h8M14 13h8M14 18h5"/>')

ICON_SHIELD = _svg('<path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z"/><path d="M9 12l2 2 4-4"/>')

ICON_ARROW_RIGHT = _svg('<path d="M5 12h14M13 6l6 6-6 6"/>')

ICON_ARROW_LEFT = _svg('<path d="M19 12H5M11 18l-6-6 6-6"/>')

ICON_USER = _svg('<circle cx="12" cy="8" r="3.5"/><path d="M4.5 20c0-4 3.4-6.5 7.5-6.5s7.5 2.5 7.5 6.5"/>')

ICON_LOCK = _svg('<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 018 0v3"/>')

ICON_EYE = _svg('<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="2.5"/>')

ICON_PLUS = _svg('<path d="M12 5v14M5 12h14"/>')

ICON_CHAT = _svg('<path d="M4 5h16v11H8l-4 4z"/>')

ICON_SEARCH = _svg('<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>')

ICON_GEAR = _svg(
    '<circle cx="12" cy="12" r="3"/>'
    '<path d="M19.4 15a1.7 1.7 0 00.34 1.87l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.7 1.7 0 00-1.87-.34 1.7 1.7 0 00-1 1.55V21a2 2 0 11-4 0v-.09a1.7 1.7 0 00-1-1.55 1.7 1.7 0 00-1.87.34l-.06.06a2 2 0 11-2.83-2.83l.06-.06A1.7 1.7 0 004.6 15a1.7 1.7 0 00-1.55-1H3a2 2 0 110-4h.09A1.7 1.7 0 004.6 9a1.7 1.7 0 00-.34-1.87l-.06-.06a2 2 0 112.83-2.83l.06.06A1.7 1.7 0 009 4.6a1.7 1.7 0 001-1.55V3a2 2 0 114 0v.09a1.7 1.7 0 001 1.55 1.7 1.7 0 001.87-.34l.06-.06a2 2 0 112.83 2.83l-.06.06A1.7 1.7 0 0019 9c.14.36.2.75.2 1.15V15z" stroke-width="0"/>'
)

ICON_LOGOUT = _svg('<path d="M9 4H5a2 2 0 00-2 2v12a2 2 0 002 2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/>')

ICON_BRIEFCASE = _svg('<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M8 7V5a2 2 0 012-2h4a2 2 0 012 2v2"/>')


def md_html(html):
    """
    Collapse a multi-line HTML string down to single-line-safe output
    before handing it to st.markdown(..., unsafe_allow_html=True).

    Streamlit's markdown renderer treats any line that starts with 4+
    leading spaces as a Markdown *indented code block* -- even with
    unsafe_allow_html=True. textwrap.dedent() only strips the minimum
    common indentation across all lines, so a multi-line f-string with
    slightly uneven indentation (e.g. a wrapped attribute continuation)
    can leave some lines with residual leading spaces, which then get
    rendered as literal text in a code block instead of parsed as HTML.

    This strips per-line leading/trailing whitespace and joins
    everything with a single space, which sidesteps the whole class of
    bug regardless of how the source string was indented.
    """
    return " ".join(line.strip() for line in html.strip().splitlines())