# ADT - APEX Deployment Tool

ADT is an open-source tool written in Python which allows you to connect to your Oracle database, export objects and data and APEX applications, files and individual components into a folder structure.
It helps you to automate the patching and deploying/migrating your changes to other environments in multiple variants.

It does not store anything in your database.

I have been building these CI/CD tools since 2008 and ADT is the newest version, heavily based on the previous [OPY](https://github.com/jkvetina/OPY/tree/master) tool, which unfortunately outgrown to a hefty spaghetti code and became more and more difficult to extend. So, I have decided to start from scratch for like 15th time...

Checkout the [INSTALL guide](./doc/install.md).

&nbsp;

## Actions/Roadmap (progress 42/61, 69%)

| Filename                                 | Description                                    | Status          | Complexity | Done |
| :-------                                 | :----------                                    | :-----          | ---------: | ---: |
| [`config.py`](./doc/config.md)           | to manage database connections and settings    | Done            |          5 | 5    |
| `export_db.py`                           | to export database objects                     | __In Progress__ |         10 | 5    |
| `export_apex.py`                         | to export APEX & REST services                 | Done            |          7 | 7    |
| `export_data.py`                         | to export data into CSV files                  | Planned         |          4 |      |
| [`live_upload.py`](./doc/live_upload.md) | to upload files to APEX                        | Done            |          1 | 1    |
| [`patch.py`](./doc/patch.md)             | to prepare patch files and deploy them         | Done            |         20 | 20   |
| `compare.py`                             | to compare two databases                       | Planned         |         10 |      |
| [`recompile.py`](./doc/recompile.md)     | to recompile invalid objects                   | Done            |          1 | 1    |
| [`search_apex.py`](./doc/search_apex.md) | to search for objects in APEX                  | Done            |          2 | 2    |
| [`search_repo.py`](./doc/search_repo.md) | to search repo history                         | Done            |          1 | 1    |

&nbsp;

## Main features (also a Roadmap)

- ✅ it can __connect to on-premise and cloud__ Oracle databases
- ✅ it can __export APEX application(s)__
    - ✅ you can request specific components based on page or date
    - ✅ also in YAML/JSON formats
    - ✅ possible with embedded code reports
    - ✅ including application and workspace files
    - ✅ option to deploy exported files to specified environment
    - ✅ live upload for files
    - ✅ export REST services
- ✅ it can __create patch files__ so you can easily deploy your database and APEX changes since last deployment, or based on your features/cards
    - ✅ it can connect to Git/BB to create a release notes for you
    - ✅ it can also create a patch file __based on a feature/card__, it will lookup which files were committed under that name and create a patch based on that (and even for APEX components so you dont have to deploy the whole app)
    - ✅ it allows you to search Git/BB history for specific string
    - ✅ include various checks and scope limits for what will be part of the patch
    - ✅ you can use sequences to sort patches created on same day, it checks for clashes
    - ✅ files are properly sorted based on dependencies
    - ✅ statements in patch scripts converted to your templates so they can be rerun
- ✅ it can also __deploy these patches__ to different environments (basically any database you can reach via direct connection on via a REST service)
    - ✅ multiple schemas patching (so far you manually specify order with numeric prefix on each patch file)
    - ✅ show progress, results and save output in customized log files
    - ✅ include various checks and logs to limit deployment issues (like using old files)
    - ✅ option to quickly deploy or redeploy created patch
    - ✅ show patch result (build log) on Teams channel
    - ✅ generate ALTER statements on same table and different commits
    - ⭕️ remote REST app deployment
- ✅ it can __export database objects__
    - ✅ generate list of dependencies
    - ✅ you can filter objects by type, name and time (export for example everything starting with XX% and changed in past 3 days)
        - ✅ tables, views, indexes, sequences, synonyms
        - ✅ packages, procedures, functions, triggers, types
        - ⭕️ materialized views + logs
        - ✅ jobs (resp. schedulers)
        - ✅ grants (made and received), user grants and roles, directories
    - ⭕️ there are also multiple whitelist and blacklist filters so you can specify which prefixes you want to include or you want to skip
    - ⭕️ you can create your own list of objects which will be exported (see locked.log), which is handy when you have multiple projects in the same schema; it now even support autolock feature
        - ⭕️ locked mode vs filter based mode
    - ⭕️ multiple schemas are supported via subfolders
    - ⭕️ you can also manually create subfolders for objects (so you can put for example views into groups/folders)
    - ⭕️ option to deploy exported files to specified environment
- ⭕️ it can __export data__ into CSV files
    - ⭕️ althought it will skip LOB columns (for now)
    - ⭕️ creates SQL MERGE statements for patching
    - ⭕️ option to deploy exported files to specified environment
- ✅ generate __install script__ for test/local environments to install everything into a clean schema
- ⭕️ it can __compare two databases__ and show you the differences and what you need to do to sync them, including the data changes
    - ⭕️ no false positives on different column positions, different identity column sequences, whitespaces...
    - ⭕️ it can also quickly compare APEX applications based on the signatures
    - ⭕️ generate ALTER statements for table changes, align columns order, sync sequences...
- ✅ it can recompile invalid objects + limit the scope based on type and name
    - ✅ it can also force recompile objects and set specific PL/SQL attributes on them
- ✅ see config.yaml file for __200+ parameters__ you can customize
    - ✅ to use your config.yaml file, just place it in the config folder in root of your project repo

&nbsp;

## Folder structure

- `doc/`
    - if you are into documenting things, you will love this folder
- `database_{$info_schema}/{$object_type}/` for database objects
- `database_{$info_schema}/data/` for exported data
- `database_{$info_schema}/unit_tests/` for packages which are unit tests
- `database/grants_made/{$info_schema}.sql`
- `database/grants_received/{$info_schema}.sql`
    - made and received grants for each schema involved
- `apex/{$app_ws}/{$app_group}/{$app_owner}/{$app_id}_{$app_alias}/`
    - for APEX app and related objects
    - optional workspace, application group, owner and app alias in the path
    - you don't have to use all of these variables
- `apex/{$app_ws}/rest/`
    - with folders and files
- `apex/{$app_ws}/workspace_files/`
- `patch/{$date_today}.{$sequence}.{$patch_code}/` for generated patch files
- `patch/{$date_today}.{$sequence}.{$patch_code}/LOGS_{$info_env}/` for deployment logs
- `patch_archive/` for old patches (use `deploy.py -archive`)
- `patch_template/` for patch templates (appended to all patches)
- `patch_scripts/{$patch_code}/` for patch scripts (appended to just for specific patch)
- `scripts/` for your scripts, snippets, tests...

&nbsp;

You can customize all of these paths through the [`config.py`](./doc/config.md) and there are plenty of variables available to fit your needs.

&nbsp;

## Supporting apps

ADT provides you more benefits when used with other APEX apps (but it is fully functional without these apps):

| Application Name                                              | Description                                       | Status
| :---------------                                              | :----------                                       | :-----
| [Cards](https://github.com/jkvetina/MASTER_TASKS)             | to manage your tasks, bugs...                     | __Done__
| [Roadmap](https://github.com/jkvetina/MASTER_ROADMAPS)        | to plan and track whole projects on higher level  | __In Progress__
| [Deployments](https://github.com/jkvetina/MASTER_DEPLOYMENTS) | to track commits, releases and deployments        | Planned
| [Reviews](https://github.com/jkvetina/MASTER_REVIEWS)         | to improve quality of your code                   | Planned

