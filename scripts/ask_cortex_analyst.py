import os
import sys
import time
import requests
from dotenv import load_dotenv
from jwt_auth import generate_jwt

load_dotenv()

ACCOUNT = os.environ["SNOWFLAKE_ACCOUNT"]
USER = os.environ["SNOWFLAKE_USER"]
# Key content comes from SNOWFLAKE_PRIVATE_KEY (deployed) or SNOWFLAKE_PRIVATE_KEY_PATH
# (local dev) -- see snowflake_auth.load_private_key(), which generate_jwt() uses directly.

HOST_ACCOUNT = ACCOUNT.lower()
BASE_URL = f"https://{HOST_ACCOUNT}.snowflakecomputing.com"

SEMANTIC_MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "semantic_model", "nl_assistant.yaml")


class CortexAnalystError(Exception):
    def __init__(self, message: str, latency: float):
        super().__init__(message)
        self.latency = latency


def ask(question: str, history: list | None = None) -> tuple[dict, list, float]:
    """Send a question to Cortex Analyst, carrying prior turns as conversation history
    so follow-up questions ("now break that down by segment") resolve correctly.

    Returns (response_json, updated_history, latency_seconds). Raises CortexAnalystError
    on network failures or non-2xx responses instead of letting requests throw raw.
    """
    token = generate_jwt(ACCOUNT, USER)
    with open(SEMANTIC_MODEL_PATH, "r") as f:
        semantic_model_yaml = f.read()

    messages = (history or []) + [{"role": "user", "content": [{"type": "text", "text": question}]}]

    start = time.time()
    try:
        resp = requests.post(
            f"{BASE_URL}/api/v2/cortex/analyst/message",
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
        latency = time.time() - start
        detail = e.response.text if getattr(e, "response", None) is not None else str(e)
        raise CortexAnalystError(detail, latency) from e

    latency = time.time() - start
    result = resp.json()
    updated_history = messages + [result["message"]]
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
