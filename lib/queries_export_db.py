matching_objects = """
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
WHERE 1 = 1
    AND o.object_type       NOT IN ('LOB', 'TABLE PARTITION', 'INDEX', 'INDEX PARTITION', 'JOB')
    AND o.object_type       LIKE :object_type || '%'
    AND o.object_name       LIKE :object_name || '%' ESCAPE '\\'
    AND o.object_name       NOT LIKE 'SYS\\_%' ESCAPE '\\'
    AND o.object_name       NOT LIKE 'ISEQ$$_%'
    AND (o.last_ddl_time    >= TRUNC(SYSDATE) + 1 - :recent OR :recent IS NULL)
    AND (o.object_type, o.object_name) NOT IN (
        SELECT
            'TABLE'         AS object_type,
            m.mview_name    AS object_name
        FROM user_mviews m
    )
UNION ALL
SELECT
    'JOB'           AS object_type,
    j.job_name      AS object_name,
    NULL            AS tablespace_name,
    NULL            AS partitioned,
    NULL            AS global_stats
FROM user_scheduler_jobs j
WHERE :recent IS NULL
    AND (:object_type   = 'JOB' OR NULLIF(:object_type, '%') IS NULL)
    AND j.job_name      LIKE :object_name || '%' ESCAPE '\\'
    AND j.schedule_type != 'IMMEDIATE'
UNION ALL
SELECT
    'MVIEW LOG'                     AS object_type,
    REPLACE(l.log_table, 'MLOG$_')  AS object_name,
    NULL                            AS tablespace_name,
    NULL                            AS partitioned,
    NULL                            AS global_stats
FROM user_mview_logs l
WHERE :recent IS NULL
    AND (:object_type LIKE 'MAT%' OR NULLIF(:object_type, '%') IS NULL)
    AND REPLACE(l.log_table, 'MLOG$_') LIKE :object_name || '%' ESCAPE '\\'
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
WHERE 1 = 1
    AND (:object_type       LIKE 'TABLE%' OR :object_type LIKE 'INDEX%' OR NULLIF(:object_type, '%') IS NULL)
    AND (t.table_name       LIKE :object_name || '%' ESCAPE '\\'
        OR t.index_name     LIKE :object_name || '%' ESCAPE '\\'
    )
    AND t.index_name        NOT LIKE 'SYS%$$'
    AND t.generated         = 'N'
    AND t.constraint_index  = 'NO'
    AND (t.last_analyzed    >= TRUNC(SYSDATE) + 1 - :recent OR :recent IS NULL)
    AND c.constraint_name   IS NULL
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

setup_dbms_metadata = """
BEGIN
    DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'PARTITIONING',          FALSE);
    DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'PHYSICAL_PROPERTIES',   FALSE);
    DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'SEGMENT_ATTRIBUTES',    FALSE);
    DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'STORAGE',               FALSE);
    DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'TABLESPACE',            FALSE);
    DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'SQLTERMINATOR',         FALSE);
    DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'PRETTY',                TRUE);
END;"""

# get table comments
pull_comments = """
SELECT
    m.table_name,
    NULL                    AS column_name,
    NULL                    AS column_full,
    m.comments,
    NULL                    AS column_id
FROM user_tab_comments m
WHERE m.table_name          LIKE :object_name || '%' ESCAPE '\\'
--
UNION ALL
SELECT
    m.table_name,
    m.column_name,
    RPAD(LOWER(m.table_name || '.' || m.column_name), MAX(FLOOR(LENGTH(m.table_name || '.' || m.column_name) / 4) * 4 + 5) OVER (PARTITION BY m.table_name)) AS column_full,
    m.comments,
    c.column_id
FROM user_col_comments m
JOIN user_tab_cols c
    ON c.table_name         = m.table_name
    AND c.column_name       = m.column_name
LEFT JOIN user_views v
    ON v.view_name          = m.table_name
WHERE m.table_name          LIKE :object_name || '%' ESCAPE '\\'
    AND m.table_name        NOT LIKE '%\\_E$' ESCAPE '\\'
    AND (
        m.column_name       NOT IN (
            'UPDATED_BY', 'UPDATED_AT', 'CREATED_BY', 'CREATED_AT'
        )
        OR m.comments       IS NOT NULL
    )
ORDER BY 1, column_id NULLS FIRST
"""

