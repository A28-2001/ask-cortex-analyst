import os
import pandas as pd
import snowflake.connector
from sqlalchemy import create_engine
from dotenv import load_dotenv

OLD_PROJECT_ENV = "../SaaS Revenue Intelligence Dashboard/.env"
load_dotenv(OLD_PROJECT_ENV)
pg_url = os.environ["DATABASE_URL"]

load_dotenv(override=True)
sf_conn = snowflake.connector.connect(
    account=os.environ["SNOWFLAKE_ACCOUNT"],
    user=os.environ["SNOWFLAKE_USER"],
    private_key_file=os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"],
    role=os.environ["SNOWFLAKE_ROLE"],
    warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
    database=os.environ["SNOWFLAKE_DATABASE"],
    schema=os.environ["SNOWFLAKE_SCHEMA"],
)

engine = create_engine(pg_url)

CHECKS = {
    "mrr_movements": "select count(*) as row_count, round(sum(ending_mrr)::numeric, 2) as sum_ending_mrr from public.mrr_movements",
    "cohort_retention": "select count(*) as row_count, sum(active_customers) as sum_active from public.cohort_retention",
    "customer_health_scores": "select count(*) as row_count, round(sum(composite_health_score)::numeric, 2) as sum_score from public.customer_health_scores",
    "anomaly_flags": "select count(*) as row_count, sum(total_anomalies) as sum_anomalies from public.anomaly_flags",
}

SF_CHECKS = {
    "mrr_movements": "select count(*) as row_count, round(sum(ending_mrr), 2) as sum_ending_mrr from mrr_movements",
    "cohort_retention": "select count(*) as row_count, sum(active_customers) as sum_active from cohort_retention",
    "customer_health_scores": "select count(*) as row_count, round(sum(composite_health_score), 2) as sum_score from customer_health_scores",
    "anomaly_flags": "select count(*) as row_count, sum(total_anomalies) as sum_anomalies from anomaly_flags",
}

print(f"{'table':<25} {'pg_rows':>8} {'sf_rows':>8} {'pg_check':>14} {'sf_check':>14}  match")
print("-" * 90)
for table, pg_sql in CHECKS.items():
    pg_row = pd.read_sql(pg_sql, engine).iloc[0]
    cur = sf_conn.cursor()
    cur.execute(SF_CHECKS[table])
    sf_row = cur.fetchone()
    sf_rows, sf_check = sf_row[0], float(sf_row[1])
    pg_rows, pg_check = int(pg_row.iloc[0]), float(pg_row.iloc[1])
    match = pg_rows == sf_rows and abs(pg_check - sf_check) < 0.5
    print(f"{table:<25} {pg_rows:>8} {sf_rows:>8} {pg_check:>14.2f} {sf_check:>14.2f}  {'MATCH' if match else 'MISMATCH'}")

sf_conn.close()
engine.dispose()
