BEGIN
    -- set workspace so we can actually import APEX
    APEX_UTIL.SET_WORKSPACE (
        p_workspace => '{$APEX_WORKSPACE}'
    );

    -- set new version
    IF '{$APEX_VERSION}' IS NOT NULL THEN
        APEX_APPLICATION_ADMIN.SET_APPLICATION_VERSION (
            p_application_id    => {$APEX_APP_ID},
            p_version           => '{$APEX_VERSION}'
        );
    END IF;
    --
    COMMIT;
END;
/
