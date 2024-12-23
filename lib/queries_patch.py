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



# drop all objects in implode script
template_objects_drop_line = "SELECT '{object_type}', '{object_name}' FROM DUAL UNION ALL"
template_objects_drop = """
DECLARE
    in_execute      CONSTANT CHAR := 'Y';    -- Y/NULL
BEGIN
    FOR c IN (
        WITH t (object_type, object_name) AS (
{object_lines}
            SELECT '', '' FROM DUAL
        )
        SELECT
            'DROP ' || RPAD(o.object_type, x.max_length) || ' ' || o.object_name ||
            CASE WHEN o.object_type LIKE 'TYPE%' THEN ' FORCE' END
            AS q
        FROM user_objects o
        CROSS JOIN (
            SELECT
                MAX(LENGTH(t.object_type)) AS max_length
            FROM t
        ) x
        JOIN t
            ON t.object_type    = o.object_type
            AND t.object_name   = o.object_name
        ORDER BY
            REPLACE(o.object_type, ' BODY', ''),
            CASE WHEN o.object_type LIKE '%BODY' THEN 1 ELSE 0 END,
            o.object_name
    ) LOOP
        DBMS_OUTPUT.PUT_LINE(c.q || ';');
        --
        IF in_execute = 'Y' THEN
            BEGIN
                EXECUTE IMMEDIATE c.q;
            EXCEPTION
            WHEN OTHERS THEN
                NULL;
            END;
        END IF;
    END LOOP;
    --
    -- KEEP IN MIND THAT AFTER OBJECTS DROP YOU NEED TO REDO THE GRANTS ...
    --
END;
/
"""



# generate diff in between two tables
generate_table_diff = """
DECLARE
    in_source_table CONSTANT VARCHAR2(64) := :source_table;     -- $1
    in_target_table CONSTANT VARCHAR2(64) := :target_table;     -- $2
    --
    v_xml_source    CLOB;
    v_xml_target    CLOB;
    v_diff          CLOB;
    v_result        CLOB;
    v_handler       NUMBER;
    v_transform     NUMBER;
BEGIN
    -- remove junk
    DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'PARTITIONING', FALSE);
    DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'PHYSICAL_PROPERTIES', FALSE);
    DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'SEGMENT_ATTRIBUTES', FALSE);
    DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'STORAGE', FALSE);
    DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'TABLESPACE', FALSE);

    -- export tables as Simple XML
    v_xml_source    := REPLACE(DBMS_METADATA.GET_SXML('TABLE', in_source_table), '$1', '');
    v_xml_target    := REPLACE(DBMS_METADATA.GET_SXML('TABLE', in_target_table), '$2', '');

    -- get diff ALTER statements
    v_handler       := DBMS_METADATA_DIFF.OPENC('TABLE');
    --
    DBMS_METADATA_DIFF.ADD_DOCUMENT(handle => v_handler, document => v_xml_source);
    DBMS_METADATA_DIFF.ADD_DOCUMENT(handle => v_handler, document => v_xml_target);
    --
    v_result        := DBMS_METADATA_DIFF.FETCH_CLOB(v_handler);
    DBMS_METADATA_DIFF.CLOSE(v_handler);
    --
    v_handler       := DBMS_METADATA.OPENW('TABLE');
    v_transform     := DBMS_METADATA.ADD_TRANSFORM(v_handler, 'ALTERXML');
    v_transform     := DBMS_METADATA.ADD_TRANSFORM(v_handler, 'ALTERDDL');
    --
    DBMS_LOB.CREATETEMPORARY(v_diff, TRUE);
    DBMS_METADATA.CONVERT(v_handler, v_result, v_diff);
    DBMS_METADATA.CLOSE(v_handler);
    --
    --DBMS_OUTPUT.PUT_LINE(v_diff);
    :result := v_diff;
END;
"""

# cleanup diff tables
diff_tables = """
WITH objects_add AS (
    SELECT /*+ MATERIALIZE CARDINALITY(t 1) */
        t.column_value AS object_like
    FROM TABLE(APEX_STRING.SPLIT(TRIM(BOTH ',' FROM NVL(:objects_prefix, '%')), ',')) t
),
objects_ignore AS (
    SELECT /*+ MATERIALIZE CARDINALITY(t 10) */
        t.column_value AS object_like
    FROM TABLE(APEX_STRING.SPLIT(TRIM(BOTH ',' FROM :objects_ignore), ',')) t
)
SELECT
    t.table_name
FROM user_tables t
JOIN objects_add a
    ON t.table_name         LIKE a.object_like ESCAPE '\\'
LEFT JOIN objects_ignore g
    ON t.table_name         LIKE g.object_like ESCAPE '\\'
WHERE 1 = 1
    AND (t.table_name       LIKE '%$1' OR t.table_name LIKE '%$2')
ORDER BY 1
"""

# compare view columns
view_columns = """
SELECT
    c.column_name,
    c.column_id
FROM user_tab_cols c
WHERE c.table_name = :view_name
"""

# to convert file for APEX
template_apex_file = """
wwv_flow_imp_shared.create_app_static_file(
 p_id=>wwv_flow_imp.id({})
,p_file_name=>'{}'
,p_mime_type=>'{}'
,p_file_charset=>'utf-8'
,p_file_content => wwv_flow_imp.varchar2_to_blob(wwv_flow_imp.g_varchar2_table)
);
wwv_flow_imp.component_end;
end;
/
"""
#
template_apex_file_id   = "wwv_flow_id.next_val"
template_apex_file_init = "wwv_flow_imp.g_varchar2_table := wwv_flow_imp.empty_varchar2_table;"
template_apex_file_line = "wwv_flow_imp.g_varchar2_table({}) := '{}';"

