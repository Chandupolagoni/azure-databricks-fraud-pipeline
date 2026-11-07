-- Snowflake-native ALERT on top of VW_TASK_FAILURE_MONITOR (snowflake/ddl/11_create_task_failure_monitor_view.sql).
--
-- That view gives on-call something to query, but nothing proactively tells them a task
-- failed -- its own header comment calls this out directly ("a future alert on top of this,
-- if added, should account for [ACCOUNT_USAGE's replication] lag in its evaluation window").
-- This closes that gap, mirroring the `adf_pipeline_failure` log-based alert
-- (terraform/modules/monitoring) one layer up the stack, but running natively in Snowflake
-- since ACCOUNT_USAGE.TASK_HISTORY isn't something Azure Monitor/Log Analytics can see.
--
-- SCHEDULE is hourly, not the ADF alert's 15-minute default: polling faster wouldn't catch
-- a failure any sooner, since a failed run can take up to ~120 minutes to appear in
-- ACCOUNT_USAGE.TASK_HISTORY at all, and would just burn WH_LOADER credits on empty checks
-- in the meantime.
--
-- The IF condition looks back 180 minutes (one schedule interval + the ~120-minute
-- replication lag), not just since the last check ~60 minutes ago -- a row that only just
-- became visible can describe a failure whose scheduled_time is up to 120 minutes in the
-- past, so a plain "since last check" window would miss it. 180 minutes guarantees every
-- newly-visible failed row falls inside at least one check's window before scrolling out of
-- it, at the cost of (intentionally) re-notifying on the same failure across a couple of
-- hourly runs rather than risk silently dropping one.
--
-- SYSTEM$SEND_EMAIL requires a notification integration bound to on-call's distribution
-- list. Like the Snowflake loader password and Databricks PAT (docs/runbook.md step 3),
-- that integration is provisioned out-of-band by ACCOUNTADMIN rather than committed here:
--   CREATE NOTIFICATION INTEGRATION task_failure_alert_notify
--     TYPE = EMAIL ENABLED = TRUE
--     ALLOWED_RECIPIENTS = ('fraud-ops@example.com');
-- Swap the recipient address below for the real on-call distribution list at deploy time.

USE SCHEMA FRAUD_PLATFORM.MARTS;

CREATE OR REPLACE ALERT ALERT_TASK_FAILURE
  WAREHOUSE = WH_LOADER
  SCHEDULE = '60 MINUTE'
  IF (
    EXISTS (
      SELECT 1
      FROM VW_TASK_FAILURE_MONITOR
      WHERE scheduled_time >= DATEADD(minute, -180, CURRENT_TIMESTAMP())
    )
  )
  THEN
    CALL SYSTEM$SEND_EMAIL(
      'task_failure_alert_notify',
      'fraud-ops@example.com',
      'FRAUD_PLATFORM: warehouse task failure detected',
      'One or more of TASK_REFRESH_MARTS, TASK_REFRESH_FRAUD_SCORES, or ' ||
      'TASK_RECONCILE_FRAUD_OUTCOMES failed in the trailing window. Check ' ||
      'FRAUD_PLATFORM.MARTS.VW_TASK_FAILURE_MONITOR for the failed run(s) and ' ||
      'VW_TASK_FAILURE_CASCADE_CHECK in case TASK_REFRESH_FRAUD_SCORES never ran as a result.'
    );

ALTER ALERT ALERT_TASK_FAILURE RESUME;
