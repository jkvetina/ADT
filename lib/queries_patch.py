templates = {}

# forward declarations for supported templates
templates['DROP']                       = ''    # index [-01418]
templates['CREATE']                     = ''    # index [-00955, -01408]
templates['ALTER | ADD COLUMN']         = ''    # [-01430, -02260, -02275]
templates['ALTER | ADD CONSTRAINT']     = ''    # [-02260, -02261, -02264, -02275]
templates['ALTER | MODIFY COLUMN']      = ''    # [-01430, -02260, -02275]
templates['ALTER | RENAME COLUMN']      = ''    # [-00942, -00957]
templates['ALTER | RENAME CONSTRAINT']  = ''    # [-23292]
templates['ALTER | DROP COLUMN']        = ''    # [-00904, -01430, -02275]
templates['ALTER | DROP CONSTRAINT']    = ''    # [-02443]
#
# https://docs.oracle.com/en/database/oracle/oracle-database/19/errmg/ORA-19999.html
#
# ORA-00904: The identifier or column name that was invalid.
# ORA-00942: table or view does not exist
# ORA-00955: name is already used by an existing object
# ORA-00957: duplicate column name
# ORA-01408: such column list already indexed
# ORA-01430: column being added already exists in table
# ORA-02260: table can have only one primary key
# ORA-02261: The unique or primary key already exists in the table.
# ORA-02264: name already used by an existing constraint
# ORA-02275: such a referential constraint already exists in the table
# ORA-02443: Cannot drop constraint - nonexistent constraint
# ORA-14511: cannot perform operation on a partitioned object
# ORA-23292: The constraint does not exist
#

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
#
templates['ALTER | RENAME COLUMN'] = templates['ALTER | DROP COLUMN']
templates['ALTER | MODIFY COLUMN'] = templates['ALTER | DROP COLUMN']

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

# drop constraint, if exists
templates['ALTER | DROP CONSTRAINT'] = """
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
    IF v_found = 'Y' THEN
        EXECUTE IMMEDIATE
            '{$STATEMENT}';
    END IF;
END;
/
"""
#
templates['ALTER | RENAME CONSTRAINT'] = templates['ALTER | DROP CONSTRAINT']

