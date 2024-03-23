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
    END IF;
END;
/
"""

# add new column to the table
templates['ALTER | ADD COLUMN'] = """
PROMPT "-- {$HEADER}";
DECLARE
    in_table_name       CONSTANT VARCHAR2(256) := '{$OBJECT_NAME}';
    in_column_name      CONSTANT VARCHAR2(256) := '{$CC_NAME}';
    --
    v_found CHAR;
BEGIN
    SELECT MAX('Y') INTO v_found
    FROM user_tab_columns
    WHERE table_name    = in_table_name
        AND column_name = in_column_name;
    --
    IF v_found IS NULL THEN
        EXECUTE IMMEDIATE
            '{$STATEMENT}';
    END IF;
END;
/
"""

# add new column to the table
templates['ALTER | DROP COLUMN'] = """
PROMPT "-- {$HEADER}";
DECLARE
    in_table_name       CONSTANT VARCHAR2(256) := '{$OBJECT_NAME}';
    in_column_name      CONSTANT VARCHAR2(256) := '{$CC_NAME}';
    --
    v_found CHAR;
BEGIN
    SELECT MAX('Y') INTO v_found
    FROM user_tab_columns
    WHERE table_name    = in_table_name
        AND column_name = in_column_name;
    --
    IF v_found = 'Y' THEN
        EXECUTE IMMEDIATE
            '{$STATEMENT}';
    END IF;
END;
/
"""

# add new constraint to the table
templates['ALTER | ADD CONSTRAINT'] = """
PROMPT "-- {$HEADER}";
DECLARE
    in_table_name           CONSTANT VARCHAR2(256) := '{$OBJECT_NAME}';
    in_constraint_name      CONSTANT VARCHAR2(256) := '{$CC_NAME}';
    --
    v_found CHAR;
BEGIN
    SELECT MAX('Y') INTO v_found
    FROM user_constraints
    WHERE table_name        = in_table_name
        AND constraint_name = in_constraint_name;
    --
    IF v_found IS NULL THEN
        EXECUTE IMMEDIATE
            '{$STATEMENT}';
    END IF;
END;
/
"""

END;
/
"""

