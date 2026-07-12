import os
import yaml
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

conn = snowflake.connector.connect(
    account=os.environ["SNOWFLAKE_ACCOUNT"],
    user=os.environ["SNOWFLAKE_USER"],
    private_key_file=os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"],
    role=os.environ["SNOWFLAKE_ROLE"],
    warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
    database=os.environ["SNOWFLAKE_DATABASE"],
    schema=os.environ["SNOWFLAKE_SCHEMA"],
)
cur = conn.cursor()

# Each answerable question carries the SQL used to independently compute its
# ground truth. This SQL is executed here, never generated or graded by
# Cortex Analyst or the baseline LLM.
ANSWERABLE_QUESTIONS = [
    # -- point-in-time MRR lookups --
    dict(id="pit_1", category="point_in_time", question="What was our total MRR in March 2025?",
         sql="SELECT ending_mrr FROM mrr_movements WHERE month = '2025-03-01'"),
    dict(id="pit_2", category="point_in_time", question="What was our starting MRR in September 2025?",
         sql="SELECT starting_mrr FROM mrr_movements WHERE month = '2025-09-01'"),
    dict(id="pit_3", category="point_in_time", question="How many customers did we churn in July 2025?",
         sql="SELECT churned_customers FROM mrr_movements WHERE month = '2025-07-01'"),
    dict(id="pit_4", category="point_in_time", question="How many new customers did we acquire in October 2025?",
         sql="SELECT new_customers FROM mrr_movements WHERE month = '2025-10-01'"),

    # -- period aggregation (flows) --
    dict(id="agg_1", category="period_aggregation", question="How much churn MRR did we lose in Q1 2025?",
         sql="SELECT SUM(churn_mrr) FROM mrr_movements WHERE month BETWEEN '2025-01-01' AND '2025-03-31'"),
    dict(id="agg_2", category="period_aggregation", question="How much expansion MRR did we generate in the second half of 2025?",
         sql="SELECT SUM(expansion_mrr) FROM mrr_movements WHERE month BETWEEN '2025-07-01' AND '2025-12-31'"),
    dict(id="agg_3", category="period_aggregation", question="What was our net new MRR for all of 2025?",
         sql="SELECT SUM(net_new_mrr) FROM mrr_movements WHERE month BETWEEN '2025-01-01' AND '2025-12-31'"),
    dict(id="agg_4", category="period_aggregation", question="How many new customers did we add in Q4 2025?",
         sql="SELECT SUM(new_customers) FROM mrr_movements WHERE month BETWEEN '2025-10-01' AND '2025-12-31'"),

    # -- segment-specific --
    dict(id="seg_1", category="segment", question="How much churn MRR did the enterprise segment have in 2025?",
         sql="SELECT SUM(churn_mrr) FROM mrr_movements_by_segment WHERE segment = 'enterprise' AND month BETWEEN '2025-01-01' AND '2025-12-31'"),
    dict(id="seg_2", category="segment", question="What was the mid-market segment's ending MRR in December 2025?",
         sql="SELECT ending_mrr FROM mrr_movements_by_segment WHERE segment = 'mid_market' AND month = '2025-12-01'"),
    dict(id="seg_3", category="segment", question="Which segment had the most new MRR in Q3 2025?",
         sql="SELECT segment FROM mrr_movements_by_segment WHERE month BETWEEN '2025-07-01' AND '2025-09-30' GROUP BY segment ORDER BY SUM(new_mrr) DESC LIMIT 1"),
    dict(id="seg_4", category="segment", question="What drove the July 2025 SMB churn increase?",
         sql="SELECT new_mrr, expansion_mrr, contraction_mrr, churn_mrr FROM mrr_movements_by_segment WHERE segment = 'smb' AND month = '2025-07-01'"),

    # -- NRR --
    dict(id="nrr_1", category="nrr", question="What was our net revenue retention in April 2025?",
         sql="SELECT net_revenue_retention_pct FROM mrr_movements WHERE month = '2025-04-01'"),
    dict(id="nrr_2", category="nrr", question="What was the average NRR across 2025?",
         sql="SELECT ROUND(AVG(net_revenue_retention_pct), 1) FROM mrr_movements WHERE month BETWEEN '2025-01-01' AND '2025-12-31'"),
    dict(id="nrr_3", category="nrr", question="What was the enterprise segment's NRR in November 2025?",
         sql="SELECT net_revenue_retention_pct FROM mrr_movements_by_segment WHERE segment = 'enterprise' AND month = '2025-11-01'"),

    # -- cohort retention --
    dict(id="cohort_1", category="cohort_retention", question="What percentage of the March 2025 cohort was still active after 3 months?",
         sql="SELECT retention_rate_pct FROM cohort_retention WHERE cohort_month = '2025-03-01' AND months_since_cohort = 3"),
    dict(id="cohort_2", category="cohort_retention", question="How many customers were in the February 2025 cohort at signup?",
         sql="SELECT DISTINCT cohort_size FROM cohort_retention WHERE cohort_month = '2025-02-01'"),
    dict(id="cohort_3", category="cohort_retention", question="Which cohort had the best 6-month retention rate?",
         sql="SELECT cohort_month FROM cohort_retention WHERE months_since_cohort = 6 ORDER BY retention_rate_pct DESC LIMIT 1"),
    dict(id="cohort_4", category="cohort_retention", question="What was the retention rate for the May 2025 cohort in their first month?",
         sql="SELECT retention_rate_pct FROM cohort_retention WHERE cohort_month = '2025-05-01' AND months_since_cohort = 0"),

    # -- customer health --
    dict(id="health_1", category="customer_health", question="How many customers are currently in critical health status?",
         sql="SELECT COUNT(*) FROM customer_health_scores WHERE health_status = 'critical'"),
    dict(id="health_2", category="customer_health", question="What is the average health score for the enterprise segment?",
         sql="SELECT ROUND(AVG(composite_health_score), 1) FROM customer_health_scores WHERE segment = 'enterprise'"),
    dict(id="health_3", category="customer_health", question="Which industry has the most at-risk customers?",
         sql="SELECT industry FROM customer_health_scores WHERE health_status = 'at_risk' GROUP BY industry ORDER BY COUNT(*) DESC LIMIT 1"),
    dict(id="health_4", category="customer_health", question="What is the total current MRR from customers with critical health status?",
         sql="SELECT SUM(current_mrr) FROM customer_health_scores WHERE health_status = 'critical'"),

    # -- anomaly / cross-table --
    dict(id="anom_1", category="anomaly", question="Which months were flagged as anomalous in 2025?",
         sql="SELECT LISTAGG(TO_VARCHAR(month), ', ') WITHIN GROUP (ORDER BY month) FROM anomaly_flags WHERE anomaly_status = 'flagged' AND month BETWEEN '2025-01-01' AND '2025-12-31'"),
    dict(id="anom_2", category="anomaly", question="What was the churn z-score in the month with the highest churn MRR in 2025?",
         sql="""WITH mc AS (
                  SELECT month FROM mrr_movements
                  WHERE month BETWEEN '2025-01-01' AND '2025-12-31'
                  ORDER BY churn_mrr DESC LIMIT 1)
                SELECT a.churn_z_score FROM mc JOIN anomaly_flags a ON mc.month = a.month"""),
    dict(id="anom_3", category="anomaly", question="How many total anomalies were flagged across all of 2025?",
         sql="SELECT SUM(total_anomalies) FROM anomaly_flags WHERE month BETWEEN '2025-01-01' AND '2025-12-31'"),
    dict(id="anom_4", category="anomaly", question="Was expansion MRR ever anomalously high in 2025?",
         sql="SELECT COUNT(*) FROM anomaly_flags WHERE expansion_anomaly = TRUE AND month BETWEEN '2025-01-01' AND '2025-12-31'"),

    # -- ambiguous phrasing (should still resolve to a defensible interpretation) --
    dict(id="amb_1", category="ambiguous", question="How's our MRR looking lately?",
         sql="SELECT ending_mrr FROM mrr_movements ORDER BY month DESC LIMIT 1",
         note="Acceptable if it answers with the most recent month's MRR, or asks which month."),
    dict(id="amb_2", category="ambiguous", question="What was our MRR growth over 2025?",
         sql="""SELECT (SELECT ending_mrr FROM mrr_movements WHERE month = '2025-12-01')
                       - (SELECT starting_mrr FROM mrr_movements WHERE month = '2025-01-01')"""),
    dict(id="amb_3", category="ambiguous", question="Which customers should we be worried about?",
         sql="SELECT COUNT(*) FROM customer_health_scores WHERE health_status IN ('at_risk', 'critical')",
         note="Acceptable if it interprets this as at_risk and/or critical customers; grade on whether the interpretation is data-grounded and stated, not on matching this exact filter."),
]

