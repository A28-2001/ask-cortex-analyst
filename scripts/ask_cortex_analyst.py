import os
import sys
import time
import requests
from dotenv import load_dotenv
from jwt_auth import generate_jwt

load_dotenv()

# Credentials are read when a call is made, not at import, so the app still
# starts (and serves recorded answers) on a machine with no Snowflake account.
# Key content comes from SNOWFLAKE_PRIVATE_KEY (deployed) or
# SNOWFLAKE_PRIVATE_KEY_PATH (local dev); see snowflake_auth.load_private_key(),
# which generate_jwt() uses directly.


def _account_and_user():
    account, user = os.environ.get("SNOWFLAKE_ACCOUNT"), os.environ.get("SNOWFLAKE_USER")
    if not account or not user:
        # status None: treated like "no response", i.e. the service is unavailable.
        raise CortexAnalystError("SNOWFLAKE_ACCOUNT / SNOWFLAKE_USER are not set", 0.0, None)
    return account, user


SEMANTIC_MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "semantic_model", "nl_assistant.yaml")

_semantic_model_cache: str | None = None


class CortexAnalystError(Exception):
    """A failed call. `status` is the HTTP status, or None when the request
    never got a response (DNS, connection refused, timeout). Callers use it
    to tell "the service is unavailable" apart from "this question failed"."""

    def __init__(self, message: str, latency: float, status: int | None = None):
        super().__init__(message)
        self.latency = latency
        self.status = status


def get_semantic_model_yaml() -> str:
    """The semantic model never changes mid-run, so read it from disk once
    per process instead of on every single chat message."""
    global _semantic_model_cache
    if _semantic_model_cache is None:
        with open(SEMANTIC_MODEL_PATH, "r") as f:
            _semantic_model_cache = f.read()
    return _semantic_model_cache


def ask(question: str, history: list | None = None) -> tuple[dict, list, float]:
    """Send a question to Cortex Analyst, carrying prior turns as conversation history
    so follow-up questions ("now break that down by segment") resolve correctly.

    Returns (response_json, updated_history, latency_seconds). Raises CortexAnalystError
    on network failures or non-2xx responses instead of letting requests throw raw.
    """
    account, user = _account_and_user()
    try:
        token = generate_jwt(account, user)
    except Exception as e:  # missing or unreadable private key
        raise CortexAnalystError(f"Could not sign a JWT: {e}", 0.0, None) from e
    semantic_model_yaml = get_semantic_model_yaml()

    messages = (history or []) + [{"role": "user", "content": [{"type": "text", "text": question}]}]

    start = time.monotonic()
    try:
        resp = requests.post(
            f"https://{account.lower()}.snowflakecomputing.com/api/v2/cortex/analyst/message",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Snowflake-Authorization-Token-Type": "KEYPAIR_JWT",
                "Content-Type": "application/json",
            },
            json={"messages": messages, "semantic_model": semantic_model_yaml},
            timeout=60,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        latency = time.monotonic() - start
        response = getattr(e, "response", None)
        detail = response.text if response is not None else str(e)
        status = response.status_code if response is not None else None
        raise CortexAnalystError(detail, latency, status) from e

    latency = time.monotonic() - start
    try:
        result = resp.json()
        reply = result["message"]
    except (ValueError, KeyError, TypeError) as e:
        # A 2xx with a body we can't use is still a failed call, not a crash.
        raise CortexAnalystError(f"Unexpected response body: {resp.text[:300]}", latency, resp.status_code) from e
    updated_history = messages + [reply]
    return result, updated_history, latency


def print_result(question: str, result: dict, latency: float):
    print(f"\n{'='*80}\nQ: {question}   ({latency:.2f}s)\n{'-'*80}")
    for block in result.get("message", {}).get("content", []):
        if block["type"] == "text":
            print(f"ANSWER: {block['text']}")
        elif block["type"] == "sql":
            print(f"SQL:\n{block['statement']}")
        elif block["type"] == "suggestions":
            print(f"SUGGESTIONS: {block.get('suggestions')}")


if __name__ == "__main__":
    questions = sys.argv[1:] if len(sys.argv) > 1 else ["What was our total MRR in June 2026?"]
    history = None
    for q in questions:
        try:
            result, history, latency = ask(q, history)
        except CortexAnalystError as e:
            print(f"\n{'='*80}\nQ: {q}   (failed after {e.latency:.2f}s)\n{'-'*80}")
            print(f"ERROR: {e}")
            continue
        print_result(q, result, latency)
