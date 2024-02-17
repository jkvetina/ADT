query_apex_version = """
BEGIN
    APEX_UTIL.SET_WORKSPACE (
        p_workspace         => '{$APEX_WORKSPACE}'
    );
    APEX_APPLICATION_ADMIN.SET_APPLICATION_VERSION (
        p_application_id    => {$APEX_APP_ID},
        p_version           => '{$APEX_VERSION}'
    );
    APEX_APPLICATION_INSTALL.SET_KEEP_SESSIONS(p_keep_sessions => TRUE);
    COMMIT;
END;
/
"""
