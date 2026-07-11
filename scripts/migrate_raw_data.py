import os
import pandas as pd
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
from sqlalchemy import create_engine
from dotenv import load_dotenv

OLD_PROJECT_ENV = "../SaaS Revenue Intelligence Dashboard/.env"
load_dotenv(OLD_PROJECT_ENV)
pg_url = os.environ["DATABASE_URL"]

load_dotenv(override=True)  # reload this project's .env (Snowflake vars) without losing DATABASE_URL name clashes
sf_account = os.environ["SNOWFLAKE_ACCOUNT"]
sf_user = os.environ["SNOWFLAKE_USER"]
sf_key_path = os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"]
sf_role = os.environ["SNOWFLAKE_ROLE"]
sf_warehouse = os.environ["SNOWFLAKE_WAREHOUSE"]
sf_database = os.environ["SNOWFLAKE_DATABASE"]

RAW_TABLES = ["raw_customers", "raw_subscription_events", "raw_usage_signals"]

engine = create_engine(pg_url)

sf_conn = snowflake.connector.connect(
    account=sf_account,
    user=sf_user,
    private_key_file=sf_key_path,
    role=sf_role,
    warehouse=sf_warehouse,
    database=sf_database,
    schema="RAW",
)

for table in RAW_TABLES:
    df = pd.read_sql(f"select * from public.{table}", engine)
    df.columns = [c.upper() for c in df.columns]
    success, nchunks, nrows, _ = write_pandas(
        sf_conn, df, table.upper(), auto_create_table=True, overwrite=True
    )
    print(f"{table}: loaded {nrows} rows into Snowflake RAW.{table.upper()} (success={success})")

sf_conn.close()
engine.dispose()
