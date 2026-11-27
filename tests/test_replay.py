"""Tests for the recorded-answer fallback (chainlit_app/replay.py).

The important properties are honesty properties: a lookup must never return
the answer to a different question, every recorded table must be labelled
with the right columns, and every starter on the home screen must have a
real recorded answer so the demo never dead-ends when the warehouse is off.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from chainlit_app import replay  # noqa: E402
from chainlit_app.starters import STARTER_GROUPS, all_messages  # noqa: E402


def test_fixture_loads_with_both_kinds_of_answer():
    kinds = {e["kind"] for e in replay.entries()}
    assert kinds == {"data", "refusal"}
    assert len(replay.entries()) >= 40


def test_every_entry_has_what_the_ui_needs():
    for e in replay.entries():
        assert e["question"].strip(), e["id"]
        assert e["recorded"] and e["origin"], e["id"]
        if e["kind"] == "data":
            assert e["sql"].lstrip().upper().startswith(("SELECT", "WITH")), e["id"]


def test_recorded_tables_are_labelled_with_the_right_number_of_columns():
    # Column names were recovered by parsing SQL; a mismatch would mean
    # values shown under the wrong headers.
    for e in replay.entries():
        if e["kind"] == "data":
            for row in e["rows"]:
                assert len(row) == len(e["columns"]), e["id"]


def test_keys_are_unique():
    keys = [e["key"] for e in replay.entries()]
    assert len(keys) == len(set(keys))


@pytest.mark.parametrize(
    "asked",
    [
        "What was our total MRR in March 2025?",
        "what was our total mrr in march 2025",
        "  What was our TOTAL MRR in March 2025 ?? ",
    ],
)
def test_lookup_ignores_case_spacing_and_trailing_punctuation(asked):
    hit = replay.lookup(asked)
    assert hit is not None and hit["id"] == "pit_1"


@pytest.mark.parametrize(
    "paraphrase",
    [
        "What was our MRR in March 2025?",          # dropped "total"
        "What was our total MRR in March 2026?",    # different year
        "What was our total MRR in April 2025?",    # different month
    ],
)
def test_lookup_never_answers_a_different_question(paraphrase):
    # The whole project is about not presenting a plausible answer to a
    # question that wasn't asked. Near misses must miss.
    assert replay.lookup(paraphrase) is None


def test_suggestions_are_real_recorded_questions():
    for q in replay.suggest("what was revenue in march", n=3):
        assert replay.lookup(q) is not None


@pytest.mark.parametrize("message", all_messages())
def test_every_starter_has_a_recorded_answer(message):
    assert replay.lookup(message) is not None, f"starter has no recording: {message!r}"


def test_starter_groups_are_balanced():
    assert len(STARTER_GROUPS) == 3
    for _, starters in STARTER_GROUPS:
        assert len(starters) == 4
