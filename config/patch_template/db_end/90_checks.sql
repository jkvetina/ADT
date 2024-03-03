
-- show invalid objects
SELECT
    o.object_type,
    o.object_name
FROM user_objects o
WHERE 1 = 1
    AND o.object_name   LIKE '%'
    AND o.status        = 'INVALID'
ORDER BY 1, 2;

-- check recent errors
SELECT e.name, e.type, e.line, e.text
FROM user_errors e
WHERE 1 = 1
    AND o.object_name   LIKE '%'
    AND e.text          NOT LIKE 'PLW%'
ORDER BY
    e.name,
    e.sequence;

