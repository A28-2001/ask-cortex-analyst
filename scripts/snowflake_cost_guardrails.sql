-- =====================================================================
-- Cost + security guardrails for the public Ask Cortex Analyst app
-- ---------------------------------------------------------------------
-- The deployed app is public and unauthenticated: every question spends
-- real money (a Cortex Analyst API call + warehouse compute to run the
-- generated SQL). Run this once, from the Snowflake worksheet, to cap the
-- downside and lock the app's role to read-only.
--
-- Object names below match .env.example. Change them if yours differ.
--   Warehouse : NL_ASSISTANT_WH
--   Database  : NL_ASSISTANT_DB
--   Schema    : ANALYTICS
--   App role  : NL_ASSISTANT_ROLE
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. SPEND CAP on warehouse compute  (the hard safety net)
--    A resource monitor auto-suspends the warehouse once the monthly
--    credit quota is hit, so a traffic spike or a loop of requests can't
--    run the compute bill away. Tune CREDIT_QUOTA to your comfort level;
--    on an X-Small warehouse each query is a small fraction of a credit.
-- ---------------------------------------------------------------------
USE ROLE ACCOUNTADMIN;

CREATE OR REPLACE RESOURCE MONITOR nl_assistant_monitor
  WITH
    CREDIT_QUOTA        = 5            -- credits / month; raise or lower as you like
    FREQUENCY           = MONTHLY
    START_TIMESTAMP     = IMMEDIATELY
    TRIGGERS
      ON 75  PERCENT DO NOTIFY
      ON 90  PERCENT DO NOTIFY
      ON 100 PERCENT DO SUSPEND            -- block new queries, let running ones finish
      ON 110 PERCENT DO SUSPEND_IMMEDIATE; -- kill running queries too

ALTER WAREHOUSE nl_assistant_wh SET RESOURCE_MONITOR = nl_assistant_monitor;


-- ---------------------------------------------------------------------
-- 2. TIGHTEN the warehouse so it isn't billing while idle
--    AUTO_SUSPEND = 60 means it stops the per-second billing 60s after the
--    last query. X-Small keeps each query cheap.
-- ---------------------------------------------------------------------
ALTER WAREHOUSE nl_assistant_wh SET
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND   = 60
  AUTO_RESUME    = TRUE;


-- ---------------------------------------------------------------------
-- 3. VERIFY the app's role is least-privilege (read-only, analytics only)
--    Run these first and read the output. The app should only ever need
--    to SELECT from the analytics schema and USE the warehouse. If you see
--    any INSERT / UPDATE / DELETE / CREATE / OWNERSHIP grants, remove them.
-- ---------------------------------------------------------------------
SHOW GRANTS TO ROLE nl_assistant_role;
SHOW GRANTS ON SCHEMA nl_assistant_db.analytics;


-- ---------------------------------------------------------------------
-- 4. RE-ASSERT read-only grants  (safe to run; grants are idempotent)
-- ---------------------------------------------------------------------
USE ROLE SECURITYADMIN;   -- or ACCOUNTADMIN

GRANT USAGE  ON DATABASE nl_assistant_db                      TO ROLE nl_assistant_role;
GRANT USAGE  ON SCHEMA   nl_assistant_db.analytics            TO ROLE nl_assistant_role;
GRANT SELECT ON ALL    TABLES IN SCHEMA nl_assistant_db.analytics TO ROLE nl_assistant_role;
GRANT SELECT ON FUTURE TABLES IN SCHEMA nl_assistant_db.analytics TO ROLE nl_assistant_role;
GRANT SELECT ON ALL    VIEWS  IN SCHEMA nl_assistant_db.analytics TO ROLE nl_assistant_role;
GRANT SELECT ON FUTURE VIEWS  IN SCHEMA nl_assistant_db.analytics TO ROLE nl_assistant_role;
GRANT USAGE  ON WAREHOUSE nl_assistant_wh                     TO ROLE nl_assistant_role;

-- If step 3 showed write/DDL privileges, revoke them (uncomment as needed):
-- REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA nl_assistant_db.analytics FROM ROLE nl_assistant_role;
-- REVOKE CREATE TABLE, CREATE VIEW ON SCHEMA nl_assistant_db.analytics FROM ROLE nl_assistant_role;


-- ---------------------------------------------------------------------
-- 5. NOTE on Cortex Analyst spend (serverless, billed separately)
--    A resource monitor caps *warehouse* credits only. Cortex Analyst
--    message calls are serverless and billed on their own. To watch/cap
--    that too, create an account-level Budget:
--    Snowsight -> Admin -> Cost Management -> Budgets, set a monthly $
--    limit with an email alert. That's the catch-all for total account
--    spend including Cortex.
-- ---------------------------------------------------------------------
