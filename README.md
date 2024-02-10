# ATD - APEX Deployment Tool

## Main Features

- it can __connect to on-premise and cloud__ Oracle databases
- it can __export database objects__
    - you can filter objects by type, name and time (export for example everything starting with XX% and changed in past 3 days)
        - tables, view, materialized views + logs, indexes, sequences
        - packages, procedures, functions, triggers, TYPEs**
        - jobs (resp. schedulers)
        - grants (made and received)
    - there are also multiple whitelist and blacklist filters so you can specify which prefixes you want to include or you want to skip
    - you can create your own list of objects which will be exported (see locked.log), which is handy when you have multiple projects in the same schema; it now even support autolock feature
        - locked mode vs filter based mode
    - multiple schemas are supported via subfolders
    - you can also manually create subfolders for objects (so you can put for example views into groups/folders)
    - see supported object types
- it can __export data__ into CSV files
    - althought it will skip LOB columns
    - creates SQL MERGE statements for patching
- it can __export APEX application(s)__
    - including REST services and workspace files
    - also in YAML/JSON formats
    - possible with embedded code reports
    - you can request specific components based on page or date
    - upload files to APEX
    - remote REST app deployment
- it can __create patch files__ so you can easily deploy your database and APEX changes since last deployment, or based on your features/cards
    - it can connect to Git/BB to create a release notes for you
    - it can also create a patch file based on a feature/card, it will lookup which files were committed under that name and create a patch based on that (and even for APEX components so you dont have to deploy the whole app)
    - it allows you to search Git/BB history
    - it can compare two databases and show you the differences and what you need to do to sync them, including the data changes
        - no false positives on different column positions, different identity column sequences, whitespaces…
    - it can also deploy these patches to different environments (basically any database you can reach via direct connection on via a REST service)
    - multiple schemas patching dependencies
    - install script for test environments or local developers
- see config.yaml file for __200+ parameters__ you can customize
    - to use your config.yaml file, just place it in the root of your project/repo

