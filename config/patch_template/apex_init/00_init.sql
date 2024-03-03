SET DEFINE OFF
SET SERVEROUTPUT OFF
--
BEGIN
    -- set workspace so we can actually import APEX
    APEX_UTIL.SET_WORKSPACE (
        p_workspace => '{$APEX_WORKSPACE}'
    );

    -- keep sessions alive
    APEX_APPLICATION_INSTALL.SET_KEEP_SESSIONS(p_keep_sessions => TRUE);
    COMMIT;
END;
/
