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

    def test_known_percent_measures_get_one_decimal_and_a_sign(self):
        # The semantic model documents these on a 0 to 100 scale.
        assert format_value("RETENTION_RATE_PCT", 76.45) == "76.5%"
        assert format_value("NET_REVENUE_RETENTION_PCT", 100.19) == "100.2%"
        assert format_value("AVG_NRR_2025", 100.1909) == "100.2%"  # Cortex's alias for NRR

    def test_a_pct_column_of_unknown_scale_is_not_given_a_percent_sign(self):
        # Cortex computed this one as a fraction, (q2 - q1) / q1. Calling
        # -0.4523 "-0.5%" would understate a 45% drop ninety times over.
        assert format_value("CHURN_PCT_CHG", -0.4523) == "-0.45"
        assert format_value("CHURN_RATE_PCT", 12.345) == "12.35"

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


# ---------------------------------------------------------------------------
# Regressions found in review. Each of these was a live bug: the column names
# are real semantic-model or Cortex-generated columns.
# ---------------------------------------------------------------------------

import datetime as dt  # noqa: E402
from decimal import Decimal  # noqa: E402

from chainlit_app.formatting import trend_chart_png  # noqa: E402


class TestColumnUnits:
    @pytest.mark.parametrize(
        "col,value,expected",
        [
            ("NET_MRR_Z_SCORE", -1.234, "-1.23"),       # was "$-1.23": a z-score, not money
            ("MRR_GROWTH_RATE", 0.053, "0.05"),         # was "$0.05": a ratio, not money
            ("CUSTOMERS_WITH_MRR", 37, "37"),           # was "$37.00": a count
            ("CARRIER_COUNT", 12, "12"),                # ARR inside CARRIER is not money
            ("COMPOSITE_HEALTH_SCORE", 65.4, "65.40"),
            ("YEAR", 2025, "2025"),                     # was "2,025"
            ("MRR_GROWTH_Q1_2026", 1234.5, "$1,234.50"),
            ("TOTAL_NET_NEW_MRR", 10, "$10.00"),
        ],
    )
    def test_units_follow_the_semantic_model(self, col, value, expected):
        assert format_value(col, value) == expected

    def test_negative_money_puts_the_sign_before_the_dollar(self):
        assert format_value("NET_NEW_MRR", -5605.57) == "-$5,605.57"


class TestExactValues:
    def test_non_finite_numbers_render_instead_of_crashing(self):
        assert format_value("TOTAL", float("nan")) == "NaN"
        assert format_value("TOTAL", float("inf")) == "∞"
        assert format_value("TOTAL", Decimal("NaN")) == "NaN"

    def test_money_rounds_half_up_exactly(self):
        # Through float, Decimal("2.675") used to render as $2.67.
        assert format_value("ENDING_MRR", Decimal("2.675")) == "$2.68"

    def test_big_integers_keep_every_digit(self):
        assert format_value("ROW_COUNT", 12345678901234567891) == "12,345,678,901,234,567,891"

    def test_absurd_magnitudes_degrade_to_text_not_a_crash(self):
        assert format_value("ENDING_MRR", Decimal("1E+40"))

    @pytest.mark.parametrize(
        "value,expected",
        [
            (dt.datetime(2025, 1, 1), "2025-01-01"),
            (dt.datetime(2025, 1, 1, 13, 45), "2025-01-01 13:45"),
            (dt.date(2025, 1, 1), "2025-01-01"),
            ("2025-01-01T00:00:00", "2025-01-01"),   # how recorded answers store dates
        ],
    )
    def test_dates_drop_a_meaningless_midnight(self, value, expected):
        assert format_value("MONTH", value) == expected


class TestHumanizeEdgeCases:
    def test_a_quoted_alias_is_already_a_display_name(self):
        assert humanize_column("Total MRR") == "Total MRR"   # was "Total mrr"

    def test_arr_is_an_acronym(self):
        assert humanize_column("ANNUAL_ARR") == "Annual ARR"


