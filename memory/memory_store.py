"""
memory/memory_store.py
======================
Persistent memory for the LangGraph + n8n multi-agent system.

Two stores:
    PostgreSQL  → structured state  (last query, email stats, session data)
    ChromaDB    → semantic memory   (past reports, email summaries, RAG context)

Two LangGraph nodes:
    memory_load_node  → called BEFORE supervisor (inject past memory into state)
    memory_save_node  → called AFTER  reporter   (persist what just happened)
"""

import json
import uuid
import os
from datetime import datetime
from typing import Any, Optional

import psycopg2
import psycopg2.extras
import chromadb
from dotenv import load_dotenv

from config import PG_CONFIG, CHROMA_PATH, get_connection

load_dotenv()


# ──────────────────────────────────────────────
# POSTGRESQL — structured state
# ──────────────────────────────────────────────

class PostgresMemory:
    """
    PostgreSQL memory storage.

    agent_state:
        Stores key/value memory for each user and session.

    action_log:
        Stores actions performed by agents and their results.
    """

    def __init__(self):

        self.conn = get_connection()

        self.conn.autocommit = True

        self._ensure_schema()

    # ==========================================================
    # CREATE / UPDATE DATABASE SCHEMA
    # ==========================================================

    def _ensure_schema(self):

        with self.conn.cursor() as cur:

            # --------------------------------------------------
            # AGENT STATE TABLE
            # --------------------------------------------------

            cur.execute("""
                CREATE TABLE IF NOT EXISTS agent_state (

                    id UUID PRIMARY KEY
                    DEFAULT gen_random_uuid(),

                    "user" TEXT
                    NOT NULL
                    DEFAULT 'default',

                    session_id TEXT
                    NOT NULL
                    DEFAULT 'default',

                    agent TEXT
                    NOT NULL
                    DEFAULT 'supervisor',

                    key TEXT
                    NOT NULL,

                    value JSONB,

                    updated_at TIMESTAMPTZ
                    DEFAULT NOW()

                );
            """)

            # --------------------------------------------------
            # ADD MISSING COLUMNS TO EXISTING TABLE
            # --------------------------------------------------

            cur.execute("""
                ALTER TABLE agent_state
                ADD COLUMN IF NOT EXISTS "user"
                TEXT DEFAULT 'default';
            """)

            cur.execute("""
                ALTER TABLE agent_state
                ADD COLUMN IF NOT EXISTS session_id
                TEXT DEFAULT 'default';
            """)

            cur.execute("""
                ALTER TABLE agent_state
                ADD COLUMN IF NOT EXISTS agent
                TEXT DEFAULT 'supervisor';
            """)

            cur.execute("""
                ALTER TABLE agent_state
                ADD COLUMN IF NOT EXISTS key
                TEXT;
            """)

            cur.execute("""
                ALTER TABLE agent_state
                ADD COLUMN IF NOT EXISTS value
                JSONB;
            """)

            cur.execute("""
                ALTER TABLE agent_state
                ADD COLUMN IF NOT EXISTS updated_at
                TIMESTAMPTZ DEFAULT NOW();
            """)

            # --------------------------------------------------
            # ACTION LOG TABLE
            # --------------------------------------------------

            cur.execute("""
                CREATE TABLE IF NOT EXISTS action_log (

                    id UUID PRIMARY KEY
                    DEFAULT gen_random_uuid(),

                    "user" TEXT
                    NOT NULL
                    DEFAULT 'default',

                    session_id TEXT
                    NOT NULL
                    DEFAULT 'default',

                    agent TEXT
                    NOT NULL
                    DEFAULT 'supervisor',

                    action_type TEXT
                    NOT NULL,

                    payload JSONB,

                    result JSONB,

                    status TEXT
                    DEFAULT 'success',

                    created_at TIMESTAMPTZ
                    DEFAULT NOW()

                );
            """)

            # --------------------------------------------------
            # ADD MISSING COLUMNS TO EXISTING TABLE
            # --------------------------------------------------

            cur.execute("""
                ALTER TABLE action_log
                ADD COLUMN IF NOT EXISTS "user"
                TEXT DEFAULT 'default';
            """)

            cur.execute("""
                ALTER TABLE action_log
                ADD COLUMN IF NOT EXISTS session_id
                TEXT DEFAULT 'default';
            """)

            cur.execute("""
                ALTER TABLE action_log
                ADD COLUMN IF NOT EXISTS agent
                TEXT DEFAULT 'supervisor';
            """)

            cur.execute("""
                ALTER TABLE action_log
                ADD COLUMN IF NOT EXISTS action_type
                TEXT;
            """)

            cur.execute("""
                ALTER TABLE action_log
                ADD COLUMN IF NOT EXISTS payload
                JSONB;
            """)

            cur.execute("""
                ALTER TABLE action_log
                ADD COLUMN IF NOT EXISTS result
                JSONB;
            """)

            cur.execute("""
                ALTER TABLE action_log
                ADD COLUMN IF NOT EXISTS status
                TEXT DEFAULT 'success';
            """)

            cur.execute("""
                ALTER TABLE action_log
                ADD COLUMN IF NOT EXISTS created_at
                TIMESTAMPTZ DEFAULT NOW();
            """)

            # --------------------------------------------------
            # INDEXES
            # --------------------------------------------------

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_state_lookup
                ON agent_state
                ("user", session_id, agent);
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_action_log_user
                ON action_log
                ("user", session_id);
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_action_log_type
                ON action_log
                (action_type, status);
            """)

            # --------------------------------------------------
            # TASKS TABLE
            # --------------------------------------------------

            cur.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id          UUID PRIMARY KEY
                    DEFAULT gen_random_uuid(),

                    "user"      TEXT
                    NOT NULL
                    DEFAULT 'default',

                    title       TEXT
                    NOT NULL,

                    description TEXT
                    DEFAULT '',

                    due_date    DATE,

                    priority    TEXT
                    DEFAULT 'Medium',

                    completed   BOOLEAN
                    DEFAULT FALSE,

                    created_at  TIMESTAMPTZ
                    DEFAULT NOW(),

                    updated_at  TIMESTAMPTZ
                    DEFAULT NOW()
                );
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_user
                ON tasks ("user", completed);
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_due
                ON tasks (due_date);
            """)

            # --------------------------------------------------
            # NOTES TABLE
            # --------------------------------------------------

            cur.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    id          UUID PRIMARY KEY
                    DEFAULT gen_random_uuid(),

                    "user"      TEXT
                    NOT NULL
                    DEFAULT 'default',

                    title       TEXT
                    NOT NULL,

                    content     TEXT
                    DEFAULT '',

                    created_at  TIMESTAMPTZ
                    DEFAULT NOW(),

                    updated_at  TIMESTAMPTZ
                    DEFAULT NOW()
                );
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_notes_user
                ON notes ("user");
            """)

            print(
                "[PostgresMemory] Database schema ready"
            )

    # ==========================================================
    # SAVE MEMORY
    # ==========================================================

    def save(
        self,
        key: str,
        value: Any,
        user: str = "default",
        session_id: str = "default",
        agent: str = "supervisor"
    ):

        with self.conn.cursor() as cur:

            cur.execute(
                """
                SELECT id
                FROM agent_state
                WHERE
                    "user" = %s
                    AND session_id = %s
                    AND agent = %s
                    AND key = %s
                LIMIT 1;
                """,
                (
                    user,
                    session_id,
                    agent,
                    key
                )
            )

            existing = cur.fetchone()

            if existing:

                cur.execute(
                    """
                    UPDATE agent_state

                    SET
                        value = %s,
                        updated_at = NOW()

                    WHERE id = %s;
                    """,
                    (
                        json.dumps(value),
                        existing[0]
                    )
                )

            else:

                cur.execute(
                    """
                    INSERT INTO agent_state
                    (
                        "user",
                        session_id,
                        agent,
                        key,
                        value,
                        updated_at
                    )

                    VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        NOW()
                    );
                    """,
                    (
                        user,
                        session_id,
                        agent,
                        key,
                        json.dumps(value)
                    )
                )

    # ==========================================================
    # LOAD ONE VALUE
    # ==========================================================

    def load(
        self,
        key: str,
        user: str = "default",
        session_id: str = "default",
        agent: str = "supervisor"
    ) -> Any:

        with self.conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            cur.execute(
                """
                SELECT value
                FROM agent_state

                WHERE
                    "user" = %s
                    AND session_id = %s
                    AND agent = %s
                    AND key = %s

                LIMIT 1;
                """,
                (
                    user,
                    session_id,
                    agent,
                    key
                )
            )

            row = cur.fetchone()

        return row["value"] if row else None

    # ==========================================================
    # LOAD ALL VALUES
    # ==========================================================

    def load_all(
        self,
        user: str = "default",
        session_id: str = "default",
        agent: str = "supervisor"
    ) -> dict:

        with self.conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            cur.execute(
                """
                SELECT key, value
                FROM agent_state

                WHERE
                    "user" = %s
                    AND session_id = %s
                    AND agent = %s;
                """,
                (
                    user,
                    session_id,
                    agent
                )
            )

            rows = cur.fetchall()

        return {
            row["key"]: row["value"]
            for row in rows
        }

    # ==========================================================
    # LOG AGENT ACTION
    # ==========================================================

    def log_action(
        self,
        action_type: str,
        payload: dict,
        result: dict,
        status: str = "success",
        user: str = "default",
        session_id: str = "default",
        agent: str = "supervisor"
    ):

        with self.conn.cursor() as cur:

            cur.execute(
                """
                INSERT INTO action_log
                (
                    "user",
                    session_id,
                    agent,
                    action_type,
                    payload,
                    result,
                    status
                )

                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                );
                """,
                (
                    user,
                    session_id,
                    agent,
                    action_type,
                    json.dumps(payload),
                    json.dumps(result),
                    status
                )
            )

    # ==========================================================
    # CLOSE CONNECTION
    # ==========================================================

    def close(self):

        if self.conn:

            self.conn.close()

    # ==========================================================
    # TASKS CRUD
    # ==========================================================

    def create_task(
        self,
        user: str,
        title: str,
        description: str = "",
        due_date: str = None,
        priority: str = "Medium"
    ) -> dict:

        with self.conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            cur.execute(
                """
                INSERT INTO tasks
                ("user", title, description, due_date, priority)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *;
                """,
                (user, title, description, due_date, priority)
            )

            row = cur.fetchone()

            return dict(row) if row else {}

    def get_tasks(
        self,
        user: str,
        completed_only: bool = None
    ) -> list:

        with self.conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            if completed_only is None:

                cur.execute(
                    """
                    SELECT * FROM tasks
                    WHERE "user" = %s
                    ORDER BY
                        completed ASC,
                        CASE priority
                            WHEN 'High' THEN 1
                            WHEN 'Medium' THEN 2
                            WHEN 'Low' THEN 3
                            ELSE 4
                        END,
                        due_date ASC NULLS LAST;
                    """,
                    (user,)
                )

            else:

                cur.execute(
                    """
                    SELECT * FROM tasks
                    WHERE "user" = %s AND completed = %s
                    ORDER BY
                        CASE priority
                            WHEN 'High' THEN 1
                            WHEN 'Medium' THEN 2
                            WHEN 'Low' THEN 3
                            ELSE 4
                        END,
                        due_date ASC NULLS LAST;
                    """,
                    (user, completed_only)
                )

            rows = cur.fetchall()

            return [dict(r) for r in rows]

    def update_task(
        self,
        task_id: str,
        user: str,
        **kwargs
    ) -> dict:

        allowed = {
            "title", "description",
            "due_date", "priority", "completed"
        }

        updates = {
            k: v for k, v in kwargs.items()
            if k in allowed and v is not None
        }

        if not updates:
            return {}

        updates["updated_at"] = "NOW()"

        set_clause = ", ".join(
            f'"{k}" = {v}' if v == "NOW()"
            else f'"{k}" = %s'
            for k, v in updates.items()
        )

        values = [
            v for v in updates.values()
            if v != "NOW()"
        ]

        values.extend([task_id, user])

        with self.conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            cur.execute(
                f"""
                UPDATE tasks
                SET {set_clause}
                WHERE id = %s AND "user" = %s
                RETURNING *;
                """,
                tuple(values)
            )

            row = cur.fetchone()

            return dict(row) if row else {}

    def delete_task(
        self,
        task_id: str,
        user: str
    ) -> bool:

        with self.conn.cursor() as cur:

            cur.execute(
                """
                DELETE FROM tasks
                WHERE id = %s AND "user" = %s;
                """,
                (task_id, user)
            )

            return cur.rowcount > 0

    def toggle_task(
        self,
        task_id: str,
        user: str
    ) -> dict:

        with self.conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            cur.execute(
                """
                UPDATE tasks
                SET completed = NOT completed,
                    updated_at = NOW()
                WHERE id = %s AND "user" = %s
                RETURNING *;
                """,
                (task_id, user)
            )

            row = cur.fetchone()

            return dict(row) if row else {}

    def get_task_stats(self, user: str) -> dict:

        with self.conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE completed) AS completed,
                    COUNT(*) FILTER (WHERE NOT completed) AS pending
                FROM tasks
                WHERE "user" = %s;
                """,
                (user,)
            )

            row = cur.fetchone()

            return {
                "total": row[0] if row else 0,
                "completed": row[1] if row else 0,
                "pending": row[2] if row else 0,
            }

    # ==========================================================
    # NOTES CRUD
    # ==========================================================

    def create_note(
        self,
        user: str,
        title: str,
        content: str = ""
    ) -> dict:

        with self.conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            cur.execute(
                """
                INSERT INTO notes
                ("user", title, content)
                VALUES (%s, %s, %s)
                RETURNING *;
                """,
                (user, title, content)
            )

            row = cur.fetchone()

            return dict(row) if row else {}

    def get_notes(self, user: str) -> list:

        with self.conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            cur.execute(
                """
                SELECT * FROM notes
                WHERE "user" = %s
                ORDER BY updated_at DESC;
                """,
                (user,)
            )

            rows = cur.fetchall()

            return [dict(r) for r in rows]

    def update_note(
        self,
        note_id: str,
        user: str,
        **kwargs
    ) -> dict:

        allowed = {"title", "content"}

        updates = {
            k: v for k, v in kwargs.items()
            if k in allowed and v is not None
        }

        if not updates:
            return {}

        updates["updated_at"] = "NOW()"

        set_clause = ", ".join(
            f'"{k}" = {v}' if v == "NOW()"
            else f'"{k}" = %s'
            for k, v in updates.items()
        )

        values = [
            v for v in updates.values()
            if v != "NOW()"
        ]

        values.extend([note_id, user])

        with self.conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            cur.execute(
                f"""
                UPDATE notes
                SET {set_clause}
                WHERE id = %s AND "user" = %s
                RETURNING *;
                """,
                tuple(values)
            )

            row = cur.fetchone()

            return dict(row) if row else {}

    def delete_note(
        self,
        note_id: str,
        user: str
    ) -> bool:

        with self.conn.cursor() as cur:

            cur.execute(
                """
                DELETE FROM notes
                WHERE id = %s AND "user" = %s;
                """,
                (note_id, user)
            )

            return cur.rowcount > 0

