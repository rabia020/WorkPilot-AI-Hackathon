"""
pages/notes_page.py
====================
WorkPilot AI — Notes Management
"""

import requests
import streamlit as st

from config import FASTAPI_BASE
from _pages._api import api_call


def render(user: dict):
    username = user.get("username", "default")

    st.markdown(
        '<div class="wp-page-header"><div class="wp-greeting">📝 Notes</div>'
        '<div class="wp-greeting-sub">Jot down thoughts, plans, anything.</div></div>',
        unsafe_allow_html=True,
    )

    # ── Track form submission results outside the form ────
    if "_note_submit_error" in st.session_state:
        err = st.session_state.pop("_note_submit_error")
        st.error(err)
    if "_note_submit_ok" in st.session_state:
        msg = st.session_state.pop("_note_submit_ok")
        st.success(msg)

    # ── New Note Form ─────────────────────────────────────
    with st.form("add_note_form", clear_on_submit=False):
        st.markdown('<div style="font-weight:700;font-size:14px;margin-bottom:8px">New note</div>', unsafe_allow_html=True)
        title = st.text_input("Title", placeholder="Note title", label_visibility="collapsed")
        content = st.text_area("Content", placeholder="Write something...", height=120, label_visibility="collapsed")
        submitted = st.form_submit_button("Save note", type="primary", use_container_width=True)

        if submitted:
            if not title or not title.strip():
                st.warning("Please enter a note title.")
            else:
                result, err = api_call("POST", "/notes", username, {
                    "title": title.strip(),
                    "content": content,
                })
                if err:
                    st.error(err)
                elif result and result.get("status") == "success":
                    st.session_state["_note_submit_ok"] = f"Note saved: {title.strip()}"
                    st.rerun()
                else:
                    st.error("Unexpected response from backend.")

    st.markdown('<div style="height: 16px"></div>', unsafe_allow_html=True)

    # ── Notes Grid ────────────────────────────────────────
    data, err = api_call("GET", "/notes", username)
    if err:
        st.warning(f"Could not load notes: {err}")
        notes = []
    else:
        notes = data.get("notes", []) if data else []

    if not notes:
        st.markdown(
            '<div class="wp-card wp-empty">'
            '<div class="wp-empty-icon">📒</div>'
            'No notes yet. Create your first note above!'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    # Display notes in a grid (3 columns)
    cols_per_row = 3
    for i in range(0, len(notes), cols_per_row):
        row_notes = notes[i:i + cols_per_row]
        cols = st.columns(cols_per_row)
        for j, note in enumerate(row_notes):
            with cols[j]:
                nid = note["id"]
                title = note.get("title", "Untitled")
                content = note.get("content", "")

                st.markdown(
                    f'<div class="wp-note-card">'
                    f'<div class="wp-note-title">{title}</div>'
                    f'<div class="wp-note-content">{content[:200]}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                ec1, ec2 = st.columns(2)
                with ec1:
                    if st.button("✏️ Edit", key=f"nedit_{nid}"):
                        st.session_state[f"editing_note_{nid}"] = True
                        st.rerun()
                with ec2:
                    if st.button("🗑️ Delete", key=f"ndel_{nid}"):
                        api_call("DELETE", f"/notes/{nid}", username)
                        st.rerun()

                # ── Inline edit form ──────────────────────
                if st.session_state.get(f"editing_note_{nid}"):
                    new_title = st.text_input("Title", value=title, key=f"ntitle_{nid}")
                    new_content = st.text_area("Content", value=content, key=f"ncontent_{nid}", height=100)
                    ec1, ec2 = st.columns(2)
                    with ec1:
                        if st.button("Save", key=f"nsave_{nid}", type="primary"):
                            api_call("PUT", f"/notes/{nid}", username, {
                                "title": new_title.strip() or title,
                                "content": new_content,
                            })
                            del st.session_state[f"editing_note_{nid}"]
                            st.rerun()
                    with ec2:
                        if st.button("Cancel", key=f"ncancel_{nid}"):
                            del st.session_state[f"editing_note_{nid}"]
                            st.rerun()
