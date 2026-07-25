"""Unit tests for chainlit_app/formatting.py.

These are the pure functions that turn raw Snowflake rows into what the user
actually reads, so a regression here is a visible product bug. The module has
no Chainlit or network dependency, which is why it is testable on its own.

Run:  pytest -q
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from chainlit_app.formatting import (  # noqa: E402
    clean_interpretation_text,
    find_trend_columns,
    format_value,
    humanize_column,
    is_numeric,
    render_answer,
    rows_to_markdown,
)


class TestHumanizeColumn:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("ENDING_MRR", "Ending MRR"),
            ("NEW_MRR", "New MRR"),
            ("CUSTOMER_ID", "Customer ID"),
            ("CUSTOMER_NAME", "Customer Name"),
            ("MONTH", "Month"),
            ("NRR", "NRR"),
            ("SMB_REVENUE", "SMB Revenue"),
        ],
    )
    def test_known_shapes(self, raw, expected):
        assert humanize_column(raw) == expected

    def test_pct_suffix_becomes_percent_sign_with_a_space(self):
        # Regression: an earlier version stripped the space and produced
        # "Retention Rate%", which reads as a typo.
        assert humanize_column("RETENTION_RATE_PCT") == "Retention Rate %"

    def test_digits_are_preserved_not_capitalised(self):
        assert humanize_column("Q3_2025") == "Q3 2025"

    def test_whitespace_is_tolerated(self):
        assert humanize_column("  ENDING_MRR  ") == "Ending MRR"


class TestIsNumeric:
    def test_bools_are_not_numbers(self):
        # bool is a subclass of int, so this needs an explicit guard.
        assert is_numeric(True) is False
        assert is_numeric(False) is False

    def test_numbers_are_numbers(self):
        assert is_numeric(3) is True
        assert is_numeric(3.5) is True

    def test_strings_and_none_are_not(self):
        assert is_numeric("3") is False
        assert is_numeric(None) is False


class TestFormatValue:
    def test_currency_columns_get_a_dollar_sign_and_two_decimals(self):
        assert format_value("ENDING_MRR", 4124700.85) == "$4,124,700.85"

    def test_percent_columns_get_one_decimal_and_a_sign(self):
        assert format_value("CHURN_RATE_PCT", 12.345) == "12.3%"

    def test_id_columns_are_never_thousands_separated(self):
        # "1,234" as a customer id would be wrong and confusing.
        assert format_value("CUSTOMER_ID", 1234) == "1234"

    def test_plain_integers_get_thousands_separators(self):
        assert format_value("ROW_COUNT", 1234567) == "1,234,567"

    def test_none_renders_as_a_placeholder_not_the_word_none(self):
        assert format_value("ENDING_MRR", None) not in ("None", "")

    def test_booleans_render_as_yes_no(self):
        assert format_value("IS_ACTIVE", True) == "Yes"
        assert format_value("IS_ACTIVE", False) == "No"

    def test_strings_pass_through(self):
        assert format_value("CUSTOMER_NAME", "Wu-Reyes") == "Wu-Reyes"


class TestCleanInterpretationText:
    def test_strips_the_boilerplate_preamble(self):
        text = "This is our interpretation of your question:\n\nTotal MRR by segment for Q3, broken out by month."
        out = clean_interpretation_text(text, "What was MRR in Q3?")
        assert "interpretation of your question" not in out
        assert out.startswith("Total MRR by segment")

    def test_drops_text_that_merely_parrots_the_question(self):
        # Restating the user's own question back at them adds nothing.
        q = "What was our total MRR in June 2026?"
        text = "This is our interpretation of your question:\n\nWhat was our total MRR in June 2026?"
        assert clean_interpretation_text(text, q) == ""

    def test_keeps_genuine_elaboration(self):
        q = "Was churn anomalous in January 2025?"
        text = (
            "Check whether churn was flagged as anomalous in January 2025. Note: the "
            "anomaly_flags table has no row for January 2025 because there is insufficient "
            "prior history to compute a rolling average or z score."
        )
        out = clean_interpretation_text(text, q)
        assert "insufficient" in out

    def test_empty_input_is_safe(self):
        assert clean_interpretation_text("", "anything") == ""
        assert clean_interpretation_text(None, "anything") == ""


class TestRenderAnswer:
    def test_single_row_single_measure_becomes_a_headline_stat(self):
        out = render_answer(["ENDING_MRR"], [(4124700.85,)])
        assert "$4,124,700.85" in out
        assert out.lstrip().startswith("##")  # headline, not a table
        assert "|" not in out

    def test_headline_keeps_other_columns_as_supporting_context(self):
        out = render_answer(["MONTH", "ENDING_MRR"], [("2026-06-01", 4124700.85)])
        assert "$4,124,700.85" in out
        assert "2026-06-01" in out

    def test_multi_measure_row_falls_back_to_a_table(self):
        out = render_answer(["NEW_MRR", "CHURN_MRR"], [(100.0, 50.0)])
        assert "|" in out

    def test_multi_row_result_is_a_table_with_humanized_headers(self):
        out = render_answer(["CUSTOMER_ID", "HEALTH_SCORE"], [("CUST-1", 65.4), ("CUST-2", 66.1)])
        assert "Customer ID" in out
        assert "|" in out


class TestRowsToMarkdown:
    def test_long_results_are_capped_and_counted(self):
        rows = [(f"CUST-{i:04d}", float(i)) for i in range(191)]
        out = rows_to_markdown(["CUSTOMER_ID", "HEALTH_SCORE"], rows, preview_limit=10)
        assert "191" in out
        # 2 header lines + 10 data rows, never all 191.
        assert out.count("CUST-") == 10

    def test_short_results_get_no_truncation_note(self):
        rows = [("CUST-0001", 1.0), ("CUST-0002", 2.0)]
        out = rows_to_markdown(["CUSTOMER_ID", "HEALTH_SCORE"], rows, preview_limit=10)
        assert "total rows" not in out


class TestFindTrendColumns:
    def test_detects_a_date_column_plus_one_measure(self):
        cols = ["MONTH", "ENDING_MRR"]
        rows = [("2025-01-01", 1.0), ("2025-02-01", 2.0), ("2025-03-01", 3.0)]
        assert find_trend_columns(cols, rows) == (0, 1)

    def test_too_few_rows_is_not_a_trend(self):
        cols = ["MONTH", "ENDING_MRR"]
        rows = [("2025-01-01", 1.0), ("2025-02-01", 2.0)]
        assert find_trend_columns(cols, rows) is None

    def test_multiple_measures_is_not_a_single_line_trend(self):
        cols = ["MONTH", "NEW_MRR", "CHURN_MRR"]
        rows = [("2025-01-01", 1.0, 2.0), ("2025-02-01", 1.0, 2.0), ("2025-03-01", 1.0, 2.0)]
        assert find_trend_columns(cols, rows) is None

    def test_no_date_column_is_not_a_trend(self):
        cols = ["CUSTOMER_ID", "HEALTH_SCORE"]
        rows = [("CUST-1", 1.0), ("CUST-2", 2.0), ("CUST-3", 3.0)]
        assert find_trend_columns(cols, rows) is None
