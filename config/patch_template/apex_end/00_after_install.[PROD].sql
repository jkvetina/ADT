BEGIN
    -- lock the application for production
    APEX_UTIL.SET_APP_BUILD_STATUS (
        p_application_id    => {$APEX_APP_ID},
        p_build_status      => 'RUN_ONLY'
        --p_build_status      => 'RUN_AND_BUILD'
    );
    --
    COMMIT;
END;
/