# ──────────────────────────────────────────────
# CHROMADB  — semantic memory
# ──────────────────────────────────────────────
class ChromaMemory:
    """
    Collections:
        reports         — past reporter outputs, searchable by meaning
        email_summaries — structured email data per session
        rag_context     — RAG context chunks used in past answers
    """

    COLLECTIONS = ["reports", "email_summaries", "rag_context"]

    def __init__(self):
        self.client = chromadb.PersistentClient(path=CHROMA_PATH)
        self.cols = {
            name: self.client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )
            for name in self.COLLECTIONS
        }

    def save(self, collection: str, text: str,
             user: str = "default", metadata: Optional[dict] = None) -> str:
        doc_id = str(uuid.uuid4())
        meta = {
            "user":      user,
            "timestamp": datetime.utcnow().isoformat(),
            **(metadata or {}),
        }
        self.cols[collection].add(
            ids=[doc_id],
            documents=[text],
            metadatas=[meta],
        )
        return doc_id

    def search(self, collection: str, query: str,
               user: Optional[str] = None, n: int = 3) -> list[dict]:
        where = {"user": user} if user else None
        try:
            results = self.cols[collection].query(
                query_texts=[query],
                n_results=n,
                where=where,
            )
        except Exception:
            return []

        return [
            {
                "content":  results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "score":    round(1 - results["distances"][0][i], 3),
            }
            for i in range(len(results["documents"][0]))
        ]


