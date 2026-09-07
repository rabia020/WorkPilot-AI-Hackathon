"""
streamlit_app.py - WorkPilot AI Main Application
Role-based workspace: Manager / Employee
"""
import streamlit as st
from auth import login
from icons import ICON_ROBOT

@st.cache_resource
def warm_up_rag_dependencies():
    """Pre-load chromadb/pyarrow/sentence-transformers on first app boot,
    so the very first native-library touch happens at startup rather than
    later during page navigation (avoids a Streamlit-thread crash)."""
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
        from config import CHROMA_PATH, EMBEDDING_MODEL

        chromadb.PersistentClient(path=CHROMA_PATH)
        SentenceTransformer(EMBEDDING_MODEL)
    except Exception:
        # If model download fails (no internet, HuggingFace down, etc.),
        # continue anyway — RAG features will degrade but the app won't crash.
        pass
    return True

try:
    warm_up_rag_dependencies()
except Exception:
    pass

st.set_page_config(
    page_title="WorkPilot AI",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# CSS
# ============================================================
def load_css():
    try:
        with open("assets/style.css", "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass

load_css()

# ============================================================
# SESSION STATE DEFAULTS
# ============================================================
DEFAULTS = {
    "page": "landing",
    "logged_in": False,
    "user": None,
    "main_view": "home",
}
for key, val in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ============================================================
# DARK SIDEBAR
# ============================================================
def render_sidebar(user):
    full_name = user.get("full_name") or user.get("username", "User")
    role = (user.get("role") or "").capitalize()

    with st.sidebar:
        # -- Brand --
        st.markdown(
            '<div class="wk-sidebar-brand">'
            '<div class="wk-sidebar-brand-icon">🤖</div>'
            '<div>'
            '<div class="wk-sidebar-brand-text">WorkPilot AI</div>'
            '<div class="wk-sidebar-brand-sub">Autonomous AI Work Assistant</div>'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        # -- New Chat button --
        if st.button("+ New Chat", key="sidebar_new_chat", use_container_width=True, type="primary"):
            for k in ("messages", "pending_review", "agent_session_id",
                       "ai_messages", "ai_session_id", "ai_pending_review"):
                st.session_state.pop(k, None)
            st.session_state.main_view = "home"
            st.rerun()

        st.markdown('<div class="wk-sidebar-divider"></div>', unsafe_allow_html=True)

        # -- Navigation --
        st.markdown('<div class="wk-sidebar-section">Navigation</div>', unsafe_allow_html=True)

        nav_items = [
            ("home",      "🏠  Home"),
            ("workspace", "🤖  WorkPilot"),
            ("tasks",     "✅  Tasks"),
            ("notes",     "📝  Notes"),
            ("calendar",  "📅  Calendar"),
            ("plan_day",  "📋  Plan My Day"),
            ("approvals", "⚡  Approvals"),
            ("activity",  "🧠  Activity"),
        ]
        current_view = st.session_state.get("main_view", "home")
        for nav_id, label in nav_items:
            is_active = current_view == nav_id
            if is_active:
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:8px;padding:8px 12px;'
                    f'margin-bottom:4px;border-radius:10px;'
                    f'background:#ede9fe;border-left:3px solid #8f75ca;'
                    f'font-size:14px;font-weight:600;color:#8f75ca">'
                    f'{label}'
                    f'<span style="margin-left:auto;font-size:8px">\u25cf</span></div>',
                    unsafe_allow_html=True,
                )
            else:
                if st.button(label, key=f"nav_{nav_id}", use_container_width=True):
                    st.session_state.main_view = nav_id
                    st.rerun()

        st.markdown('<div class="wk-sidebar-divider"></div>', unsafe_allow_html=True)

        # -- User Info --
        st.markdown(
            f'<div class="wp-user-info">'
            f'<div class="wp-user-name">{full_name}</div>'
            f'<div class="wp-user-role">{role}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        st.markdown('<div style="height: 8px"></div>', unsafe_allow_html=True)

        if st.button("⚙️  Settings", key="sidebar_settings", use_container_width=True):
            st.session_state.main_view = "settings"
            st.rerun()

        if st.button("🚪  Sign Out", key="sidebar_signout", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.session_state.page = "landing"
            st.session_state.logged_in = False
            st.rerun()


# ============================================================
# WORKSPACE HEADERS
# ============================================================
def _render_top_bar(full_name, role_label):
    """Render the dark top bar matching screenshots: branding left, user avatar right."""
    avatar_letter = full_name[0].upper() if full_name else "U"
    st.markdown(
        '<div class="wk-top-bar">'
        '<div class="wk-top-bar-inner">'
        '<div class="wk-top-bar-left">'
        '<div class="wk-top-bar-brand">WorkPilot AI</div>'
        '<div class="wk-top-bar-sub">Autonomous AI Work Assistant</div>'
        '</div>'
        '<div class="wk-top-bar-right">'
        f'<div class="wk-top-bar-user-info">'
        f'<div class="wk-top-bar-name">{full_name}</div>'
        f'<div class="wk-top-bar-role">{role_label}</div>'
        '</div>'
        f'<div class="wk-top-bar-avatar">{avatar_letter}</div>'
        '</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def _workspace_header(full_name, role_label, emoji, subtitle):
    from datetime import datetime
    hour = datetime.now().hour
    if hour < 12:
        greeting = "Good morning"
    elif hour < 17:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"

    st.markdown(
        '<div class="wk-workspace-header">'
        f'<div class="wk-workspace-title">{emoji} {role_label} Workspace</div>'
        f'<div class="wk-workspace-greeting">{greeting} <span class="wk-workspace-name">{full_name}</span>, '
        f'{subtitle}</div>'
        '</div>',
        unsafe_allow_html=True,
    )


# ============================================================
# MANAGER WORKSPACE
# ============================================================
def render_manager_workspace(user):
    full_name = user.get("full_name") or user.get("username", "User")
    _workspace_header(full_name, "Manager", "\U0001f527",
                      "what would you like WorkPilot to help with?")

    tab_ai, tab_doc = st.tabs(["\U0001f4ac AI Assistant", "\U0001f4c1 Document Management"])

    with tab_ai:
        from chat_panel import show_chat_panel_content
        show_chat_panel_content()

    with tab_doc:
        from manager_panel import show_manager_panel
        show_manager_panel()

    # Chat input rendered OUTSIDE tabs so it sits at the viewport bottom
    from chat_panel import show_chat_panel_input
    show_chat_panel_input()


# ============================================================
# EMPLOYEE WORKSPACE
# ============================================================
def render_employee_workspace(user):
    full_name = user.get("full_name") or user.get("username", "User")
    _workspace_header(full_name, "Employee", "\U0001f392",
                      "what would you like WorkPilot to help with?")

    tab_ai, tab_profile = st.tabs(["\U0001f4ac AI Assistant", "\U0001f464 My Profile"])

    with tab_ai:
        from chat_panel import show_chat_panel_content
        show_chat_panel_content()

    with tab_profile:
        from employee_panel import show_employee_panel
        show_employee_panel()

    # Chat input rendered OUTSIDE tabs so it sits at the viewport bottom
    from chat_panel import show_chat_panel_input
    show_chat_panel_input()


# ============================================================
# LANDING PAGE
# ============================================================
GRADIENT_BG = (
    '<style>'
    '.stApp { background: '
    'radial-gradient(circle at top left, rgba(225,216,247,0.9), transparent 28%), '
    'radial-gradient(circle at bottom right, rgba(192,167,235,0.28), transparent 30%), '
    'linear-gradient(180deg, #f8f4ff 0%, #f4f0ff 100%) !important; }'
    '</style>'
)


def landing_page():
    st.markdown(GRADIENT_BG, unsafe_allow_html=True)
    left, center, right = st.columns([0.8, 4, 0.8])
    with center:
        st.markdown(
            '<div class="wp-auth-card" style="padding: 56px 48px; text-align: center">'
            '<div style="margin-bottom: 28px">'
            '<div style="width:80px;height:80px;border-radius:22px;'
            'background:linear-gradient(135deg,#6d28d9,#8b5cf6);'
            'display:inline-flex;align-items:center;justify-content:center;'
            'box-shadow:0 12px 28px rgba(109,40,217,0.35)">'
            '<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M12 2a7 7 0 0 0-7 7c0 2.5 1.5 4.5 3 6l4 5 4-5c1.5-1.5 3-3.5 3-6a7 7 0 0 0-7-7z"/>'
            '<path d="M9 9h.01"/><path d="M15 9h.01"/>'
            '<path d="M8 13c0 0 1.5 2 4 2s4-2 4-2"/>'
            '</svg>'
            '</div>'
            '</div>'
            '<div style="display:inline-flex;align-items:center;gap:8px;padding:8px 20px;'
            'border-radius:999px;border:1px solid #E1D8F7;background:#f8f5ff;'
            'margin-bottom:24px">'
            '<span style="font-size:14px">✦</span>'
            '<span style="font-size:11px;font-weight:700;letter-spacing:0.22em;'
            'text-transform:uppercase;color:#6d28d9">AI Work-Pilot</span>'
            '</div>'
            '<h1 style="font-size:clamp(32px,3.5vw,48px);font-weight:800;color:#1e293b;'
            'letter-spacing:-0.02em;line-height:1.12;margin:0 0 16px 0">WorkPilot AI</h1>'
            '<p style="font-size:16px;color:#64748b;line-height:1.7;max-width:440px;margin:0 auto">'
            'An AI employee that understands your work, plans your day, '
            'and executes tasks for you.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div style="height: 28px"></div>', unsafe_allow_html=True)
        st.markdown(
            '<div style="text-align:center;font-weight:800;color:var(--text-primary);'
            'font-size:16px;margin-bottom:16px">Continue As</div>',
            unsafe_allow_html=True,
        )
        col1, col2 = st.columns(2, gap="large")
        with col1:
            if st.button("👤  Manager", use_container_width=True, type="primary", key="mgr_btn"):
                st.session_state.page = "manager_login"
                st.rerun()
        with col2:
            if st.button("👥  Employee", use_container_width=True, key="emp_btn"):
                st.session_state.page = "employee_login"
                st.rerun()



# ============================================================
# LOGIN PAGE
# ============================================================
def login_page():
    st.markdown(GRADIENT_BG, unsafe_allow_html=True)
    is_manager = st.session_state.page == "manager_login"
    title = "Manager Login" if is_manager else "Employee Login"
    subtitle = "Sign in to access your WorkPilot AI workspace."
    expected = "manager" if is_manager else "employee"

    # Back button (outside the card)
    left, center, right = st.columns([1, 4, 1])
    with left:
        if st.button("\u2190 Back", type="secondary", key="login_back"):
            st.session_state.page = "landing"
            st.rerun()

    # Single card: wider column ratio
    left2, center2, right2 = st.columns([0.8, 3.5, 0.8])
    with center2:
        # Everything inside ONE form = ONE card
        with st.form("login_form", clear_on_submit=False):
            # Purple gradient top border
            st.markdown(
                '<div style="height:4px;background:linear-gradient(90deg,#6d28d9,#8b5cf6,#a78bfa);'
                'border-radius:20px 20px 0 0;margin:-16px -16px 24px -16px"></div>',
                unsafe_allow_html=True,
            )
            # Brand section
            st.markdown(
                '<div style="display:flex;align-items:center;gap:14px;padding:16px 20px;'
                'background:#f8f5ff;border:1px solid #e9e0f7;border-radius:16px;margin-bottom:24px">'
                '<div style="width:44px;height:44px;border-radius:12px;'
                'background:linear-gradient(135deg,#6d28d9,#8b5cf6);'
                'display:inline-flex;align-items:center;justify-content:center;'
                'box-shadow:0 4px 12px rgba(109,40,217,0.25);flex-shrink:0">'
                '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                '<path d="M12 2a7 7 0 0 0-7 7c0 2.5 1.5 4.5 3 6l4 5 4-5c1.5-1.5 3-3.5 3-6a7 7 0 0 0-7-7z"/>'
                '<path d="M9 9h.01"/><path d="M15 9h.01"/>'
                '<path d="M8 13c0 0 1.5 2 4 2s4-2 4-2"/>'
                '</svg>'
                '</div>'
                '<div>'
                '<p style="font-size:11px;font-weight:700;letter-spacing:0.18em;'
                'text-transform:uppercase;color:#6d28d9;margin:0">WorkPilot AI</p>'
                f'<p style="font-size:13px;font-weight:400;color:#64748b;margin:4px 0 0 0">{subtitle}</p>'
                '</div></div>',
                unsafe_allow_html=True,
            )
            # Welcome back + title
            st.markdown(
                '<div style="text-align:center;margin-bottom:16px">'
                '<p style="font-size:11px;font-weight:700;letter-spacing:0.18em;'
                'text-transform:uppercase;color:#94a3b8;margin:0">Welcome back</p>'
                f'<h1 style="font-size:32px;font-weight:800;color:#1e293b;margin:8px 0 0 0">{title}</h1>'
                '</div>',
                unsafe_allow_html=True,
            )
            # Form inputs
            username = st.text_input("Username", placeholder="Enter your username", key="login_user")
            password = st.text_input("Password", type="password", placeholder="Enter your password", key="login_pass")
            submitted = st.form_submit_button("\u2192  Login", use_container_width=True, type="primary")

        if submitted:
            if not username.strip() or not password.strip():
                st.warning("Please enter both username and password.")
            else:
                user = login(username.strip(), password)
                if user is None:
                    st.error("Invalid username or password.")
                elif user["role"] != expected:
                    st.error(f"This account belongs to a {user['role'].capitalize()}, not {expected.capitalize()}.")
                else:
                    st.session_state.logged_in = True
                    st.session_state.user = user
                    st.session_state.page = "dashboard"
                    st.session_state.main_view = "home"
                    st.rerun()

        st.markdown(
            '<p style="text-align:center;font-size:12px;color:#94a3b8;margin-top:24px">'
            'Powered by WorkPilot AI \u2014 your autonomous work assistant.</p>',
            unsafe_allow_html=True,
        )


# ============================================================
# PLAN MY DAY PAGE
# ============================================================
def _render_plan_day(user):
    full_name = user.get("full_name") or user.get("username", "User")
    username = user.get("username", "default")

    st.markdown(
        '<div class="wk-workspace-header">'
        '<div class="wk-workspace-title">📋 Plan My Day</div>'
        '<div class="wk-workspace-greeting">Let AI organize your tasks into an optimized daily plan.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div style="height: 12px"></div>', unsafe_allow_html=True)

    # Generate plan button
    if st.button("🤖 Generate My Daily Plan", type="primary", use_container_width=True, key="gen_plan_btn"):
        from agents.daily_planner import plan_my_day
        with st.spinner("Analyzing your tasks, notes, and schedule..."):
            try:
                result = plan_my_day(username)
                st.session_state["plan_result"] = result
            except Exception as e:
                st.error(f"Failed to generate plan: {e}")
                return

    # Display existing or new result
    result = st.session_state.get("plan_result")
    if result:
        # Greeting
        greeting = result.get("greeting", "")
        if greeting:
            st.markdown(f"### {greeting}")

        # Summary
        summary = result.get("summary", "")
        if summary:
            st.info(summary)

        st.markdown('<div style="height: 8px"></div>', unsafe_allow_html=True)

        # Context info
        ctx = result.get("context_used", {})
        if ctx:
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Tasks", ctx.get("tasks_count", 0))
            with c2:
                st.metric("Notes", ctx.get("notes_count", 0))
            with c3:
                st.metric("Calendar", "Yes" if ctx.get("has_calendar") else "No")
            with c4:
                st.metric("Emails", "Yes" if ctx.get("has_emails") else "No")

        st.markdown('<div style="height: 12px"></div>', unsafe_allow_html=True)

        # Plan sections
        plan = result.get("plan", {})

        # High priority
        high = plan.get("high_priority", [])
        if high:
            st.markdown('**🔴 High Priority**')
            for item in high:
                task = item.get("task", "")
                time_est = item.get("estimated_time", "")
                reason = item.get("reason", "")
                st.markdown(
                    f'<div class="wp-task-row">'
                    f'<span class="wp-task-title">{task}</span>'
                    f'<span class="wp-task-due">{time_est}</span>'
                    f'<span class="wp-badge wp-badge-high">High</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if reason:
                    st.caption(f"  {reason}")

        # Medium priority
        medium = plan.get("medium_priority", [])
        if medium:
            st.markdown('**🟡 Medium Priority**')
            for item in medium:
                task = item.get("task", "")
                time_est = item.get("estimated_time", "")
                st.markdown(
                    f'<div class="wp-task-row">'
                    f'<span class="wp-task-title">{task}</span>'
                    f'<span class="wp-task-due">{time_est}</span>'
                    f'<span class="wp-badge wp-badge-medium">Medium</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        # Low priority
        low = plan.get("low_priority", [])
        if low:
            st.markdown('**🔵 Low Priority**')
            for item in low:
                task = item.get("task", "")
                time_est = item.get("estimated_time", "")
                st.markdown(
                    f'<div class="wp-task-row">'
                    f'<span class="wp-task-title">{task}</span>'
                    f'<span class="wp-task-due">{time_est}</span>'
                    f'<span class="wp-badge wp-badge-low">Low</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        # Breaks
        breaks = plan.get("breaks", [])
        if breaks:
            st.markdown('<div style="height: 8px"></div>', unsafe_allow_html=True)
            st.markdown('**☕ Break Schedule**')
            for b in breaks:
                st.markdown(f"- {b.get('type', 'Break')} after {b.get('after', 'tasks')} -- {b.get('duration', '5 min')}")

        # Recommendations
        recs = plan.get("recommendations", [])
        if recs:
            st.markdown('<div style="height: 8px"></div>', unsafe_allow_html=True)
            st.markdown('**💡 Recommendations**')
            for r in recs:
                st.markdown(f"- {r}")

    else:
        st.markdown(
            '<div class="wp-card wp-empty">'
            '<div class="wp-empty-icon">📋</div>'
            'Click the button above to generate your AI-powered daily plan.'
            '</div>',
            unsafe_allow_html=True,
        )


# ============================================================
# MAIN DASHBOARD (REDIRECTOR)
# ============================================================
def dashboard():
    user = st.session_state.user
    render_sidebar(user)

    view = st.session_state.get("main_view", "home")
    role = (user.get("role") or "employee").lower()

    if view == "home":
        from _pages import dashboard as dash_mod
        dash_mod.render(user)

    elif view == "workspace":
        if role == "manager":
            render_manager_workspace(user)
        else:
            render_employee_workspace(user)

    elif view == "tasks":
        from _pages import tasks_page as mod
        mod.render(user)

    elif view == "projects":
        from _pages import projects_page as mod
        mod.render(user)

    elif view == "notes":
        from _pages import notes_page as mod
        mod.render(user)

    elif view == "calendar":
        from _pages import calendar_page as mod
        mod.render(user)

    elif view == "plan_day":
        _render_plan_day(user)

    elif view == "inbox":
        from _pages import inbox_page as mod
        mod.render(user)

    elif view == "approvals":
        from _pages import approvals_page as mod
        mod.render(user)

    elif view == "activity":
        from _pages import activity_page as mod
        mod.render(user)

    elif view == "settings":
        from _pages import settings_page as mod
        mod.render(user)

    else:
        st.session_state.main_view = "home"
        st.rerun()


# ============================================================
# ENTRY POINT
# ============================================================
def main():
    if st.session_state.logged_in:
        dashboard()
        return
    page = st.session_state.get("page", "landing")
    if page == "landing":
        landing_page()
    elif page in ("manager_login", "employee_login"):
        login_page()
    else:
        st.session_state.page = "landing"
        st.rerun()


if __name__ == "__main__":
    main()
