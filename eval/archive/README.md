Intermediate raw results from the iteration cycles in Phases 4 and 6,
kept as evidence of the before/after fixes rather than deleted. The
current, final results live one level up in `eval/`.

- `cortex_analyst_results_v1.yaml` — first pass, before any fixes (93.1%)
- `cortex_analyst_results_v2_pre_s8_fix.yaml` — after the Phase 4
  guardrail/amb_2 fixes, before the Phase 6 false-premise fix
- `cortex_analyst_results_v2b_pre_daterange_fix.yaml` — after the s8
  false-premise fix, before the date-range documentation fix
- `stress_test_cortex_results_v1.yaml` — first stress test pass, before
  the s1/s8 false-premise fix
- `stress_test_cortex_results_v2.yaml` — after the false-premise fix,
  before the date-range fix (amb_2 regression discovered on this run)
- `baseline_results_raw_v1_parsing_bug.yaml` — first baseline run, before
  fixing the harness's CANNOT_ANSWER parsing bug (not a baseline behavior
  change, a measurement fix)

See `eval/phase4_results_summary.md` and `eval/phase6_results_summary.md`
for the full narrative these snapshots support.