# Guardrail questions have no ground-truth SQL: the correct behavior is a
# refusal, not an answer. expected_reason documents why.
GUARDRAIL_QUESTIONS = [
    dict(id="guard_1", category="guardrail_forecast", question="What will our MRR be next quarter?",
         expected_reason="Forecasting is out of scope; the model only has historical data."),
    dict(id="guard_2", category="guardrail_undefined_metric", question="What is our customer lifetime value?",
         expected_reason="CLV is not a defined metric in the semantic model (no acquisition cost data)."),
    dict(id="guard_3", category="guardrail_insufficient_data", question="Was churn anomalous in January 2025?",
         expected_reason="January 2025 is the dataset's first month; anomaly_flags has no row for it (insufficient rolling history). Correct behavior is to say history is insufficient, not to imply it was normal."),
    dict(id="guard_4", category="guardrail_undefined_metric", question="What is our customer acquisition cost?",
         expected_reason="No marketing spend or acquisition cost data exists in this dataset."),
    dict(id="guard_5", category="guardrail_no_data", question="How does our churn rate compare to our competitors?",
         expected_reason="No competitor data exists in this dataset."),
    dict(id="guard_6", category="guardrail_nonexistent_entity", question="What is the health score for customer CUST-9999?",
         expected_reason="CUST-9999 does not exist (valid IDs run CUST-0001 to CUST-0500)."),
]


