import streamlit as st
from datetime import datetime

from config import get_connection, DEMO_MODE


# ==========================================================
# DEMO USER STORAGE
# ==========================================================

def _init_demo_users():

    if "demo_users" not in st.session_state:

        users = []

        # Load the initial demo users from Streamlit Secrets
        demo_users = st.secrets.get("demo_users", {})

        for username, config in demo_users.items():

            users.append({
                "id": config.get("id", username),
                "full_name": config.get(
                    "full_name",
                    username.title()
                ),
                "username": username,
                "email": config.get("email", ""),
                "role": config.get("role", "employee"),
                "active": True,
                "created_at": datetime.now(),
                "last_login": None,
                "created_by": "System",
                "password": config.get("password", ""),
            })

        st.session_state["demo_users"] = users


def _demo_users():
    _init_demo_users()
    return st.session_state["demo_users"]


# ==========================================================
# LOGIN
# ==========================================================

def login(username, password):

    # ------------------------------------------------------
    # STREAMLIT CLOUD / DEMO LOGIN
    # ------------------------------------------------------
    if DEMO_MODE:

        users = _demo_users()

        for user in users:

            if (
                user["username"] == username
                and user["password"] == password
            ):

                if not user["active"]:
                    return None

                user["last_login"] = datetime.now()

                return {
                    "id": user["id"],
                    "username": user["username"],
                    "full_name": user["full_name"],
                    "email": user["email"],
                    "role": user["role"],
                    "active": user["active"],
                }

        return None

    # ------------------------------------------------------
    # ORIGINAL POSTGRESQL LOGIN
    # ------------------------------------------------------

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            username,
            full_name,
            email,
            role,
            active
        FROM users
        WHERE username=%s
        AND password=%s
        AND active=TRUE
    """, (username, password))

    row = cur.fetchone()

    if row:

        cur.execute("""
            UPDATE users
            SET last_login=CURRENT_TIMESTAMP
            WHERE username=%s
        """, (username,))

        conn.commit()

        user = {
            "id": row[0],
            "username": row[1],
            "full_name": row[2],
            "email": row[3],
            "role": row[4],
            "active": row[5]
        }

    else:
        user = None

    cur.close()
    conn.close()

    return user


# ==========================================================
# CREATE USER
# ==========================================================

def create_user(
        full_name,
        email,
        username,
        password,
        created_by,
        role="employee"
):

    # ------------------------------------------------------
    # DEMO MODE
    # ------------------------------------------------------

    if DEMO_MODE:

        users = _demo_users()

        if any(
            u["username"].lower() == username.lower()
            for u in users
        ):
            return False, "Username already exists."

        if any(
            u["email"].lower() == email.lower()
            for u in users
        ):
            return False, "Email already exists."

        users.append({
            "id": f"demo-{len(users) + 1}",
            "full_name": full_name,
            "email": email,
            "username": username,
            "password": password,
            "role": role,
            "active": True,
            "created_at": datetime.now(),
            "last_login": None,
            "created_by": created_by,
        })

        return True, "Demo user created successfully."

    # ------------------------------------------------------
    # ORIGINAL POSTGRESQL
    # ------------------------------------------------------

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT id FROM users WHERE username=%s",
        (username,)
    )

    if cur.fetchone():

        cur.close()
        conn.close()

        return False, "Username already exists."

    cur.execute(
        "SELECT id FROM users WHERE email=%s",
        (email,)
    )

    if cur.fetchone():

        cur.close()
        conn.close()

        return False, "Email already exists."

    cur.execute("""
        INSERT INTO users
        (
            full_name,
            email,
            username,
            password,
            role,
            active,
            created_by
        )
        VALUES
        (
            %s,%s,%s,%s,%s,TRUE,%s
        )
    """, (
        full_name,
        email,
        username,
        password,
        role,
        created_by
    ))

    conn.commit()

    cur.close()
    conn.close()

    return True, "User created successfully."


# ==========================================================
# GET USER
# ==========================================================

def get_user(username):

    # ------------------------------------------------------
    # DEMO MODE
    # ------------------------------------------------------

    if DEMO_MODE:

        for user in _demo_users():

            if user["username"] == username:

                return {
                    "id": user["id"],
                    "username": user["username"],
                    "full_name": user["full_name"],
                    "email": user["email"],
                    "role": user["role"],
                    "active": user["active"],
                    "created_at": user["created_at"],
                    "last_login": user["last_login"],
                    "created_by": user["created_by"],
                }

        return None

    # ------------------------------------------------------
    # ORIGINAL POSTGRESQL
    # ------------------------------------------------------

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            username,
            full_name,
            email,
            role,
            active,
            created_at,
            last_login,
            created_by
        FROM users
        WHERE username=%s
    """, (username,))

    row = cur.fetchone()

    cur.close()
    conn.close()

    if row is None:
        return None

    return {
        "id": row[0],
        "username": row[1],
        "full_name": row[2],
        "email": row[3],
        "role": row[4],
        "active": row[5],
        "created_at": row[6],
        "last_login": row[7],
        "created_by": row[8]
    }


