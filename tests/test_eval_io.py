"""Tests for scripts/eval_io.py: a broken eval run must never replace good
recorded results. This guards against the incident where re-running the
stress test against an ended trial overwrote the real responses with API
errors."""

import datetime as dt
import os
import sys
from decimal import Decimal

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from eval_io import infrastructure_failures, save_results  # noqa: E402

API_ERROR = 'API_ERROR: {"code": "390913", "message": "Your free trial has ended and all of your virtual warehouses have been suspended."}'


def test_api_errors_count_as_infrastructure_failures():
    results = [{"id": "s1", "cortex_text": API_ERROR}, {"id": "s2", "cortex_text": "A real answer."}]
    assert infrastructure_failures(results) == ["s1"]


def test_a_model_writing_bad_sql_is_a_legitimate_result_not_a_failure():
    # The baseline's own SQL errors are recorded findings (see Phase 5).
    results = [{"id": "cohort_3", "exec_error": "SQL compilation error: 'COHORT_MONTH' is not a valid group by expression"}]
    assert infrastructure_failures(results) == []


def test_a_broken_run_leaves_the_canonical_file_untouched(tmp_path):
    canonical = tmp_path / "results.yaml"
    canonical.write_text("results:\n- id: s1\n  cortex_text: the real recorded answer\n")
    before = canonical.read_bytes()
    written = save_results(str(canonical), [{"id": "s1", "cortex_text": API_ERROR}])
    assert canonical.read_bytes() == before
    assert ".failed-" in written and os.path.exists(written)


def test_a_clean_run_writes_safe_loadable_yaml(tmp_path):
    out = tmp_path / "results.yaml"
    save_results(str(out), [{"id": "h1", "actual_rows": [[Decimal("1512773.33")]], "month": dt.date(2025, 8, 1)}])
    loaded = yaml.safe_load(out.read_text())   # used to need an unsafe loader for Decimal tags
    assert loaded["results"][0]["actual_rows"] == [[1512773.33]]
    assert loaded["results"][0]["month"] == "2025-08-01"
