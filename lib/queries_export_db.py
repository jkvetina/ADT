matching_objects = """
SELECT DISTINCT
    o.object_type,
    o.object_name
FROM user_objects o
WHERE 1 = 1
    AND o.object_type       NOT IN ('LOB', 'TABLE PARTITION', 'INDEX', 'INDEX PARTITION')
    AND o.object_type       LIKE :object_type || '%'
    AND o.object_name       LIKE :object_name || '%' ESCAPE '\\'
    AND o.object_name       NOT LIKE 'SYS\\_%' ESCAPE '\\'
    AND o.object_name       NOT LIKE 'ISEQ$$_%'
    AND (o.last_ddl_time    >= TRUNC(SYSDATE) + 1 - :recent OR :recent IS NULL)
    AND (o.object_type, o.object_name) NOT IN (
        SELECT
            'INDEX'         AS object_type,
            i.index_name    AS object_name
        FROM (
            SELECT
                i.table_name,
                i.index_name,
                LISTAGG(i.column_name, ', ') WITHIN GROUP (ORDER BY i.column_position) AS index_cols
            FROM user_ind_columns i
            GROUP BY i.table_name, i.index_name
        ) i
        JOIN (
            SELECT
                t.table_name,
                t.constraint_name,
                LISTAGG(t.column_name, ', ') WITHIN GROUP (ORDER BY t.position) AS constraint_cols
            FROM user_cons_columns t
            JOIN user_constraints n
                ON n.constraint_name    = t.constraint_name
            WHERE n.constraint_type     IN ('P', 'U')
            GROUP BY t.table_name, t.constraint_name
        ) c
            ON c.table_name         = i.table_name
            AND c.constraint_cols   = i.index_cols
    )
    AND (o.object_type, o.object_name) NOT IN (
        SELECT
            'TABLE'         AS object_type,
            m.mview_name    AS object_name
        FROM user_mviews m
    )
    AND o.object_type NOT IN ('JOB')
UNION ALL
SELECT
    'JOB'           AS object_type,
    j.job_name      AS object_name
FROM user_scheduler_jobs j
WHERE :recent IS NULL
    AND (:object_type   = 'JOB' OR NULLIF(:object_type, '%') IS NULL)
    AND j.job_name      LIKE :object_name || '%' ESCAPE '\\'
    AND j.schedule_type != 'IMMEDIATE'
UNION ALL
SELECT
    'MVIEW LOG'                     AS object_type,
    REPLACE(l.log_table, 'MLOG$_')  AS object_name
FROM user_mview_logs l
WHERE :recent IS NULL
    AND (:object_type LIKE 'MAT%' OR NULLIF(:object_type, '%') IS NULL)
    AND REPLACE(l.log_table, 'MLOG$_') LIKE :object_name || '%' ESCAPE '\\'
UNION ALL
SELECT
    'INDEX'             AS object_type,
    t.index_name        AS object_name
FROM user_indexes t
WHERE 1 = 1
    AND (:object_type       LIKE 'TABLE%' OR :object_type LIKE 'INDEX%' OR NULLIF(:object_type, '%') IS NULL)
    AND (t.table_name       LIKE :object_name || '%' ESCAPE '\\'
        OR t.index_name     LIKE :object_name || '%' ESCAPE '\\'
    )
    AND t.index_name        NOT LIKE 'SYS%$$'
    AND t.generated         = 'N'
    AND t.constraint_index  = 'NO'
    AND (t.last_analyzed    >= TRUNC(SYSDATE) + 1 - :recent OR :recent IS NULL)
"""

