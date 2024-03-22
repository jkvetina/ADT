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

# translate ids to more meaningful names
apex_id_names = """
SELECT
    t.authorization_scheme_id       AS component_id,
    t.authorization_scheme_name     AS component_name,
    'AUTHORIZATION'                 AS component_type
FROM apex_application_authorization t
WHERE t.application_id = :app_id
--
UNION ALL
SELECT
    t.lov_id,
    t.list_of_values_name,
    'LOV'
FROM apex_application_lovs t
WHERE t.application_id = :app_id
--
UNION ALL
SELECT
    t.group_id,
    t.page_group_name,
    'PAGE GROUP'
FROM apex_application_page_groups t
WHERE t.application_id = :app_id
--
UNION ALL
SELECT
    t.list_id,
    t.list_name,
    'LIST'
FROM apex_application_lists t
WHERE t.application_id = :app_id
--
UNION ALL
SELECT
    t.breadcrumb_id,
    t.breadcrumb_name,
    'BREADCRUMB'
FROM apex_application_breadcrumbs t
WHERE t.application_id = :app_id
--
UNION ALL
SELECT
    t.email_template_id,
    t.name,
    'EMAIL TEMPLATE'
FROM apex_appl_email_templates t
WHERE t.application_id = :app_id
"""

# get list of developers
workspace_developers = """
SELECT
    d.workspace_name    AS workspace,
    d.user_name,
    d.email             AS user_mail
FROM apex_workspace_developers d
WHERE 1 = 1
    AND d.is_application_developer = 'Yes'
    AND d.account_locked = 'No'
    --AND (d.account_expiry > TRUNC(SYSDATE) OR d.account_expiry IS NULL)
    AND d.email NOT LIKE 'dba@%'
    AND d.date_last_updated > TRUNC(SYSDATE) - 90
GROUP BY
    d.workspace_name,
    d.user_name,
    d.email
ORDER BY 1, 2
"""