# ==========================================================
# GET ALL USERS
# ==========================================================

def get_all_users():

    # ------------------------------------------------------
    # DEMO MODE
    # ------------------------------------------------------

    if DEMO_MODE:

        users = _demo_users()

        return [
            (
                user["id"],
                user["full_name"],
                user["username"],
                user["email"],
                user["role"],
                user["active"],
                user["created_at"],
                user["last_login"],
                user["created_by"],
            )
            for user in users
        ]

    # ------------------------------------------------------
    # ORIGINAL POSTGRESQL
    # ------------------------------------------------------

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            full_name,
            username,
            email,
            role,
            active,
            created_at,
            last_login,
            created_by
        FROM users
        ORDER BY id
    """)

    users = cur.fetchall()

    cur.close()
    conn.close()

    return users


# ==========================================================
# CHANGE PASSWORD
# ==========================================================

def change_password(username, new_password):

    # ------------------------------------------------------
    # DEMO MODE
    # ------------------------------------------------------

    if DEMO_MODE:

        for user in _demo_users():

            if user["username"] == username:

                user["password"] = new_password
                return True

        return False

    # ------------------------------------------------------
    # ORIGINAL POSTGRESQL
    # ------------------------------------------------------

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET password=%s
        WHERE username=%s
    """, (
        new_password,
        username
    ))

    conn.commit()

    cur.close()
    conn.close()

    return True


# ==========================================================
# ACTIVATE USER
# ==========================================================

def activate_user(username):

    if DEMO_MODE:

        for user in _demo_users():

            if user["username"] == username:
                user["active"] = True
                return True

        return False

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET active=TRUE
        WHERE username=%s
    """, (username,))

    conn.commit()

    cur.close()
    conn.close()

    return True


# ==========================================================
# DEACTIVATE USER
# ==========================================================

def deactivate_user(username):

    if DEMO_MODE:

        for user in _demo_users():

            if user["username"] == username:
                user["active"] = False
                return True

        return False

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET active=FALSE
        WHERE username=%s
    """, (username,))

    conn.commit()

    cur.close()
    conn.close()

    return True


# ==========================================================
# DELETE USER
# ==========================================================

def delete_user(username):

    if DEMO_MODE:

        users = _demo_users()

        original_length = len(users)

        st.session_state["demo_users"] = [
            user
            for user in users
            if user["username"] != username
        ]

        return len(st.session_state["demo_users"]) < original_length

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM users
        WHERE username=%s
    """, (username,))

    conn.commit()

    cur.close()
    conn.close()

    return True


# ==========================================================
# USER EXISTS
# ==========================================================

def user_exists(username):

    if DEMO_MODE:

        return any(
            user["username"].lower() == username.lower()
            for user in _demo_users()
        )

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT id FROM users WHERE username=%s",
        (username,)
    )

    exists = cur.fetchone() is not None

    cur.close()
    conn.close()

    return exists


# ==========================================================
# EMAIL EXISTS
# ==========================================================

def email_exists(email):

    if DEMO_MODE:

        return any(
            user["email"].lower() == email.lower()
            for user in _demo_users()
        )

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT id FROM users WHERE email=%s",
        (email,)
    )

    exists = cur.fetchone() is not None

    cur.close()
    conn.close()

    return exists