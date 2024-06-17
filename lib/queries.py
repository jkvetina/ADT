matching_objects = """
WITH objects_prefix AS (
    SELECT /*+ MATERIALIZE CARDINALITY(t 1) */
        t.column_value AS object_like
    FROM TABLE(APEX_STRING.SPLIT(TRIM(BOTH ',' FROM :objects_prefix), ',')) t
),
objects_types AS (
    SELECT /*+ MATERIALIZE CARDINALITY(t 10) */
        t.column_value AS object_like
    FROM TABLE(APEX_STRING.SPLIT(TRIM(BOTH ',' FROM :object_type), ',')) t
),
objects_names AS (
    SELECT /*+ MATERIALIZE CARDINALITY(t 10) */
        t.column_value AS object_like
    FROM TABLE(APEX_STRING.SPLIT(TRIM(BOTH ',' FROM :object_name), ',')) t
),
objects_ignore AS (
    SELECT /*+ MATERIALIZE CARDINALITY(t 10) */
        t.column_value AS object_like
    FROM TABLE(APEX_STRING.SPLIT(TRIM(BOTH ',' FROM :objects_ignore), ',')) t
)
SELECT DISTINCT
    o.object_type,
    o.object_name,
    t.tablespace_name,
    t.partitioned,
    t.global_stats
FROM user_objects o
LEFT JOIN user_tables t
    ON t.table_name         = o.object_name
    AND o.object_type       = 'TABLE'
JOIN objects_prefix a
    ON o.object_name        LIKE a.object_like ESCAPE '\\'
JOIN objects_types p
    ON o.object_type        LIKE p.object_like ESCAPE '\\'
    AND o.object_type       NOT IN ('LOB', 'TABLE PARTITION', 'INDEX', 'INDEX PARTITION', 'JOB', 'CREDENTIAL')
JOIN objects_names n
    ON o.object_name        LIKE n.object_like ESCAPE '\\'
LEFT JOIN objects_ignore g
    ON o.object_name        LIKE g.object_like ESCAPE '\\'
WHERE 1 = 1
    AND g.object_like       IS NULL
    AND o.object_name       NOT LIKE 'SYS\\_%' ESCAPE '\\'
    AND o.object_name       NOT LIKE 'ISEQ$$_%'
    AND o.object_name       NOT LIKE 'ST%='
    AND (o.last_ddl_time    >= TRUNC(SYSDATE) + 1 - :recent OR :recent IS NULL)
    AND (o.object_type, o.object_name) NOT IN (
        SELECT
            'TABLE'         AS object_type,
            m.mview_name    AS object_name
        FROM user_mviews m
    )
--
UNION ALL
SELECT
    'JOB'           AS object_type,
    j.job_name      AS object_name,
    NULL            AS tablespace_name,
    NULL            AS partitioned,
    NULL            AS global_stats
FROM user_scheduler_jobs j
JOIN objects_prefix a
    ON j.job_name           LIKE a.object_like ESCAPE '\\'
JOIN objects_names n
    ON j.job_name           LIKE n.object_like ESCAPE '\\'
LEFT JOIN objects_ignore g
    ON j.job_name           LIKE g.object_like ESCAPE '\\'
WHERE 1 = 1
    AND g.object_like       IS NULL
    AND :recent             IS NULL
    AND (:object_type       LIKE 'J%' OR :object_type LIKE '%,J%' OR NULLIF(:object_type, '%') IS NULL)
    AND j.schedule_type     != 'IMMEDIATE'
--
UNION ALL
SELECT
    'MVIEW LOG'             AS object_type,
    l.master                AS object_name,
    NULL                    AS tablespace_name,
    NULL                    AS partitioned,
    NULL                    AS global_stats
FROM user_mview_logs l
JOIN objects_prefix a
    ON l.master             LIKE a.object_like ESCAPE '\\'
JOIN objects_names n
    ON l.master             LIKE n.object_like ESCAPE '\\'
LEFT JOIN objects_ignore g
    ON l.master             LIKE g.object_like ESCAPE '\\'
WHERE 1 = 1
    AND g.object_like       IS NULL
    AND :recent             IS NULL
    AND (:object_type       LIKE 'M%' OR :object_type LIKE '%,M%' OR NULLIF(:object_type, '%') IS NULL)
--
UNION ALL
SELECT
    'INDEX'             AS object_type,
    t.index_name        AS object_name,
    t.tablespace_name,
    t.partitioned,
    t.global_stats
FROM user_indexes t
LEFT JOIN user_constraints c
    ON c.table_name         = t.table_name
    AND c.constraint_name   = t.index_name
    AND c.constraint_type   IN ('P', 'U')
JOIN objects_prefix a
    ON (
        t.index_name        LIKE a.object_like ESCAPE '\\'
        OR t.table_name     LIKE a.object_like ESCAPE '\\'
    )
JOIN objects_names n
    ON (
        t.index_name        LIKE n.object_like ESCAPE '\\'
        OR t.table_name     LIKE n.object_like ESCAPE '\\'
    )
LEFT JOIN objects_ignore g
    ON (
        t.index_name        LIKE g.object_like ESCAPE '\\'
        OR t.table_name     LIKE g.object_like ESCAPE '\\'
    )
WHERE 1 = 1
    AND g.object_like       IS NULL
    AND (:object_type       LIKE 'I%' OR :object_type LIKE '%,I%' OR NULLIF(:object_type, '%') IS NULL)
    AND t.index_name        NOT LIKE 'SYS%$$'
    AND t.generated         = 'N'
    AND t.constraint_index  = 'NO'
    AND (t.last_analyzed    >= TRUNC(SYSDATE) + 1 - :recent OR :recent IS NULL)
    AND c.constraint_name   IS NULL
"""

