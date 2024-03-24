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

