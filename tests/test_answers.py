"""Tests for chainlit_app/answers.py: what the visitor reads for every outcome."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from chainlit_app import answers, replay  # noqa: E402

DASHES = ("—", "–")  # em dash, en dash: the owner's house style bans both


class TestParseReply:
    @pytest.mark.parametrize("resp", [None, {}, {"message": None}, {"message": {"content": None}},
                                      {"message": {"content": [None, {}, {"type": "unknown"}]}}])
    def test_malformed_responses_parse_to_nothing_instead_of_raising(self, resp):
        assert answers.parse_reply(resp) == (None, "", [])

    def test_a_sql_block_missing_its_statement_is_not_sql(self):
        # Used to raise KeyError mid-answer, after history had already been saved.
        resp = {"message": {"content": [{"type": "sql"}, {"type": "text", "text": "hi"}]}}
        assert answers.parse_reply(resp) == (None, "hi", [])

    def test_extracts_all_three_parts(self):
        resp = {"message": {"content": [
            {"type": "text", "text": "Interpretation"},
            {"type": "sql", "statement": "SELECT 1"},
            {"type": "suggestions", "suggestions": ["Next?", "", None, "  "]},
        ]}}
        assert answers.parse_reply(resp) == ("SELECT 1", "Interpretation", ["Next?"])


class TestCompose:
    def test_no_sql_is_a_declined_answer(self):
        body, trend = answers.compose("q?", "Forecasting is out of scope.", None)
        assert body.startswith("**Can't answer this.**") and "Forecasting is out of scope." in body
        assert trend is None

    def test_zero_rows_explains_instead_of_showing_an_empty_table(self):
        body, _ = answers.compose("q?", "", "SELECT 1", ["X"], [])
        assert body.startswith("**No matching data.**") and "|" not in body

    def test_a_single_value_becomes_a_headline(self):
        body, _ = answers.compose("q?", "", "SELECT 1", ["ENDING_MRR"], [(4124700.85,)])
        assert "## $4,124,700.85" in body

    def test_total_rows_reaches_the_table_note(self):
        rows = [(f"C{i}", float(i)) for i in range(20)]
        body, _ = answers.compose("q?", "", "SELECT 1", ["CUSTOMER_ID", "HEALTH_SCORE"], rows, total_rows=238)
        assert "238 total rows" in body


class TestRecordedLabels:
    @pytest.mark.parametrize("reason", list(answers.WHY_RECORDED))
    def test_every_recorded_answer_is_labelled_with_its_real_reason(self, reason):
        data = next(e for e in replay.entries() if e["kind"] == "data")
        refusal = next(e for e in replay.entries() if e["kind"] == "refusal")
        for entry in (data, refusal):
            note = answers.recorded_note(entry, reason)
            assert note.startswith("> **Recorded answer.**")
            assert answers.WHY_RECORDED[reason] in note
            assert entry["origin"] in note and entry["recorded"] in note
        assert "Snowflake returned" in answers.recorded_note(data, reason)
        assert "Snowflake returned" not in answers.recorded_note(refusal, reason)


class TestWithoutDashes:
    @pytest.mark.parametrize("text,expected", [
        ("historical MRR data \u2014 it has no forecasting data", "historical MRR data, it has no forecasting data"),
        ("new MRR in Q3 2025 (July\u2013September 2025)?", "new MRR in Q3 2025 (July to September 2025)?"),
        ("between 2025\u20132026", "between 2025 to 2026"),
        ("flags\u2014but none", "flags, but none"),
        ("A well-formed, hyphenated mid-market answer", "A well-formed, hyphenated mid-market answer"),
        ("", ""),
        (None, None),
    ])
    def test_dashes_become_plain_punctuation(self, text, expected):
        assert answers.without_dashes(text) == expected

    def test_every_recorded_answer_renders_without_a_dash(self):
        for e in replay.entries():
            body, _ = answers.compose(e["question"], e["text"], e.get("sql"), e.get("columns"), e.get("rows"))
            assert not any(d in body for d in DASHES), (e["id"], body[:200])


def test_no_visitor_facing_copy_contains_a_dash():
    entry = replay.entries()[0]
    copy = [answers.DECLINED_DEFAULT, answers.EMPTY_DEFAULT, answers.NO_SQL_STEP,
            answers.QUERY_FAILED, answers.REQUEST_FAILED]
    copy += [answers.no_recording(r) for r in answers.WHY_RECORDED]
    copy += [answers.recorded_note(entry, r) for r in answers.WHY_RECORDED]
    for text in copy:
        assert not any(d in text for d in DASHES), text
