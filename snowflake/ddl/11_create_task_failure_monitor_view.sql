-- MARTS.VW_TASK_FAILURE_MONITOR
--
-- TASK_REFRESH_MARTS, TASK_REFRESH_FRAUD_SCORES, and TASK_RECONCILE_FRAUD_OUTCOMES
-- (snowflake/tasks/task_refresh_marts.sql, snowflake/tasks/task_reconcile_fraud_outcomes.sql)
-- currently fail silently from an operator's point of view: a task that errors out just
-- stops advancing its downstream table, and that only shows up indirectly -- e.g. as
-- `CONFIRMED_FRAUD_OUTCOMES not growing` or `VW_ACCOUNT_VELOCITY_TRIAGE_QUEUE` going thin
-- (see docs/runbook.md's Common incidents table) -- well after the actual failure. This
-- mirrors the `adf_pipeline_failure` log-based alert (terraform/modules/monitoring) one
-- layer down the stack, surfacing the same class of failure for the warehouse-side task
-- graph instead of the orchestration-side pipeline runs.
--
-- Built on ACCOUNT_USAGE.TASK_HISTORY rather than INFORMATION_SCHEMA.TASK_HISTORY: the
-- INFORMATION_SCHEMA table function only looks back 7 days and requires an explicit
-- SCHEDULED_TIME_RANGE_START argument per call, which doesn't compose into a plain
-- queryable view. ACCOUNT_USAGE.TASK_HISTORY trades that for its normal up-to-120-minute
-- replication lag -- acceptable here since this view is for daily/on-call triage, not
-- real-time paging (a future alert on top of this, if added, should account for that lag
-- in its evaluation window).

USE SCHEMA FRAUD_PLATFORM.MARTS;

CREATE OR REPLACE VIEW VW_TASK_FAILURE_MONITOR AS
SELECT
  name                                                AS task_name,
  database_name,
  schema_name,
  state,
  error_code,
  error_message,
  scheduled_time,
  query_start_time,
  completed_time,
  graph_run_group_id,
  return_value
FROM TABLE(SNOWFLAKE.ACCOUNT_USAGE.TASK_HISTORY())
WHERE database_name = 'FRAUD_PLATFORM'
  AND schema_name = 'MARTS'
  AND name IN ('TASK_REFRESH_MARTS', 'TASK_REFRESH_FRAUD_SCORES', 'TASK_RECONCILE_FRAUD_OUTCOMES')
  AND state = 'FAILED'
  AND scheduled_time >= DATEADD(day, -7, CURRENT_TIMESTAMP())
ORDER BY scheduled_time DESC;

-- Same-graph-run lens: when TASK_REFRESH_MARTS (the root task) fails, TASK_REFRESH_FRAUD_SCORES
-- never runs at all rather than itself failing, since its `AFTER` dependency is never
-- satisfied -- that looks identical to "nothing to do today" unless an operator knows to
-- check the root task first. This view flags exactly that case: a failed run with no
-- matching child-task row in the same graph_run_group_id.
CREATE OR REPLACE VIEW VW_TASK_FAILURE_CASCADE_CHECK AS
SELECT
  root.graph_run_group_id,
  root.scheduled_time        AS root_failed_at,
  root.error_code            AS root_error_code,
  root.error_message         AS root_error_message,
  NOT EXISTS (
    SELECT 1
    FROM VW_TASK_FAILURE_MONITOR child
    WHERE child.graph_run_group_id = root.graph_run_group_id
      AND child.task_name = 'TASK_REFRESH_FRAUD_SCORES'
  )                           AS fraud_scores_never_ran
FROM VW_TASK_FAILURE_MONITOR root
WHERE root.task_name = 'TASK_REFRESH_MARTS'
ORDER BY root.scheduled_time DESC;
