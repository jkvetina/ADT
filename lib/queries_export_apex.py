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

apex_export_start = """
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
        --
        APEX_SESSION.CREATE_SESSION (
            p_app_id                    => :app_id,
            p_page_id                   => 0,
            p_username                  => c.workspace,
            p_call_post_authentication  => FALSE
        );
        --
        APEX_COLLECTION.CREATE_COLLECTION (
            p_collection_name       => 'ADT_APEX_EXPORT',
            p_truncate_if_exists    => 'YES'
        );
        COMMIT;
    END LOOP;
END;
"""

apex_export_full = """
DECLARE
    l_files         apex_t_export_files;
BEGIN
    l_files := APEX_EXPORT.GET_APPLICATION (
        p_application_id        => :app_id,
        p_split                 => FALSE,
        p_with_date             => FALSE,
        p_with_original_ids     => (:originals = 'Y'),
        p_with_comments         => FALSE
    );
    --
    FOR i IN l_files.FIRST .. l_files.LAST LOOP
        APEX_COLLECTION.ADD_MEMBER (
            p_collection_name   => 'ADT_APEX_EXPORT',
            p_c001              => l_files(i).name,
            p_clob001           => l_files(i).contents
        );
    END LOOP;
    COMMIT;
END;
"""

apex_export_split = """
DECLARE
    l_files         apex_t_export_files;
BEGIN
    l_files := APEX_EXPORT.GET_APPLICATION (
        p_application_id        => :app_id,
        p_split                 => TRUE,
        p_type                  => 'APPLICATION_SOURCE,READABLE_YAML,EMBEDDED_CODE',
        p_with_date             => FALSE,
        p_with_translations     => TRUE,
        p_with_original_ids     => (:originals = 'Y'),
        p_with_comments         => FALSE
    );
    --
    FOR i IN l_files.FIRST .. l_files.LAST LOOP
        IF (l_files(i).name LIKE '%/files/%' OR l_files(i).name LIKE '%/app_static_files/%') THEN     -- ignore files
            CONTINUE;
        END IF;
        --
        APEX_COLLECTION.ADD_MEMBER (
            p_collection_name   => 'ADT_APEX_EXPORT',
            p_c001              => l_files(i).name,
            p_clob001           => l_files(i).contents
        );
    END LOOP;
    COMMIT;
END;
"""

apex_export_recent = """
DECLARE
    l_files         apex_t_export_files;
BEGIN
    l_files := APEX_EXPORT.GET_APPLICATION (
        p_application_id        => :app_id,
        p_split                 => TRUE,
        p_type                  => 'APPLICATION_SOURCE,READABLE_YAML',
        p_with_date             => FALSE,
        p_with_translations     => TRUE,
        p_with_original_ids     => (:originals = 'Y'),
        p_with_comments         => FALSE,
        p_components            => APEX_STRING.SPLIT(:components, ',')
    );
    --
    FOR i IN l_files.FIRST .. l_files.LAST LOOP
        IF (l_files(i).name LIKE '%/files/%' OR l_files(i).name LIKE '%/app_static_files/%') THEN     -- ignore files
            CONTINUE;
        END IF;
        --
        APEX_COLLECTION.ADD_MEMBER (
            p_collection_name   => 'ADT_APEX_EXPORT',
            p_c001              => l_files(i).name,
            p_clob001           => l_files(i).contents
        );
    END LOOP;
    COMMIT;
END;
"""

apex_export_recent_list = """
SELECT
    a.type_name,
    a.id,
    a.name
    --a.used_on_pages
FROM apex_appl_export_comps a
WHERE a.application_id      = :app_id
    AND (a.last_updated_on  >= TRUNC(SYSDATE) + 1 - :recent OR :recent IS NULL)
    AND (a.last_updated_by  = :author OR :author IS NULL)
ORDER BY
    a.type_name,
    CASE WHEN a.type_name = 'PAGE'
        THEN LPAD(a.id, 8, '0')
        ELSE a.name
        END
"""

apex_export_fetch_files = """
SELECT
    c.seq_id,
    c.c001      AS file_name,
    c.clob001   AS clob_content
FROM apex_collections c
WHERE c.collection_name = 'ADT_APEX_EXPORT'
"""



# get authentication schemes
apex_authentication_schemes = """
SELECT
    a.authentication_scheme_id AS authentication_id,
    a.authentication_scheme_name || ' (' || a.scheme_type || ')' AS authentication_name
FROM apex_application_auth a
WHERE a.application_id = :app_id
"""

# export APEX files in as a binary
apex_files = """
SELECT
    f.filename,
    f.blob_content
FROM wwv_flow_files f
WHERE f.flow_id                 = :app_id
    AND NVL(f.created_by, '-')  NOT IN ('SYS')
    AND f.content_type          IS NULL
"""

# upload file to application static files
apex_upload_app_file = """
BEGIN
    WWV_FLOW_API.CREATE_APP_STATIC_FILE (
        p_flow_id       => :app_id,
        p_file_name     => :name,
        p_mime_type     => :mime,
        p_file_charset  => 'utf-8',
        p_file_content  => :payload
    );
    COMMIT;
END;
"""

# upload file to application static files
apex_upload_ws_file = """
BEGIN
    WWV_FLOW_API.CREATE_WORKSPACE_STATIC_FILE (
        p_file_name     => :name,
        p_mime_type     => :mime,
        p_file_charset  => 'utf-8',
        p_file_content  => :payload
    );
    COMMIT;
END;
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

page_comments = """
SELECT
    t.page_id,
    t.page_name,
    t.last_updated_by,
    t.last_updated_on,
    t.page_comment
FROM apex_application_pages t
WHERE t.application_id = :app_id
    AND t.page_comment IS NOT NULL
"""

page_region_comments = """
SELECT
    t.page_id,
    t.page_name,
    t.region_id,
    t.region_name,
    t.last_updated_by,
    t.last_updated_on,
    t.component_comment
    --t.display_sequence
FROM apex_application_page_regions t
WHERE t.application_id = :app_id
    AND t.component_comment IS NOT NULL
"""