# get database objects overview
overview = """
WITH objects_add AS (
    SELECT /*+ MATERIALIZE CARDINALITY(t 1) */
        t.column_value AS object_like
    FROM TABLE(APEX_STRING.SPLIT(TRIM(BOTH ',' FROM NVL(:objects_prefix, '%')), ',')) t
),
objects_ignore AS (
    SELECT /*+ MATERIALIZE CARDINALITY(t 10) */
        t.column_value AS object_like
    FROM TABLE(APEX_STRING.SPLIT(TRIM(BOTH ',' FROM :objects_ignore), ',')) t
)
SELECT
    o.object_type,
    COUNT(*) AS total,
    NULL AS fixed,
    SUM(CASE WHEN o.status != 'VALID' THEN 1 ELSE 0 END) AS invalid
FROM user_objects o
JOIN objects_add a
    ON o.object_name        LIKE a.object_like ESCAPE '\\'
LEFT JOIN objects_ignore g
    ON o.object_name        LIKE g.object_like ESCAPE '\\'
WHERE 1 = 1
    AND g.object_like       IS NULL
    AND o.object_type       IN ('PACKAGE', 'PACKAGE BODY', 'PROCEDURE', 'FUNCTION', 'TRIGGER', 'VIEW', 'MATERIALIZED VIEW', 'SYNONYM', 'TYPE', 'TYPE BODY')
    AND (o.object_type      LIKE :object_type ESCAPE '\\' OR :object_type IS NULL)
    AND (o.object_name      LIKE :object_name ESCAPE '\\' OR :object_name IS NULL)
GROUP BY o.object_type
--
UNION ALL
SELECT
    'MVIEW LOG' AS object_type,
    COUNT(*)    AS total,
    NULL        AS fixed,
    NULL        AS invalid
FROM user_mview_logs l
JOIN objects_add a
    ON REPLACE(l.log_table, 'MLOG$_') LIKE a.object_like ESCAPE '\\'
LEFT JOIN objects_ignore g
    ON REPLACE(l.log_table, 'MLOG$_') LIKE g.object_like ESCAPE '\\'
WHERE 1 = 1
    AND g.object_like       IS NULL
    AND REPLACE(l.log_table, 'MLOG$_') LIKE :object_name ESCAPE '\\'
    AND (:object_type LIKE 'M%' OR :object_type IS NULL)
HAVING COUNT(*) > 0
ORDER BY 1
"""