# ──────────────────────────────────────────────
# MEMORY STORE  — main interface
# ──────────────────────────────────────────────
class MemoryStore:
    """
    Single memory interface used by all agents.

    Two LangGraph nodes:
        memory_load_node(state) → called at graph START
        memory_save_node(state) → called at graph END (after human review)
    """

    def __init__(self):
        self.pg     = PostgresMemory()
        self.chroma = ChromaMemory()
        print("[MemoryStore] Ready -- PostgreSQL + ChromaDB connected")

    # ══════════════════════════════
    # GRAPH NODE: load (START)
    # ══════════════════════════════
    def memory_load_node(self, state: dict) -> dict:
        """
        Injected at START of graph (before supervisor).
        Loads past session context so supervisor has history.
        """
        user       = state.get("user", "default")
        session_id = state.get("session_id", "default")

        # Load all keys for this user/session under supervisor agent
        past = self.pg.load_all(user=user, session_id=session_id, agent="supervisor")

        # Semantic: find past reports relevant to this query
        similar_reports = []
        if state.get("query"):
            similar_reports = self.chroma.search(
                "reports", state["query"], user=user, n=2
            )

        memory_context = {
            "last_query":       past.get("last_query"),
            "last_query_type":  past.get("last_query_type"),
            "last_report_type": past.get("last_report_type"),
            "total_runs":       past.get("total_runs", 0),
            "email_count":      past.get("email_count", 0),
            "similar_reports":  similar_reports,
        }

        print(f"[Memory] Loaded context for user={user!r} — "
              f"total_runs={memory_context['total_runs']}")

        return {"memory_context": memory_context}

    # ══════════════════════════════
    # GRAPH NODE: save (END)
    # ══════════════════════════════
    def memory_save_node(self, state: dict) -> dict:
        """
        Persist every run to PostgreSQL + ChromaDB.

        Runs on all terminal paths, not just approved ones: `approved`
        is tri-state (None = no side effect to approve, True = approved,
        False = rejected). Gating persistence on approval used to drop
        every read-only run and every rejection.
        """
        user       = state.get("user", "default")
        session_id = state.get("session_id", "default")
        query      = state.get("query", "")
        emails     = state.get("emails", [])
        context    = state.get("context", "")
        report     = state.get("report", "")
        query_type = state.get("query_type") or self._infer_query_type(state)
        approved   = state.get("approved", None)

        review_happened = approved is not None

        # ── PostgreSQL: structured state ──────────────────────────────────────
        total_runs  = (self.pg.load("total_runs",  user, session_id, agent="supervisor") or 0) + 1
        email_count = (self.pg.load("email_count", user, session_id, agent="supervisor") or 0) + len(emails)

        self.pg.save("last_query",       query,      user, session_id, agent="supervisor")
        self.pg.save("last_query_type",  query_type, user, session_id, agent="supervisor")
        self.pg.save("last_report_type", query_type, user, session_id, agent="supervisor")
        self.pg.save("total_runs",       total_runs, user, session_id, agent="supervisor")
        self.pg.save("email_count",      email_count, user, session_id, agent="supervisor")
        self.pg.save("last_run_at",
                     datetime.utcnow().isoformat(), user, session_id, agent="supervisor")
        self.pg.save("last_approved",
                     approved, user, session_id, agent="supervisor")

        # Email severity stats
        if emails:
            severity_counts = {}
            for e in emails:
                sev = e.get("severity", "medium")
                severity_counts[sev] = severity_counts.get(sev, 0) + 1

            self.pg.save("last_email_severity_stats",
                         severity_counts, user, session_id, agent="email_agent")

            self.pg.log_action(
                action_type="email_fetch",
                payload={"label": "complaints", "days": 30},
                result={"count": len(emails), "severity_stats": severity_counts},
                status="success",
                user=user, session_id=session_id, agent="email_agent",
            )

        # Log the approval decision — only when there was one to log.
        if review_happened:
            self.pg.log_action(
                action_type="human_review",
                payload={"query": query},
                result={"approved": approved,
                        "comment": state.get("approval_comment", "")},
                status="success" if approved else "rejected",
                user=user, session_id=session_id, agent="supervisor",
            )

        # Log what the external actions actually did. Without this the
        # audit trail recorded approvals but never any execution.
        for outcome in state.get("execution_results", []) or []:
            self.pg.log_action(
                action_type="execution",
                payload={"query": query, "action": outcome.get("action", "")},
                result={"detail": outcome.get("detail", "")},
                status="success" if outcome.get("success") else "error",
                user=user, session_id=session_id, agent="supervisor",
            )

        # ── ChromaDB: semantic memory ─────────────────────────────────────────
        if report:
            self.chroma.save(
                "reports", report, user,
                metadata={
                    "query":       query,
                    "query_type":  query_type,
                    "session_id":  session_id,
                    "email_count": str(len(emails)),
                    "approved":    str(approved),
                },
            )

        if emails:
            email_text = "\n".join([
                f"{e.get('sender')}: {e.get('summary')} "
                f"[{e.get('category')} | {e.get('severity')}]"
                for e in emails
            ])
            self.chroma.save(
                "email_summaries", email_text, user,
                metadata={
                    "query":      query,
                    "session_id": session_id,
                    "count":      str(len(emails)),
                },
            )

        if context and context != "No relevant documents found.":
            self.chroma.save(
                "rag_context", context, user,
                metadata={"query": query, "session_id": session_id},
            )

        print(f"[Memory] Saved run #{total_runs} — "
              f"emails={len(emails)}  report={bool(report)}  "
              f"approved={approved}  user={user!r}")

        update = {
            "messages": [f"[Memory] Run #{total_runs} saved to PostgreSQL + ChromaDB"],
            "execution_results": state.get("execution_results", []),
        }

        if state.get("email_send_result") is not None:
            update["email_send_result"] = state["email_send_result"]

        return update

    # ══════════════════════════════
    # DIRECT ACCESS (optional)
    # Called by individual agents mid-run
    # ══════════════════════════════
    def save_memory(self, key: str, value: Any,
                    user: str = "default", session_id: str = "default",
                    agent: str = "supervisor"):
        self.pg.save(key, value, user, session_id, agent=agent)

    def load_memory(self, key: str,
                    user: str = "default", session_id: str = "default",
                    agent: str = "supervisor") -> Any:
        return self.pg.load(key, user, session_id, agent=agent)

    def search_past_reports(self, query: str,
                             user: str = "default", n: int = 3) -> list[dict]:
        return self.chroma.search("reports", query, user=user, n=n)

    def search_past_emails(self, query: str,
                            user: str = "default", n: int = 3) -> list[dict]:
        return self.chroma.search("email_summaries", query, user=user, n=n)

    # ══════════════════════════════
    # HELPERS
    # ══════════════════════════════
    def _infer_query_type(self, state: dict) -> str:
        """Fallback — infer query type from state if supervisor didn't set it."""
        if state.get("query_type"):
            return state["query_type"]
        if state.get("emails"):
            return "complaint"
        if state.get("context") and state["context"] != "No relevant documents found.":
            return "document"
        return "research"

    def close(self):
        self.pg.close()


# ──────────────────────────────────────────────
# SINGLETON
# ──────────────────────────────────────────────
_memory_store: Optional[MemoryStore] = None

def get_memory_store() -> MemoryStore:
    global _memory_store
    if _memory_store is None:
        _memory_store = MemoryStore()
    return _memory_store