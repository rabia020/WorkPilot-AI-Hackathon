"""
config.py
=========
WorkPilot AI — Centralized Configuration

Single source of truth for database, API, and service configuration.
All other modules import from here instead of defining their own constants.
"""

import os
from dotenv import load_dotenv

load_dotenv()


# ==========================================================
# DATABASE
# ==========================================================

PG_CONFIG = {
    "host":     os.getenv("PG_HOST", "127.0.0.1"),
    "port":     int(os.getenv("PG_PORT", 5432)),
    "dbname":   os.getenv("PG_DBNAME", "agent_memory"),
    "user":     os.getenv("PG_USER", "postgres"),
    "password": os.getenv("PG_PASSWORD", "postgres"),
}


def get_connection():
    """Create a new PostgreSQL connection using the centralized config."""
    import psycopg2
    return psycopg2.connect(**PG_CONFIG)


# ==========================================================
# CHROMADB
# ==========================================================

CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")


# ==========================================================
# API ENDPOINTS
# ==========================================================

FASTAPI_BASE = os.getenv("FASTAPI_BASE", "http://127.0.0.1:8000")
FASTAPI_PORT = int(os.getenv("FASTAPI_PORT", 8000))


# ==========================================================
# n8n WEBHOOKS
# ==========================================================

N8N_ACTION_URL = os.getenv(
    "N8N_ACTION_URL",
    "http://localhost:5678/webhook/copilot-actions"
)

N8N_AGENT_URL = os.getenv(
    "N8N_AGENT_URL",
    "http://localhost:5678/webhook/copilot"
)


# ==========================================================
# LLM
# ==========================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
GROQ_TEMPERATURE = float(os.getenv("GROQ_TEMPERATURE", "0.2"))

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest")


# ==========================================================
# RAG
# ==========================================================

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
RAG_COLLECTION = os.getenv("RAG_COLLECTION", "company_docs")