# get database objects to recompile
objects_to_recompile = """
WITH objects_add AS (
    SELECT /*+ MATERIALIZE CARDINALITY(t 1) */
        t.column_value AS object_like
    FROM TABLE(APEX_STRING.SPLIT(TRIM(BOTH ',' FROM NVL(:objects_prefix, '%')), ',')) t
),
objects_ignore AS (
    SELECT /*+ MATERIALIZE CARDINALITY(t 10) */
        t.column_value AS object_like
    FROM TABLE(APEX_STRING.SPLIT(TRIM(BOTH ',' FROM :objects_ignore), ',')) t
)
SELECT
    o.object_type,
    o.object_name
FROM (
    SELECT
        o.object_type,
        o.object_name
    FROM user_objects o
    JOIN objects_add a
        ON o.object_name        LIKE a.object_like ESCAPE '\\'
    LEFT JOIN objects_ignore g
        ON o.object_name        LIKE g.object_like ESCAPE '\\'
    WHERE 1 = 1
        AND g.object_like       IS NULL
        AND o.status            != 'VALID'
        AND o.object_type       NOT IN ('SEQUENCE')
        AND (o.object_type      LIKE :object_type ESCAPE '\\' OR :object_type IS NULL)
        AND (o.object_name      LIKE :object_name ESCAPE '\\' OR :object_name IS NULL)
    --
    UNION ALL
    SELECT
        o.object_type,
        o.object_name
    FROM user_objects o
    JOIN objects_add a
        ON o.object_name        LIKE a.object_like ESCAPE '\\'
    LEFT JOIN objects_ignore g
        ON o.object_name        LIKE g.object_like ESCAPE '\\'
    WHERE 1 = 1
        AND g.object_like       IS NULL
        AND :force              = 'Y'
        AND o.object_type       IN ('PACKAGE', 'PACKAGE BODY', 'PROCEDURE', 'FUNCTION', 'TRIGGER', 'VIEW', 'MATERIALIZED VIEW', 'SYNONYM', 'TYPE', 'TYPE BODY')
        AND (o.object_type      LIKE :object_type ESCAPE '\\' OR :object_type IS NULL)
        AND (o.object_name      LIKE :object_name ESCAPE '\\' OR :object_name IS NULL)
) o
ORDER BY CASE o.object_type
    WHEN 'TYPE'                 THEN 1
    WHEN 'PACKAGE'              THEN 2
    WHEN 'PROCEDURE'            THEN 3
    WHEN 'FUNCTION'             THEN 4
    WHEN 'TRIGGER'              THEN 5
    WHEN 'PACKAGE BODY'         THEN 7
    WHEN 'TYPE BODY'            THEN 8
    WHEN 'MATERIALIZED VIEW'    THEN 9
    ELSE                             6 END, o.object_name
"""

# get summary of errors
objects_errors_summary = """
WITH objects_add AS (
    SELECT /*+ MATERIALIZE CARDINALITY(t 1) */
        t.column_value AS object_like
    FROM TABLE(APEX_STRING.SPLIT(TRIM(BOTH ',' FROM NVL(:objects_prefix, '%')), ',')) t
),
objects_ignore AS (
    SELECT /*+ MATERIALIZE CARDINALITY(t 10) */
        t.column_value AS object_like
    FROM TABLE(APEX_STRING.SPLIT(TRIM(BOTH ',' FROM :objects_ignore), ',')) t
)
SELECT
    e.type          AS object_type,
    e.name          AS object_name,
    COUNT(e.line)   AS errors,
    COALESCE(
        MIN(REGEXP_SUBSTR(e.text, 'ORA-\\d+')),
        MIN(REGEXP_SUBSTR(e.text, 'PLS-\\d+'))
    ) AS error
FROM user_errors e
JOIN objects_add a
    ON e.name       LIKE a.object_like ESCAPE '\\'
LEFT JOIN objects_ignore g
    ON e.name       LIKE g.object_like ESCAPE '\\'
WHERE 1 = 1
    AND g.object_like   IS NULL
    AND (e.type         LIKE :object_type ESCAPE '\\' OR :object_type IS NULL)
    AND (e.name         LIKE :object_name ESCAPE '\\' OR :object_name IS NULL)
    AND e.text          NOT LIKE 'PLW%'     -- skip warnings
GROUP BY
    e.type,
    e.name
ORDER BY 1, 2
"""

