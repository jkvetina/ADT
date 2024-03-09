# get applications from the same schema
apex_applications = """
SELECT
    a.workspace,
    a.workspace_id,
    a.application_group     AS app_group,
    a.application_id        AS app_id,
    a.alias                 AS app_alias,
    a.application_name      AS app_name,
    a.pages,
    --a.version,
    TO_CHAR(a.last_updated_on, 'YYYY-MM-DD HH24:MI') AS updated_at
    --
FROM apex_applications a
WHERE 1 = 1
    AND a.owner                 = :owner
    AND (a.workspace            = :workspace    OR :workspace IS NULL)
    AND (a.application_group    = :group_id     OR :group_id IS NULL)
    --
    AND ('|' || :app_id || '|' LIKE '%|' || a.application_id || '|%' OR :app_id IS NULL)
ORDER BY
    a.application_group,
    a.application_id"""

