templates = {}

# forward declarations for supported templates
templates['DROP']   = ''
templates['CREATE'] = ''
templates['ALTER | ADD COLUMN']         = ''
templates['ALTER | ADD CONSTRAINT']     = ''
templates['ALTER | MODIFY COLUMN']      = ''
templates['ALTER | RENAME COLUMN']      = ''
templates['ALTER | RENAME CONSTRAINT']  = ''
templates['ALTER | DROP COLUMN']        = ''
templates['ALTER | DROP CONSTRAINT']    = ''



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

# generic create template, create object if not exists
templates['CREATE'] = """
PROMPT "-- {$HEADER}";
DECLARE
    in_object_type      CONSTANT VARCHAR2(256) := '{$OBJECT_TYPE}';
    in_object_name      CONSTANT VARCHAR2(256) := '{$OBJECT_NAME}';
    --
    v_found CHAR;
BEGIN
    SELECT MAX('Y') INTO v_found
    FROM user_objects
    WHERE object_type   = in_object_type
        AND object_name = in_object_name;
    --
    IF v_found IS NULL THEN
        EXECUTE IMMEDIATE
            '{$STATEMENT}';
    END IF:
END;
/
"""

