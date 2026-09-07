import os
import pandas as pd
import streamlit as st

from rag.ingest import ingest_pdf

from auth import (
    create_user,
    get_all_users,
    activate_user,
    deactivate_user,
    delete_user
)

# ----------------------------------------
# CONFIG
# ----------------------------------------

UPLOAD_FOLDER = "data"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ----------------------------------------
# MANAGER PANEL
# ----------------------------------------

def show_manager_panel():

    st.header("🛠 Manager Dashboard")

    tab1, tab2, tab3 = st.tabs(
        [
            "👤 Create User",
            "👥 Manage Users",
            "📂 Company Documents"
        ]
    )

    # =====================================================
    # TAB 1 - CREATE USER
    # =====================================================

    with tab1:

        st.subheader("Create New User")

        full_name = st.text_input("Full Name")

        email = st.text_input("Email")

        username = st.text_input("Username")

        password = st.text_input(
            "Password",
            type="password"
        )

        role = st.selectbox(
            "Role",
            [
                "employee",
                "manager"
            ]
        )

        if st.button("Create User"):

            if (
                full_name == ""
                or email == ""
                or username == ""
                or password == ""
            ):
                st.warning("Please complete all fields.")

            else:

                success, message = create_user(
                    full_name=full_name,
                    email=email,
                    username=username,
                    password=password,
                    role=role,
                    created_by=st.session_state.user["username"]
                )

                if success:
                    st.success(message)
                else:
                    st.error(message)

    # =====================================================
    # TAB 2 - USER MANAGEMENT
    # =====================================================

    with tab2:

        st.subheader("Registered Users")

        users = get_all_users()

        if len(users) == 0:

            st.info("No users found.")

        else:

            columns = [
                "ID",
                "Full Name",
                "Username",
                "Email",
                "Role",
                "Active",
                "Created At",
                "Last Login",
                "Created By"
            ]

            df = pd.DataFrame(
                users,
                columns=columns
            )

            st.dataframe(
                df,
                use_container_width=True
            )

            st.markdown("---")

            selected_user = st.selectbox(
                "Select User",
                df["Username"]
            )

            col1, col2, col3 = st.columns(3)

            with col1:

                if st.button("Activate"):

                    activate_user(selected_user)

                    st.success("User Activated")

                    st.rerun()

            with col2:

                if st.button("Deactivate"):

                    if (
                        selected_user
                        ==
                        st.session_state.user["username"]
                    ):

                        st.error(
                            "You cannot deactivate your own account."
                        )

                    else:

                        deactivate_user(selected_user)

                        st.success("User Deactivated")

                        st.rerun()

            with col3:

                if st.button("Delete"):

                    if (
                        selected_user
                        ==
                        st.session_state.user["username"]
                    ):

                        st.error(
                            "You cannot delete your own account."
                        )

                    else:

                        delete_user(selected_user)

                        st.success("User Deleted")

                        st.rerun()

    # =====================================================
    # TAB 3 - DOCUMENT UPLOAD
    # =====================================================

    with tab3:

        st.subheader("📂 Upload Company Documents")

        st.write(
            "Managers can upload company documents to the AI Knowledge Base."
        )

        uploaded_file = st.file_uploader(
            "Choose File",
            type=[
                "pdf",
                "docx",
                "txt"
            ]
        )

        if uploaded_file is not None:

            save_path = os.path.join(
                UPLOAD_FOLDER,
                uploaded_file.name
            )

            with open(save_path, "wb") as f:

                f.write(uploaded_file.getbuffer())

            st.success(
                f"{uploaded_file.name} saved successfully."
            )

            if st.button("Add to Knowledge Base"):

                try:

                    with st.spinner(
                        "Indexing document into ChromaDB..."
                    ):

                        # -----------------------------
                        # Direct Python RAG Ingestion
                        # -----------------------------
                        ingest_pdf(save_path)

                    st.success(
                        "Document successfully indexed into ChromaDB."
                    )

                except Exception as e:

                    st.error(
                        f"Indexing Failed: {str(e)}"
                    )

        st.info(
            """
Only Managers can upload company documents.

Uploaded documents are indexed into ChromaDB and become searchable by all employees through the AI Assistant.
"""
        )