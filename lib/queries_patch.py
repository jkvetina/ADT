templates = {}

# delete any object, only if exists
templates['DROP'] = """
PROMPT "-- {$HEADER}";
DECLARE
    in_object_type      CONSTANT VARCHAR2(256) := '{$OBJECT_TYPE}';
    in_object_name      CONSTANT VARCHAR2(256) := '{$OBJECT_NAME}';
BEGIN
    FOR c IN (
        SELECT object_type, object_name
        FROM user_objects
        WHERE object_type   = in_object_type
            AND object_name = in_object_name
    ) LOOP
        EXECUTE IMMEDIATE
            '{$STATEMENT}';
    END LOOP;
END;
/
"""