class TestInterpretationFilter:
    def test_preamble_on_the_same_line_is_still_stripped(self):
        out = clean_interpretation_text(
            "This is our interpretation of your question: Total MRR by segment, by month.", "MRR?"
        )
        assert out == "Total MRR by segment, by month."

    def test_a_refusal_is_never_dropped_even_if_it_echoes_the_question(self):
        q = "What is our gross margin?"
        refusal = "What is our gross margin? Not answerable: there is no cost data."
        assert clean_interpretation_text(refusal, q) == refusal


class TestTableEdgeCases:
    def test_a_pipe_inside_a_value_does_not_shift_the_columns(self):
        out = rows_to_markdown(["NAME", "NOTE"], [("Acme", "a | b")])
        assert out.splitlines()[2].count(" | ") == 1 + out.splitlines()[0].count(" | ") - 1
        assert "a \\| b" in out

    def test_reports_the_full_result_size_when_only_part_was_fetched(self):
        rows = [(f"CUST-{i:04d}", float(i)) for i in range(1000)]
        out = rows_to_markdown(["CUSTOMER_ID", "HEALTH_SCORE"], rows, total_rows=1500)
        assert "1,500 total rows" in out


class TestTrendDetectionEdgeCases:
    def test_several_series_stacked_by_month_are_not_drawn_as_one_line(self):
        cols = ["MONTH", "SEGMENT", "ENDING_MRR"]
        rows = [(m, s, 1.0) for m in ("2025-01-01", "2025-02-01", "2025-03-01") for s in ("smb", "enterprise")]
        assert find_trend_columns(cols, rows) is None

    def test_a_name_containing_month_is_not_a_date(self):
        cols = ["AVG_MONTHLY_MRR", "TOTAL_MRR"]
        rows = [(1.0, 2.0), (3.0, 4.0), (5.0, 6.0)]
        assert find_trend_columns(cols, rows) is None

    def test_nulls_in_the_series_are_skipped_not_fatal(self):
        cols = ["MONTH", "NET_REVENUE_RETENTION_PCT"]
        rows = [("2025-01-01", None), ("2025-02-01", 99.0), ("2025-03-01", 101.0), ("2025-04-01", 100.5)]
        assert find_trend_columns(cols, rows) == (0, 1)
        assert trend_chart_png(cols, rows, 0, 1).startswith(b"\x89PNG")

    def test_real_date_objects_are_detected(self):
        cols = ["MONTH", "ENDING_MRR"]
        rows = [(dt.date(2025, m, 1), float(m)) for m in (3, 2, 1)]  # latest first
        assert find_trend_columns(cols, rows) == (0, 1)
        assert trend_chart_png(cols, rows, 0, 1).startswith(b"\x89PNG")


class TestQuestionEcho:
    PRE = "This is our interpretation of your question:  "

    def test_a_word_for_word_echo_is_dropped_and_the_note_kept(self):
        text = self.PRE + "Was churn anomalous in January 2025? Note: According to the docs, January 2025 has no row."
        assert clean_interpretation_text(text, "Was churn anomalous in January 2025?") == \
            "According to the docs, January 2025 has no row."

    def test_a_parenthetical_after_the_echo_is_unwrapped(self):
        text = self.PRE + "How many new customers did we acquire in October 2025? (Retrieving the count from mrr_movements.)"
        assert clean_interpretation_text(text, "How many new customers did we acquire in October 2025?") == \
            "Retrieving the count from mrr_movements."

    def test_a_restatement_that_sharpens_the_question_is_kept(self):
        text = self.PRE + "What was the mid-market segment's ending MRR at the end of December 2025? This uses mrr_movements_by_segment."
        out = clean_interpretation_text(text, "What was the mid-market segment's ending MRR in December 2025?")
        assert out.startswith("What was the mid-market segment's ending MRR at the end of December 2025?")

    def test_a_refusal_that_repeats_the_question_is_never_trimmed(self):
        text = "Was churn anomalous in January 2025? That can't be evaluated, there is no prior history."
        assert clean_interpretation_text(text, "Was churn anomalous in January 2025?") == text