object_dependencies = """
WITH objects_add AS (
    SELECT /*+ MATERIALIZE CARDINALITY(t 1) */
        t.column_value AS object_like
    FROM TABLE(APEX_STRING.SPLIT(TRIM(BOTH ',' FROM NVL(:objects_prefix, '%')), ',')) t
),
objects_ignore AS (
    SELECT /*+ MATERIALIZE CARDINALITY(t 10) */
        t.column_value AS object_like
    FROM TABLE(APEX_STRING.SPLIT(TRIM(BOTH ',' FROM :objects_ignore), ',')) t
)
SELECT
    t.object_name,
    t.object_type,
    t.referenced_name,
    t.referenced_type
FROM (
    SELECT
        t.sequence_name         AS object_name,
        'SEQUENCE'              AS object_type,
        NULL                    AS referenced_name,
        NULL                    AS referenced_type
    FROM user_sequences t
    JOIN objects_add a
        ON t.sequence_name      LIKE a.object_like ESCAPE '\\'
    LEFT JOIN objects_ignore g
        ON t.sequence_name      LIKE g.object_like ESCAPE '\\'
    WHERE 1 = 1
        AND g.object_like       IS NULL
        AND t.sequence_name     NOT LIKE 'ISEQ$$%'
    --
    UNION ALL
    SELECT
        t.table_name            AS object_name,
        'TABLE'                 AS object_type,
        NULL                    AS referenced_name,
        NULL                    AS referenced_type
    FROM user_tables t
    JOIN objects_add a
        ON t.table_name         LIKE a.object_like ESCAPE '\\'
    LEFT JOIN objects_ignore g
        ON t.table_name         LIKE g.object_like ESCAPE '\\'
    WHERE 1 = 1
        AND g.object_like       IS NULL
    --
    UNION ALL
    SELECT
        t.index_name            AS object_name,
        'INDEX'                 AS object_type,
        NULL                    AS referenced_name,
        NULL                    AS referenced_type
    FROM user_indexes t
    JOIN objects_add a
        ON t.index_name         LIKE a.object_like ESCAPE '\\'
    LEFT JOIN objects_ignore g
        ON t.index_name         LIKE g.object_like ESCAPE '\\'
    WHERE 1 = 1
        AND g.object_like       IS NULL
    --
    UNION ALL
    SELECT
        c.table_name            AS object_name,
        'TABLE'                 AS object_type,
        r.table_name            AS referenced_name,
        'TABLE'                 AS referenced_type
    FROM user_constraints c
    JOIN user_constraints r
        ON r.constraint_name    = c.r_constraint_name
        AND r.owner             = c.owner
    JOIN objects_add a
        ON c.table_name         LIKE a.object_like ESCAPE '\\'
    LEFT JOIN objects_ignore g
        ON c.table_name         LIKE g.object_like ESCAPE '\\'
    WHERE 1 = 1
        AND g.object_like       IS NULL
        AND c.table_name        != r.table_name
        AND c.constraint_type   = 'R'
        AND c.owner             = c.r_owner
        AND c.status            = 'ENABLED'
    GROUP BY
        c.table_name,
        r.table_name
    --
    UNION ALL
    SELECT
        o.object_name,
        o.object_type,
        NULL                    AS referenced_name,
        NULL                    AS referenced_type
    FROM user_objects o
    JOIN objects_add a
        ON o.object_name        LIKE a.object_like ESCAPE '\\'
    LEFT JOIN objects_ignore g
        ON o.object_name        LIKE g.object_like ESCAPE '\\'
    WHERE 1 = 1
        AND g.object_like       IS NULL
        AND o.object_type       IN ('PACKAGE', 'PACKAGE BODY', 'PROCEDURE', 'FUNCTION', 'TRIGGER', 'VIEW', 'MATERIALIZED VIEW', 'SYNONYM', 'TYPE', 'TYPE BODY')
    --
    UNION ALL
    SELECT
        d.name                  AS object_name,
        d.type                  AS object_type,
        d.referenced_name,
        d.referenced_type
    FROM user_dependencies d
    JOIN objects_add a
        ON d.name               LIKE a.object_like ESCAPE '\\'
    LEFT JOIN objects_ignore g
        ON d.name               LIKE g.object_like ESCAPE '\\'
    JOIN objects_add a2
        ON d.referenced_name    LIKE a2.object_like ESCAPE '\\'
    LEFT JOIN objects_ignore g2
        ON d.referenced_name    LIKE g2.object_like ESCAPE '\\'
    WHERE 1 = 1
        AND g.object_like       IS NULL
        AND g2.object_like      IS NULL
        AND d.referenced_owner  = USER
        AND d.referenced_type   NOT IN ('TABLE', 'SEQUENCE')
    --
    UNION ALL
    SELECT
        t.job_name              AS object_name,
        'JOB'                   AS object_type,
        NULL                    AS referenced_name,
        NULL                    AS referenced_type
    FROM user_scheduler_jobs t
    JOIN objects_add a
        ON t.job_name           LIKE a.object_like ESCAPE '\\'
    LEFT JOIN objects_ignore g
        ON t.job_name           LIKE g.object_like ESCAPE '\\'
    WHERE 1 = 1
        AND g.object_like       IS NULL
        AND t.job_creator       NOT IN ('APEX_PUBLIC_USER', 'SYS')
) t
ORDER BY
    CASE t.object_type
        WHEN 'SEQUENCE'             THEN 1
        WHEN 'TABLE'                THEN 2
        WHEN 'TYPE'                 THEN 3
        WHEN 'TYPE BODY'            THEN 4
        WHEN 'PACKAGE'              THEN 5
        WHEN 'PACKAGE BODY'         THEN 7
        WHEN 'TRIGGER'              THEN 8
        WHEN 'MATERIALIZED VIEW'    THEN 9
        ELSE 6 END,
    1,
    2,
    3 NULLS FIRST,
    4 NULLS FIRST
"""

