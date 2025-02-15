-- show invalid objects
PROMPT "INVALID OBJECTS:"
COLUMN object_type FORMAT A10
COLUMN object_name FORMAT A30
--
SELECT
    o.object_type,
    o.object_name
FROM user_objects o
WHERE 1 = 1
    AND o.object_name   LIKE '%'
    AND o.status        = 'INVALID'
ORDER BY 1, 2;



-- recompile invalid objects
PROMPT "RECOMPILE INVALID OBJECTS..."
BEGIN
    DBMS_UTILITY.COMPILE_SCHEMA (
        schema          => SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA'),
        compile_all     => FALSE
    );
END;
/



-- show invalid objects
PROMPT "INVALID OBJECTS:"
COLUMN object_type FORMAT A10
COLUMN object_name FORMAT A30
--
SELECT
    o.object_type,
    o.object_name
FROM user_objects o
WHERE 1 = 1
    AND o.object_name   LIKE '%'
    AND o.status        = 'INVALID'
ORDER BY 1, 2;



-- check recent errors
PROMPT "RECENT ERRORS:"
COLUMN object_type FORMAT A10
COLUMN object_name FORMAT A30
COLUMN line FORMAT A5
COLUMN text FORMAT A30
--
SELECT
    e.type AS object_type,
    e.name AS object_name,
    e.line,
    e.text
FROM user_errors e
WHERE 1 = 1
    AND e.name  LIKE '%'
    AND e.text  NOT LIKE 'PLW%'
ORDER BY
    e.type,
    e.name,
    e.sequence;

