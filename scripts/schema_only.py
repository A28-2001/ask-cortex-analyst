"""Raw schema text for the naive baseline -- names and types only, no
business descriptions, no synonyms, no guardrails, no examples. This is
the deliberate control condition against the grounded semantic model."""

RAW_SCHEMA = """
Table: mrr_movements (one row per calendar month, company-wide)
  month DATE
  starting_mrr FLOAT
  new_mrr FLOAT
  expansion_mrr FLOAT
  contraction_mrr FLOAT
  churn_mrr FLOAT
  reactivation_mrr FLOAT
  net_new_mrr FLOAT
  ending_mrr FLOAT
  new_customers NUMBER
  churned_customers NUMBER
  net_revenue_retention_pct FLOAT

Table: mrr_movements_by_segment (one row per month x segment)
  month DATE
  segment TEXT
  starting_mrr FLOAT
  new_mrr FLOAT
  expansion_mrr FLOAT
  contraction_mrr FLOAT
  churn_mrr FLOAT
  reactivation_mrr FLOAT
  net_new_mrr FLOAT
  ending_mrr FLOAT
  new_customers NUMBER
  churned_customers NUMBER
  net_revenue_retention_pct FLOAT

Table: cohort_retention (one row per cohort_month x active_month)
  cohort_month DATE
  active_month DATE
  months_since_cohort NUMBER
  cohort_size NUMBER
  active_customers NUMBER
  retention_rate_pct NUMBER

Table: customer_health_scores (one row per active customer)
  customer_id TEXT
  company_name TEXT
  segment TEXT
  cohort_month DATE
  industry TEXT
  sales_rep TEXT
  engagement_score FLOAT
  recency_score NUMBER
  support_score NUMBER
  nps_score_normalized FLOAT
  revenue_health_score FLOAT
  current_mrr FLOAT
  expansion_mrr FLOAT
  contraction_mrr FLOAT
  composite_health_score FLOAT
  health_status TEXT

Table: anomaly_flags (one row per calendar month, company-wide)
  month DATE
  new_mrr FLOAT
  expansion_mrr FLOAT
  contraction_mrr FLOAT
  churn_mrr FLOAT
  net_new_mrr FLOAT
  ending_mrr FLOAT
  net_revenue_retention_pct FLOAT
  net_mrr_z_score FLOAT
  churn_z_score FLOAT
  expansion_z_score FLOAT
  new_mrr_z_score FLOAT
  contraction_z_score FLOAT
  net_mrr_anomaly BOOLEAN
  churn_anomaly BOOLEAN
  expansion_anomaly BOOLEAN
  new_mrr_anomaly BOOLEAN
  contraction_anomaly BOOLEAN
  total_anomalies NUMBER
  anomaly_status TEXT
""".strip()