# used in APEX searching
referenced_objects = """
SELECT
    p.page_id,
    'PROCESS:' || p.process_point_code  AS source,
    p.attribute_02                      AS owner,
    p.attribute_03                      AS object_name,
    p.attribute_04                      AS module_name
FROM apex_application_page_proc p
WHERE p.application_id          = :app_id
    AND p.process_type_code     = 'NATIVE_INVOKE_API'
--
UNION ALL
SELECT
    t.page_id,
    'REGION:' || t.region_name      AS source,
    t.table_owner                   AS owner,
    t.table_name                    AS object_name,
    NULL                            AS module_name
FROM apex_application_page_regions t
WHERE t.application_id          = :app_id
    AND t.location_code         = 'LOCAL'
    AND t.table_name            IS NOT NULL
--
UNION ALL
SELECT
    p.page_id,
    'LOV:' || t.list_of_values_name AS source,
    t.table_owner                   AS owner,
    t.table_name                    AS object_name,
    NULL                            AS module_name
FROM apex_application_lovs t
LEFT JOIN (
    SELECT                      -- IG columns
        g.lov_id,
        g.page_id
    FROM apex_appl_page_ig_columns g
    WHERE g.application_id      = :app_id
        AND g.lov_id            IS NOT NULL
    --
    UNION ALL
    SELECT                      -- IG filters
        g.lov_id,
        g.page_id
    FROM apex_appl_page_ig_columns g
    WHERE g.application_id      = :app_id
        AND g.filter_lov_id     IS NOT NULL
) p
    ON p.lov_id                 = t.lov_id
WHERE t.application_id          = :app_id
    AND t.location_code         = 'LOCAL'
    AND t.source_type_code      = 'TABLE'
    AND t.table_name            IS NOT NULL
--
UNION ALL
SELECT DISTINCT
    p.page_id,
    'LOV:' || t.list_of_values_name AS source,
    t.table_owner                   AS owner,
    t.table_name                    AS object_name,
    NULL                            AS module_name
FROM apex_application_lovs t
JOIN (
    SELECT          -- page items
        t.lov_named_lov AS lov_name,
        t.page_id
    FROM apex_application_page_items t
    WHERE t.application_id      = :app_id
        AND t.lov_named_lov     IS NOT NULL
    --
    UNION ALL
    SELECT                      -- IR columns
        t.named_lov,            -- also rpt_lov
        t.page_id
    FROM apex_application_page_ir_col t
    WHERE t.application_id      = :app_id
        AND t.named_lov         IS NOT NULL
    --
    UNION ALL
    SELECT                      -- classic report columns
        t.named_list_of_values, -- also inline_list_of_values
        t.page_id
    FROM apex_application_page_rpt_cols t
    WHERE t.application_id          = :app_id
        AND t.named_list_of_values  IS NOT NULL
) p
    ON p.lov_name               = t.list_of_values_name
WHERE t.application_id          = :app_id
    AND t.location_code         = 'LOCAL'
    AND t.source_type_code      = 'TABLE'
    AND t.table_name            IS NOT NULL
--
ORDER BY
    source,
    page_id,
    owner,
    object_name
"""



