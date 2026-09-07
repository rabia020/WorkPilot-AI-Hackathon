import streamlit as st


def show_employee_panel():

    user = st.session_state.user

    st.markdown(
        '<div class="eka-workspace-title" style="font-size:20px;">👤 My Profile</div>',
        unsafe_allow_html=True
    )

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    with st.container():

        st.markdown('<div class="eka-overview-card">', unsafe_allow_html=True)

        col1, col2 = st.columns(2)

        with col1:
            st.text_input("Username", value=user["username"], disabled=True)
            st.text_input("Role", value=user["role"].capitalize(), disabled=True)

        with col2:
            st.text_input("Full Name", value=user.get("full_name", ""), disabled=True)
            st.text_input("Email", value=user.get("email", ""), disabled=True)

        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    st.success("Account Status : Active")

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    st.markdown(
        '<div class="eka-starter-label">Available Features</div>',
        unsafe_allow_html=True
    )

    features = [
        ("✅", "AI Chat Assistant", True),
        ("✅", "Company Knowledge Search (RAG)", True),
        ("✅", "Company Documents", True),
        ("🕓", "Email Assistant", False),
        ("🕓", "Calendar Assistant", False),
        ("🕓", "Report Generation", False),
        ("🕓", "Database Query Assistant", False),
    ]

    rows = ""
    for mark, label, live in features:
        status = "Available" if live else "Coming soon"
        color = "var(--accent-teal-light)" if live else "var(--text-muted)"
        rows += (
            f'<div class="eka-cap-row" style="justify-content:space-between;">'
            f'<span>{mark}&nbsp;&nbsp;{label}</span>'
            f'<span style="color:{color};font-size:12.5px;font-weight:700;">{status}</span>'
            f'</div>'
        )

    st.markdown(
        f'<div class="eka-capabilities-box">{rows}</div>',
        unsafe_allow_html=True
    )

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    st.info("If you require additional permissions, please contact your manager.")