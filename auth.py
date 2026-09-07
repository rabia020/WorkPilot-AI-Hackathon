from config import get_connection


# ==========================================================
# LOGIN
# ==========================================================
def login(username, password):

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

    conn = get_connection()
    cur = conn.cursor()

    # Check username
    cur.execute(
        "SELECT id FROM users WHERE username=%s",
        (username,)
    )

    if cur.fetchone():

        cur.close()
        conn.close()

        return False, "Username already exists."

    # Check email
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