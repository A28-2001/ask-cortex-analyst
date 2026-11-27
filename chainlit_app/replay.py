"""Recorded answers, served when the live warehouse is unavailable.

Built by scripts/build_replay_fixtures.py from the evaluation runs in eval/,
so every answer here is a real Cortex Analyst response with the rows Snowflake
actually returned at the time.

Lookups are exact after normalizing case, spacing and trailing punctuation.
There is deliberately no fuzzy matching. Serving the answer to a *different*
question than the one asked is precisely the failure this project measures,
so near misses are offered as suggestions the visitor can click, never as
answers.
"""

import json
import os
import re
from difflib import SequenceMatcher
from functools import lru_cache

PATH = os.path.join(os.path.dirname(__file__), "replay.json")


def normalize(question: str) -> str:
    """Lookup key: case, spacing and trailing punctuation don't matter."""
    q = (question or "").lower().strip()
    q = re.sub(r"[^\w\s$%.-]", "", q)
    q = re.sub(r"\s+", " ", q)
    return q.rstrip(" .?!")


@lru_cache(maxsize=1)
def _index():
    with open(PATH, encoding="utf-8") as f:
        entries = json.load(f)["entries"]
    return entries, {e["key"]: e for e in entries}


def entries():
    return _index()[0]


def lookup(question: str):
    """The recorded answer to exactly this question, or None."""
    return _index()[1].get(normalize(question))


def suggest(question: str, n: int = 3):
    """Recorded questions closest to what was asked, as clickable suggestions.

    Only ever offered as "here are questions I do have answers for", so a
    wrong guess costs a click rather than a misleading answer.
    """
    key = normalize(question)
    ranked = sorted(
        entries(),
        key=lambda e: SequenceMatcher(None, key, e["key"]).ratio(),
        reverse=True,
    )
    return [e["question"] for e in ranked[:n]]
