# get database objects overview
overview = """
SELECT
    a.object_type,
    COUNT(*) AS object_count,
    SUM(CASE WHEN a.status = 'INVALID' THEN 1 ELSE 0 END) AS invalid
FROM user_objects a
WHERE a.object_type     NOT IN ('LOB', 'TABLE PARTITION', 'INDEX')
    AND a.object_name   LIKE :object_name || '%' ESCAPE '\\'
GROUP BY a.object_type
--
UNION ALL
SELECT
    'MVIEW LOG' AS object_type,
    COUNT(*)    AS object_count,
    NULL        AS invalid
FROM user_mview_logs l
WHERE REPLACE(l.log_table, 'MLOG$_') LIKE :object_name || '%' ESCAPE '\\'
HAVING COUNT(*) > 0
--
UNION ALL
SELECT
    'INDEX'     AS object_type,
    COUNT(*)    AS object_count,
    NULL        AS invalid
FROM user_indexes t
WHERE (t.table_name         LIKE :object_name || '%' ESCAPE '\\'
    OR t.index_name         LIKE :object_name || '%' ESCAPE '\\')
    AND t.index_name        NOT LIKE 'SYS%$$'
    AND t.generated         = 'N'
    AND t.constraint_index  = 'NO'
ORDER BY 1"""

# get database objects to recompile
objects_to_recompile = """
SELECT o.*
FROM (
    SELECT o.object_name, o.object_type
    FROM user_objects o
    WHERE o.status              != 'VALID'
        AND o.object_type       NOT IN ('SEQUENCE')
        AND (o.object_type      LIKE :object_type ESCAPE '\\' OR :object_type IS NULL)
        AND (o.object_name      LIKE :object_name ESCAPE '\\' OR :object_name IS NULL)
    UNION ALL
    SELECT o.object_name, o.object_type
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
    WHEN 'MATERIALIZED VIEW'    THEN 7
    WHEN 'TYPE BODY'            THEN 8
    WHEN 'PACKAGE BODY'         THEN 9
    ELSE                             6 END"""

