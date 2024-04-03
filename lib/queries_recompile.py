# get database objects overview
overview = """
SELECT
    o.object_type,
    COUNT(*) AS total,
    NULL AS fixed,
    SUM(CASE WHEN o.status != 'VALID' THEN 1 ELSE 0 END) AS invalid
FROM user_objects o
WHERE 1 = 1
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
WHERE 1 = 1
    AND REPLACE(l.log_table, 'MLOG$_') LIKE :object_name || '%' ESCAPE '\\'
    AND (:object_type LIKE 'M%' OR :object_type IS NULL)
HAVING COUNT(*) > 0
ORDER BY 1
"""

# get database objects to recompile
objects_to_recompile = """
SELECT
    o.object_type,
    o.object_name
FROM (
    SELECT
        o.object_type,
        o.object_name
    FROM user_objects o
    WHERE o.status              != 'VALID'
        AND o.object_type       NOT IN ('SEQUENCE')
        AND (o.object_type      LIKE :object_type ESCAPE '\\' OR :object_type IS NULL)
        AND (o.object_name      LIKE :object_name ESCAPE '\\' OR :object_name IS NULL)
    UNION ALL
    SELECT
        o.object_type,
        o.object_name
    FROM user_objects o
    WHERE :force                = 'Y'
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
SELECT
    e.type          AS object_type,
    e.name          AS object_name,
    COUNT(e.line)   AS errors,
    COALESCE(
        MIN(REGEXP_SUBSTR(e.text, 'ORA-\\d+')),
        MIN(REGEXP_SUBSTR(e.text, 'PLS-\\d+'))
    ) AS error
FROM user_errors e
WHERE 1 = 1
    AND (e.type     LIKE :object_type ESCAPE '\\' OR :object_type IS NULL)
    AND (e.name     LIKE :object_name ESCAPE '\\' OR :object_name IS NULL)
    AND e.text      NOT LIKE 'PLW%'     -- skip warnings
GROUP BY
    e.type,
    e.name
ORDER BY 1, 2
"""

object_dependencies = """
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
    WHERE t.sequence_name       LIKE :objects_prefix
        AND t.sequence_name     NOT LIKE 'ISEQ$$%'
    --
    UNION ALL
    SELECT
        t.table_name            AS object_name,
        'TABLE'                 AS object_type,
        NULL                    AS referenced_name,
        NULL                    AS referenced_type
    FROM user_tables t
    WHERE t.table_name          LIKE :objects_prefix
    --
    UNION ALL
    SELECT
        t.index_name            AS object_name,
        'INDEX'                 AS object_type,
        NULL                    AS referenced_name,
        NULL                    AS referenced_type
    FROM user_indexes t
    WHERE t.table_name          LIKE :objects_prefix
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
    WHERE c.table_name          LIKE :objects_prefix
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
    WHERE o.object_name         LIKE :objects_prefix
        AND o.object_type       IN ('PACKAGE', 'PACKAGE BODY', 'PROCEDURE', 'FUNCTION', 'TRIGGER', 'VIEW', 'MATERIALIZED VIEW', 'SYNONYM', 'TYPE', 'TYPE BODY')
    --
    UNION ALL
    SELECT
        d.name                  AS object_name,
        d.type                  AS object_type,
        d.referenced_name,
        d.referenced_type
    FROM user_dependencies d
    WHERE d.name                LIKE :objects_prefix
        AND d.referenced_owner  = USER
        AND d.referenced_name   LIKE :objects_prefix
        AND d.referenced_type   NOT IN ('TABLE', 'SEQUENCE')
    --
    UNION ALL
    SELECT
        t.job_name              AS object_name,
        'JOB'                   AS object_type,
        NULL                    AS referenced_name,
        NULL                    AS referenced_type
    FROM user_scheduler_jobs t
    WHERE t.job_creator         NOT IN ('APEX_PUBLIC_USER', 'SYS')
        AND t.schedule_type     NOT IN ('ONCE')
        AND t.job_name          LIKE :objects_prefix
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
"""
CREATE MATERIALIZED VIEW ... AS ^;
CREATE UNIQUE INDEX ..._uq ON ... (
    object_name,
    object_type,
    referenced_name,
    referenced_type
);
"""

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