# grants made by current schema
grants_made = """
WITH objects_add AS (
    SELECT /*+ MATERIALIZE CARDINALITY(t 1) */
        t.column_value AS object_like
    FROM TABLE(APEX_STRING.SPLIT(TRIM(BOTH ',' FROM NVL(:objects_prefix, '%')), ',')) t
),
objects_ignore AS (
    SELECT /*+ MATERIALIZE CARDINALITY(t 10) */
        t.column_value AS object_like
    FROM TABLE(APEX_STRING.SPLIT(TRIM(BOTH ',' FROM :objects_ignore), ',')) t
)
SELECT
    t.type,
    t.table_name,
    APEX_STRING.FORMAT (
        'GRANT %0 ON %1 TO %2%3;',
        t.privs,
        LOWER(t.table_name),
        LOWER(t.grantee),
        CASE WHEN t.grantable = 'YES' THEN ' WITH GRANT OPTION' END
    ) AS sql
FROM (
    SELECT
        t.type,
        t.table_name,
        LISTAGG(DISTINCT t.privilege, ', ') WITHIN GROUP (ORDER BY t.privilege) AS privs,
        LISTAGG(DISTINCT t.grantee, ', ')   WITHIN GROUP (ORDER BY t.grantee)   AS grantee,
        t.grantable
    FROM user_tab_privs_made t
    JOIN objects_add a
        ON t.table_name     LIKE a.object_like ESCAPE '\\'
    LEFT JOIN objects_ignore g
        ON t.table_name     LIKE g.object_like ESCAPE '\\'
    WHERE 1 = 1
        AND g.object_like   IS NULL
        AND t.table_name    NOT LIKE 'ST%='
        AND t.table_name    NOT LIKE 'BIN$%'
        AND t.grantor       = USER
        AND t.type          NOT IN ('USER')
    GROUP BY
        t.type,
        t.table_name,
        t.grantable
) t
ORDER BY 1, 2, 3
"""

# grants received by current schema
grants_recd = """
SELECT
    t.owner,
    t.type,
    t.table_name,
    APEX_STRING.FORMAT (
        'GRANT %0 ON %1 TO %2%3;',
        t.privilege,
        LOWER(t.table_name),
        LOWER(USER),
        CASE WHEN t.grantable = 'YES' THEN ' WITH GRANT OPTION' END
    ) AS sql
FROM user_tab_privs_recd t
WHERE t.type            NOT IN ('USER')
    AND t.table_name    NOT LIKE 'BIN$%'
ORDER BY 1, 2, 3
"""

switch_schema = 'ALTER SESSION SET CURRENT_SCHEMA = {};\n'

# grants used to create user
user_roles = """
SELECT
    'GRANT ' || RPAD(p.granted_role, 21) || ' TO ' || LOWER(p.username) || ';' AS line
FROM user_role_privs p
ORDER BY 1
"""
#
user_privs = """
SELECT
    'GRANT ' || RPAD(p.privilege, 33) || ' TO ' || LOWER(p.username) || ';' AS line
FROM user_sys_privs p
ORDER BY 1
"""

# export directories
directories = """
SELECT
    'CREATE OR REPLACE DIRECTORY ' || LOWER(d.owner) || '.' || RPAD(LOWER(d.directory_name), 31) || ' AS ''' || d.directory_path || ''';' AS line
FROM all_directories d
ORDER BY 1
"""



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



describe_object = """
SELECT DBMS_METADATA.GET_DDL(REPLACE(o.object_type, ' ', '_'), o.object_name) AS object_desc
FROM user_objects o
WHERE o.object_type     = :object_type
    AND o.object_name   = :object_name
"""

