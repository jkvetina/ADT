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
    a.application_id
"""

# setup APEX security context to access APEX views
apex_security_context = """
BEGIN
    FOR c IN (
        SELECT a.workspace
        FROM apex_applications a
        WHERE a.application_id = :app_id
    ) LOOP
        APEX_UTIL.SET_WORKSPACE (
            p_workspace => c.workspace
        );
        APEX_UTIL.SET_SECURITY_GROUP_ID (
            p_security_group_id => APEX_UTIL.FIND_SECURITY_GROUP_ID(p_workspace => c.workspace)
        );
    END LOOP;
END;
"""

# export APEX files in as a binary
apex_files = """
SELECT f.filename, f.blob_content f
FROM wwv_flow_files f
WHERE f.flow_id                 = :app_id
    AND NVL(f.created_by, '-')  NOT IN ('SYS')
    AND f.content_type          IS NULL
"""

