# ADT - APEX Deployment Tool

ADT is an open-source tool written in Python which allows you to connect to your Oracle database, export objects and data and APEX applications, files and individual components into a folder structure.
It helps you to automate the patching and deploying/migrating your changes to other environments in multiple variants.

ADT provides you more benefits when used with other APEX apps:

| Application Name                                              | Description                                       | Status
| :---------------                                              | :----------                                       | :-----
| [Cards](https://github.com/jkvetina/MASTER_TASKS)             | to manage your tasks, bugs...                     | Done
| [Roadmap](https://github.com/jkvetina/MASTER_ROADMAPS)        | to plan and track whole projects on higher level  | In Progress
| [Deployments](https://github.com/jkvetina/MASTER_DEPLOYMENTS) | to track commits, releases and deployments        | Planned
| [Reviews](https://github.com/jkvetina/MASTER_REVIEWS)         | to improve quality of your code                   | Planned

I have been building these CI/CD tools since 2008 and ADT is the newest version, heavily based on the previous [OPY](https://github.com/jkvetina/OPY/tree/master) tool, which unfortunately outgrown to a hefty spaghetti code and became more and more difficult to extend. So, I have decided to start from scratch for like 15th time...

&nbsp;

## How to install

- clone this repo
    - get the [GitHub Desktop](https://desktop.github.com) if needed
- [install neccessary tools](./doc/install.md) like Python and SQLcl
- run `python config.py` which will guide you through the setup
    - read more about config file if needed
- run `python export.py` to export database and/or APEX into your repo
- explore other actions

&nbsp;

## Actions
| Filename                                 | Description                                    | Status
| :-------                                 | :----------                                    | :-----
| [`config.py`](./doc/config.md)           | to manage database connections and settings    | In Progress
| [`export_db.py`](./doc/export_db.md)     | to export database objects                     | OPY
| [`export_apex.py`](./doc/export_apex.md) | to export APEX                                 | OPY
| [`export_data.py`](./doc/export_data.md) | to export data into CSV files                  | OPY
| [`patch.py`](./doc/patch.md)             | to prepare patch files from your changes       | Done
| [`deploy.py`](./doc/deploy.md)           | to deploy your patch files                     | Planned
| [`compare.py`](./doc/compare.md)         | to compare two databases                       | Planned
| [`recompile.py`](./doc/recompile.md)     | to recompile invalid objects                   | Planned

&nbsp;

## Main features

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
    - it can also __deploy these patches__ to different environments (basically any database you can reach via direct connection on via a REST service)
    - multiple schemas patching dependencies
    - install script for test environments or local developers
- it can __compare two databases__ and show you the differences and what you need to do to sync them, including the data changes
    - no false positives on different column positions, different identity column sequences, whitespaces...
    - it can also quickly compare APEX applications based on the signatures
- see config.yaml file for __200+ parameters__ you can customize
    - to use your config.yaml file, just place it in the root of your project/repo

&nbsp;

## Folder structure

- `doc/`
    - if you are into documenting things, you will love this folder
- `database_{$info_schema}/{$object_type}/` for database objects
- `database_{$info_schema}/data/` for exported data
- `database/grants_made/{$info_schema}.sql`
- `database/grants_received/{$info_schema}.sql`
    - made and received grants for each schema involved
- `apex_{$app_ws}_{$app_schema}/{$app_id}_{$app_alias}/`
    - for APEX app and related objects
    - optional workspace and app alias or group in the path
    - schema can be also pulled from config
- `apex_{$app_ws}_{$app_schema}/rest/`
    - with folders and files
- `apex_{$app_ws}/workspace_files/`
- `patch/{$info_env}/{$date_today}_{$patch_code}_{$info_schema|$app_schema}/` to store files snapshot
- `patch/{$info_env}/{$date_today}_{$patch_code}_{$info_schema|$app_schema}.sql` for generated patch script
- `patch_logs/{$info_env}/compare{$date_time}_{$source_env}.log`
    - changed objects, APEX components, timings...
- `patch_archive/{$info_env}/` for old patches
- `patch_template/{$info_env}_{$info_schema|$app_schema}/` for patch templates
- `scripts/`

&nbsp;

You can customize all of these paths in the config and there are plenty of variables available to fit your needs.

For APEX these variables will be determined based on requested application id or workspace:

| Variable       | Description
| :------------- | :----------
| `app_ws`       | workspace of the current application
| `app_id`       | application id
| `app_alias`    | application alias
| `app_schema`   | application schema
| `app_group`    | application group

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
| `date_time`    | YYYY-MM-DD_HH24-MI
| `date_custom`  | whatever you decide...
