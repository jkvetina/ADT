SET SERVEROUTPUT ON
SET SQLBLANKLINES ON
SET DEFINE OFF
--
BEGIN
    DBMS_SESSION.SET_NLS('NLS_LANGUAGE',            '''ENGLISH''');
    DBMS_SESSION.SET_NLS('NLS_TERRITORY',           '''CZECH REPUBLIC''');
    DBMS_SESSION.SET_NLS('NLS_NUMERIC_CHARACTERS',  '''. ''');
    DBMS_SESSION.SET_NLS('NLS_DATE_FORMAT',         '''YYYY-MM-DD HH24:MI:SS''');
    DBMS_SESSION.SET_NLS('NLS_TIME_FORMAT',         '''HH24:MI:SSXFF''');
    DBMS_SESSION.SET_NLS('NLS_TIMESTAMP_FORMAT',    '''YYYY-MM-DD HH24:MI:SSXFF''');
    DBMS_SESSION.SET_NLS('NLS_TIME_TZ_FORMAT',      '''HH24:MI:SSXFF TZR''');
    DBMS_SESSION.SET_NLS('NLS_TIMESTAMP_TZ_FORMAT', '''YYYY-MM-DD HH24:MI:SSXFF TZR''');
    DBMS_SESSION.SET_NLS('NLS_SORT',                '''BINARY_AI''');
    DBMS_SESSION.SET_NLS('NLS_COMP',                '''LINGUISTIC''');
END;
/
