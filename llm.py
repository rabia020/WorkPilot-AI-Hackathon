"""
llm.py
======
Generate answers for RAG queries using Groq (primary) with Mistral fallback.
Groq has a generous free tier; Mistral free tier is very rate-limited.
"""

import time
import requests
from config import GROQ_API_KEY, GROQ_MODEL, MISTRAL_API_KEY, MISTRAL_MODEL


# ------------------------------------------------------------------
# Prompt template
# ------------------------------------------------------------------
_SYSTEM_PROMPT = """\
You are an Enterprise AI Assistant.

Use ONLY the information provided in the context below.
If the context contains partial information, summarize what is available.
Do NOT invent information.
If the context does not contain the answer, reply:
"I couldn't find this information in the company knowledge base."
"""


def _build_prompt(question: str, context: str) -> str:
    return (
        f"{_SYSTEM_PROMPT}\n\n"
        f"--- Context ---\n{context}\n\n"
        f"--- Question ---\n{question}\n\n"
        f"Answer:"
    )


# ------------------------------------------------------------------
# Groq provider (primary - generous free tier)
# ------------------------------------------------------------------
def _call_groq(prompt, max_retries=2):
    """Call Groq's OpenAI-compatible API. Returns answer or None on failure."""
    if not GROQ_API_KEY:
        return None

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]

            # Retry on 429 / 5xx
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                delay = 2 * (2 ** (attempt - 1))
                print(f"[llm] Groq {resp.status_code}, retrying in {delay}s "
                      f"(attempt {attempt}/{max_retries})")
                time.sleep(delay)
                continue

            print(f"[llm] Groq returned {resp.status_code}: {resp.text[:200]}")
            return None

        except Exception as e:
            print(f"[llm] Groq error: {e}")
            return None

    return None


# ------------------------------------------------------------------
# Mistral provider (fallback - free tier is very rate-limited)
# ------------------------------------------------------------------
def _call_mistral(prompt, max_retries=2):
    """Call Mistral API. Returns answer or None on failure."""
    if not MISTRAL_API_KEY:
        return None

    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MISTRAL_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=120)
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]

            if resp.status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                delay = 2 * (2 ** (attempt - 1))
                print(f"[llm] Mistral {resp.status_code}, retrying in {delay}s "
                      f"(attempt {attempt}/{max_retries})")
                time.sleep(delay)
                continue

            print(f"[llm] Mistral returned {resp.status_code}: {resp.text[:200]}")
            return None

        except Exception as e:
            print(f"[llm] Mistral error: {e}")
            return None

    return None


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------
def generate_answer(question, context):
    """
    Generate an answer using Groq (primary) with Mistral fallback.
    Raises RuntimeError only if both providers fail.
    """
    prompt = _build_prompt(question, context)

    # 1) Try Groq first
    answer = _call_groq(prompt)
    if answer:
        print("[llm] Answer generated via Groq")
        return answer

    # 2) Fall back to Mistral
    print("[llm] Groq unavailable, falling back to Mistral")
    answer = _call_mistral(prompt)
    if answer:
        print("[llm] Answer generated via Mistral")
        return answer

    # 3) Both failed
    missing = []
    if not GROQ_API_KEY:
        missing.append("GROQ_API_KEY")
    if not MISTRAL_API_KEY:
        missing.append("MISTRAL_API_KEY")

    if missing:
        raise RuntimeError(
            f"AI API keys not configured: {', '.join(missing)} are missing. "
            "Add them to your .env file:\n"
            "  GROQ_API_KEY=your_key_here\n"
            "  MISTRAL_API_KEY=your_key_here\n\n"
            "Get a free Groq key (recommended): https://console.groq.com"
        )
    else:
        raise RuntimeError(
            "Could not reach any AI provider (both Groq and Mistral failed). "
            "Check your API keys and network connection."
        )