def fetch_ground_truth(sql: str):
    cur.execute(sql)
    rows = cur.fetchall()
    if len(rows) == 1 and len(rows[0]) == 1:
        return rows[0][0]
    return rows


results = []
for q in ANSWERABLE_QUESTIONS:
    truth = fetch_ground_truth(q["sql"])
    results.append({
        "id": q["id"],
        "category": q["category"],
        "type": "answerable",
        "question": q["question"],
        "ground_truth_sql": q["sql"].strip(),
        "ground_truth_value": str(truth),
        **({"note": q["note"]} if "note" in q else {}),
    })

for q in GUARDRAIL_QUESTIONS:
    results.append({
        "id": q["id"],
        "category": q["category"],
        "type": "guardrail",
        "question": q["question"],
        "expected_behavior": "refuse",
        "expected_reason": q["expected_reason"],
    })

out_path = os.path.join(os.path.dirname(__file__), "..", "eval", "questions.yaml")
with open(out_path, "w") as f:
    yaml.dump({"questions": results}, f, sort_keys=False, width=100, allow_unicode=True)

print(f"Wrote {len(results)} questions ({len(ANSWERABLE_QUESTIONS)} answerable, {len(GUARDRAIL_QUESTIONS)} guardrail) to {out_path}")
for r in results:
    if r["type"] == "answerable":
        print(f"  [{r['id']}] {r['question']}  -> {r['ground_truth_value']}")
    else:
        print(f"  [{r['id']}] {r['question']}  -> EXPECT REFUSAL ({r['expected_reason'][:50]}...)")

conn.close()
