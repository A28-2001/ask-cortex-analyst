import os
import sys
import json
import requests
from dotenv import load_dotenv
from jwt_auth import generate_jwt

load_dotenv()

ACCOUNT = os.environ["SNOWFLAKE_ACCOUNT"]
USER = os.environ["SNOWFLAKE_USER"]
KEY_PATH = os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"]

HOST_ACCOUNT = ACCOUNT.lower()
BASE_URL = f"https://{HOST_ACCOUNT}.snowflakecomputing.com"

SEMANTIC_MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "semantic_model", "nl_assistant.yaml")


def ask(question: str) -> dict:
    token = generate_jwt(ACCOUNT, USER, KEY_PATH)
    with open(SEMANTIC_MODEL_PATH, "r") as f:
        semantic_model_yaml = f.read()

    resp = requests.post(
        f"{BASE_URL}/api/v2/cortex/analyst/message",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Snowflake-Authorization-Token-Type": "KEYPAIR_JWT",
            "Content-Type": "application/json",
        },
        json={
            "messages": [{"role": "user", "content": [{"type": "text", "text": question}]}],
            "semantic_model": semantic_model_yaml,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def print_result(question: str, result: dict):
    print(f"\n{'='*80}\nQ: {question}\n{'-'*80}")
    for block in result.get("message", {}).get("content", []):
        if block["type"] == "text":
            print(f"ANSWER: {block['text']}")
        elif block["type"] == "sql":
            print(f"SQL:\n{block['statement']}")
        elif block["type"] == "suggestions":
            print(f"SUGGESTIONS: {block.get('suggestions')}")


if __name__ == "__main__":
    question = sys.argv[1] if len(sys.argv) > 1 else "What was our total MRR in June 2026?"
    result = ask(question)
    print_result(question, result)
