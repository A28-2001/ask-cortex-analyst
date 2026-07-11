import os
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

conn = snowflake.connector.connect(
    account=os.environ["SNOWFLAKE_ACCOUNT"],
    user=os.environ["SNOWFLAKE_USER"],
    private_key_file=os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"],
)
cur = conn.cursor()

statements = [
    """CREATE WAREHOUSE IF NOT EXISTS NL_ASSISTANT_WH
         WAREHOUSE_SIZE = 'XSMALL'
         AUTO_SUSPEND = 60
         AUTO_RESUME = TRUE
         INITIALLY_SUSPENDED = TRUE""",
    "CREATE DATABASE IF NOT EXISTS NL_ASSISTANT_DB",
    "CREATE SCHEMA IF NOT EXISTS NL_ASSISTANT_DB.ANALYTICS",
    "CREATE ROLE IF NOT EXISTS NL_ASSISTANT_ROLE",
    "GRANT USAGE ON WAREHOUSE NL_ASSISTANT_WH TO ROLE NL_ASSISTANT_ROLE",
    "GRANT ALL ON DATABASE NL_ASSISTANT_DB TO ROLE NL_ASSISTANT_ROLE",
    "GRANT ALL ON SCHEMA NL_ASSISTANT_DB.ANALYTICS TO ROLE NL_ASSISTANT_ROLE",
    "GRANT ROLE NL_ASSISTANT_ROLE TO USER AAKASH",
]

for stmt in statements:
    cur.execute(stmt)
    print(f"OK: {stmt.splitlines()[0]}")

cur.execute("SHOW WAREHOUSES LIKE 'NL_ASSISTANT_WH'")
print(cur.fetchall())

cur.close()
conn.close()