describe_mview_log = """
SELECT DBMS_METADATA.GET_DDL('MATERIALIZED_VIEW_LOG', l.log_table) AS object_desc
FROM user_mview_logs l
WHERE l.log_table = :object_name
"""

# export jobs
describe_job = """
SELECT DBMS_METADATA.GET_DDL('PROCOBJ', job_name) AS object_desc
FROM user_scheduler_jobs
WHERE job_name = :object_name
"""

describe_job_details = """
SELECT job_name, enabled, job_priority
FROM user_scheduler_jobs j
WHERE j.job_name = :job_name"""

describe_job_args = """
SELECT
    j.argument_name,
    j.argument_position,
    j.argument_type,
    j.value
FROM user_scheduler_job_args j
WHERE j.job_name = :job_name
ORDER BY j.argument_position"""

# template used to extract jobs
template_job = """
DECLARE
    in_job_name             CONSTANT VARCHAR2(128)  := '{job_name}';
    in_run_immediatelly     CONSTANT BOOLEAN        := FALSE;
BEGIN
    DBMS_OUTPUT.PUT_LINE('--');
    DBMS_OUTPUT.PUT_LINE('-- REPLACE JOB ' || UPPER(in_job_name));
    DBMS_OUTPUT.PUT_LINE('--');
    --
    BEGIN
        DBMS_SCHEDULER.DROP_JOB(in_job_name, TRUE);
    EXCEPTION
    WHEN OTHERS THEN
        NULL;
    END;
    --
    DBMS_SCHEDULER.CREATE_JOB (
{job_payload}
    );
    --{job_args}
    DBMS_SCHEDULER.SET_ATTRIBUTE(in_job_name, 'JOB_PRIORITY', {job_priority});
    {job_enabled}DBMS_SCHEDULER.ENABLE(in_job_name);
    COMMIT;
    --
    IF in_run_immediatelly THEN
        DBMS_SCHEDULER.RUN_JOB(in_job_name);
        COMMIT;
    END IF;
END;
/
"""

# drop object query
template_object_drop = """
BEGIN
    DBMS_UTILITY.EXEC_DDL_STATEMENT('DROP {object_type} {object_name}');
    DBMS_OUTPUT.PUT_LINE('--');
    DBMS_OUTPUT.PUT_LINE('-- DROP {object_type} {object_name}, DONE');
    DBMS_OUTPUT.PUT_LINE('--');
EXCEPTION
WHEN OTHERS THEN
    NULL;
END;
/
--\n"""



# get all compatible columns to export table to CSV
csv_columns = """
SELECT
    t.column_name,
    t.data_type,
    t.column_id,
    MIN(CASE WHEN n.constraint_name IS NOT NULL THEN c.position END) AS pk,
    MIN(CASE WHEN u.constraint_name IS NOT NULL THEN c.position END) AS uq
FROM user_tab_cols t
LEFT JOIN user_cons_columns c
    ON c.table_name         = t.table_name
    AND c.column_name       = t.column_name
LEFT JOIN user_constraints n
    ON n.table_name         = c.table_name
    AND n.constraint_name   = c.constraint_name
    AND n.constraint_type   = 'P'
LEFT JOIN (
    SELECT MIN(u.constraint_name) AS constraint_name
    FROM user_constraints u
    WHERE u.table_name          = UPPER(:table_name)
        AND u.constraint_type   = 'U'
) u
    ON u.constraint_name    = c.constraint_name
WHERE t.table_name          = UPPER(:table_name)
    AND t.column_id         > 0   -- ignore virtual and hidden columns
    AND t.data_type         NOT IN ('BLOB', 'CLOB', 'XMLTYPE', 'JSON')
GROUP BY
    t.column_name,
    t.data_type,
    t.column_id
ORDER BY
    t.column_id
"""

# template for MERGE statement from CSV file
template_csv_merge = """
BEGIN
    DBMS_OUTPUT.PUT_LINE('--');
    DBMS_OUTPUT.PUT_LINE('-- MERGE ' || UPPER('{table_name}'));
    DBMS_OUTPUT.PUT_LINE('--');
END;
/
--
{skip_delete}DELETE FROM {table_name}{where_filter};
--
MERGE INTO {table_name} t
USING (
    {csv_content_query}
) s
ON ({primary_cols_set})
{skip_update}WHEN MATCHED THEN
{skip_update}    UPDATE SET
{skip_update}        {non_primary_cols_set}
{skip_insert}WHEN NOT MATCHED THEN
{skip_insert}    INSERT (
{skip_insert}        {all_cols}
{skip_insert}    )
{skip_insert}    VALUES (
{skip_insert}        {all_values}
{skip_insert}    )
;
"""



