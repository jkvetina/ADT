# ATD - APEX Deployment Tool

## Available Actions

| Filename                                 | Description
| :--------------------------------------- | :----------
| [`conn.py`](./doc/conn.md)               | to manage database connections
| [`recompile.py`](./doc/recompile.py)     | to recompile invalid objects
| [`export_db.py`](./doc/export_db.py)     | to export database objects
| [`export_apex.py`](./doc/export_apex.py) | to export APEX
| [`export_data.py`](./doc/export_data.py) | to export data into CSV files
| [`compare.py`](./doc/compare.py)         | to compare two databases
| [`patch.py`](./doc/patch.py)             | to prepare patch files from your changes
| [`deploy.py`](./doc/deploy.py)           | to deploy your patch files

&nbsp;

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
    - it can also create a patch file __based on a feature/card__, it will lookup which files were committed under that name and create a patch based on that (and even for APEX components so you dont have to deploy the whole app)
    - it allows you to search Git/BB history
    - it can __compare two databases__ and show you the differences and what you need to do to sync them, including the data changes
        - no false positives on different column positions, different identity column sequences, whitespaces…
    - it can also __deploy these patches__ to different environments (basically any database you can reach via direct connection on via a REST service)
    - multiple schemas patching dependencies
    - install script for test environments or local developers
- see config.yaml file for __200+ parameters__ you can customize
    - to use your config.yaml file, just place it in the root of your project/repo

&nbsp;

## Folder Structure

- `doc/`
    - if you are into documenting things, you will love this folder
- `database{_$schema}/$object_type/`
- `database{_$schema}/data/`
    - database exports - objects and data
- `database/grants_made/$schema.sql`
- `database/grants_received/$schema.sql`
    - made and received grants for each schema involved
- `apex{\_$app_ws}{\_$app_owner}/$app_id{_$app_alias}/`
    - for APEX app and related objects
    - optional workspace and app alias in the path
- `apex{_$app_ws}/workspace_files/`
- `apex{_$app_ws}/rest/`
    - folders and files
- `patch/$env/{$date_today}_{$patch_code}/`
    - store snapshot of the files
    - store install/deploy script here
- `patch_logs/$env/compare{$datetime}_{$source_env}.log`
    - changed objects, APEX components, timings...
- `patch_archive{/$env}/`
- `patch_template{/$env}/`
- `scripts/`

&nbsp;

You can customize all of these paths in the config and there are plenty of variables available to fit your needs.

For APEX these variables will be determined based on requested application id or workspace:

| Variable       | Description
| :------------- | :----------
| `app_ws`       | workspace of the current application
| `app_id`       | application id
| `app_alias`    | application alias
| `app_owner`    | application owner
| `app_schema`   | application schema

You can use some other variables determined on your request and config file:

| Variable       | Description
| :------------- | :----------
| `info_client`  | client code, to group your projects
| `info_project` | project code
| `info_schema`  | database schema
| `info_env`     | current environment

And finally some date formats (adjustable in the config file):

| Variable       | Description
| :------------- | :----------
| `date_today`   | YYYY-MM-DD
| `date_time`    | YYYY-MM-DD_HH24_MI
| `date_custom`  | whatever you decide...

&nbsp;

