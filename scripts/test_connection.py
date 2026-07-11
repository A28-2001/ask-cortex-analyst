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
cur.execute("select current_user(), current_role(), current_version()")
row = cur.fetchone()
print(f"Connected as user={row[0]} role={row[1]} snowflake_version={row[2]}")
cur.close()
conn.close()