setup_dbms_metadata = """
BEGIN
    DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'PARTITIONING',          TRUE);
    DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'PHYSICAL_PROPERTIES',   FALSE);
    DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'SEGMENT_ATTRIBUTES',    FALSE);
    DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'STORAGE',               FALSE);
    DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'TABLESPACE',            FALSE);
    DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'SQLTERMINATOR',         FALSE);
    DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'PRETTY',                TRUE);
END;"""

# get table comments
pull_comments = """
WITH objects_prefix AS (
    SELECT /*+ MATERIALIZE CARDINALITY(t 1) */
        t.column_value AS object_like
    FROM TABLE(APEX_STRING.SPLIT(TRIM(BOTH ',' FROM :objects_prefix), ',')) t
),
objects_types AS (
    SELECT /*+ MATERIALIZE CARDINALITY(t 10) */
        t.column_value AS object_like
    FROM TABLE(APEX_STRING.SPLIT(TRIM(BOTH ',' FROM :object_type), ',')) t
),
objects_names AS (
    SELECT /*+ MATERIALIZE CARDINALITY(t 10) */
        t.column_value AS object_like
    FROM TABLE(APEX_STRING.SPLIT(TRIM(BOTH ',' FROM :object_name), ',')) t
),
objects_ignore AS (
    SELECT /*+ MATERIALIZE CARDINALITY(t 10) */
        t.column_value AS object_like
    FROM TABLE(APEX_STRING.SPLIT(TRIM(BOTH ',' FROM :objects_ignore), ',')) t
)
SELECT
    o.object_type,
    m.table_name,
    NULL                    AS column_name,
    NULL                    AS column_full,
    m.comments,
    NULL                    AS column_id
FROM user_tab_comments m
JOIN user_objects o
    ON o.object_name        = m.table_name
    AND o.object_type       IN ('TABLE', 'VIEW', 'MATERIALIZED VIEW')
JOIN objects_prefix a
    ON o.object_name        LIKE a.object_like ESCAPE '\\'
JOIN objects_types p
    ON o.object_type        LIKE p.object_like ESCAPE '\\'
JOIN objects_names n
    ON o.object_name        LIKE n.object_like ESCAPE '\\'
LEFT JOIN objects_ignore g
    ON o.object_name        LIKE g.object_like ESCAPE '\\'
WHERE 1 = 1
    AND g.object_like       IS NULL
--
UNION ALL
SELECT
    NULL AS object_type,
    m.table_name,
    m.column_name,
    RPAD(LOWER(m.table_name || '.' || m.column_name), MAX(FLOOR(LENGTH(m.table_name || '.' || m.column_name) / 4) * 4 + 5) OVER (PARTITION BY m.table_name)) AS column_full,
    m.comments,
    c.column_id
FROM user_col_comments m
JOIN user_tab_cols c
    ON c.table_name         = m.table_name
    AND c.column_name       = m.column_name
JOIN user_objects o
    ON o.object_name        = m.table_name
    AND o.object_type       IN ('TABLE', 'VIEW', 'MATERIALIZED VIEW')
JOIN objects_prefix a
    ON o.object_name        LIKE a.object_like ESCAPE '\\'
JOIN objects_types p
    ON o.object_type        LIKE p.object_like ESCAPE '\\'
JOIN objects_names n
    ON o.object_name        LIKE n.object_like ESCAPE '\\'
LEFT JOIN objects_ignore g
    ON o.object_name        LIKE g.object_like ESCAPE '\\'
WHERE 1 = 1
    AND g.object_like       IS NULL
    AND (
        m.column_name       NOT IN (
            'UPDATED_BY', 'UPDATED_AT', 'CHANGED_BY', 'CHANGED_AT', 'CREATED_BY', 'CREATED_AT'
        )
        OR m.comments       IS NOT NULL
    )
ORDER BY 1, column_id NULLS FIRST
"""

