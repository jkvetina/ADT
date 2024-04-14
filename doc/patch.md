# Patch

Patching is the most significant feature of ADT. You can do a lot of cool things in ADT,
but I consider patching the coolest and unique think on the market.

The idea behind this is to focus on your job as a developer and don't worry about mundane tasks like creating patch files manually.
It has many checks and features to give you confidence on deploying.

This patch script does not connect to the database (unless you are deploying), it gets all the information from your Git repo, the folders, files and the config file. To be clear, the whole ADT does not store anything in database. So to make this work, you must be using Git (BitBucket is supported). If you are not using Git, you will not be able to use this patch script.

Multiple schemas are supported. Each schema and each APEX application will get its own patch file.
There are plenty of config options available to customize patching so it can be tailored to your individual needs.

&nbsp;

## Workflow

- you will do your changes on database objects and/or APEX applications as usual in any tool you prefer
- you will [export_db](./export_db.md), [export_apex](./export_apex.md) for recent changes and commit your changes in Git (ideally with the card number and meaningful description for release notes, you will use this card number later to identify which commits will be part of your patch), you can commit just parts of the file and you can do unlimited number of commits
- whenever you want to release the changes to other environment, you will run [patch.py](../patch.py) and this little magic script will create a patch file for you
- there are several significant features built in to make your life as a developer (or release manager) easier
- you can specify patch templates which basically adds template files to specific points in each patch file (for example to setup NLS at start, recompile invalid objects before mviews, or increase APEX app version after APEX deployment...), anything you would include in every patch
- you can specify patch scripts for specific card numbers, these scripts will be added to a specific point in patch file just for this card (typically used for ALTER statements after tables or DML statements before APEX installation...), anything you need to add just once for a specific patch
- files will be sorted properly so the invalidated objects and errors are minimized, grants are added automatically, some other source modifications will happen, variables in templates will be replaced, ALTER statements in scripts will be wrapped in a repeatable blocks...
- if you need to do some data changes you have to write the script for that yourself, except tracked data files (see [export_data](./export_data.md))
- you can also deploy it to any known environment you can access without any pipeline infrastructure
- if your patch is not deployed right away, you might face issues on deloyment later, ADT provides several mechanisms how to mitigate this

To see all available options, run script without arguments:
```
adt patch
```

Typical use would be:
```
adt patch -patch {CARD_NUMBER} -create
```

The output would be a list of matching commits, patch file in your patch folder and snapshot of each file in snapshots/ subfolder.
The patch file will contain the overview at top so you can see what is planned, it will be enriched with prompts so you don't get lost while reading the logs, it would also contain the source of the files (commit numbers) so you have clear path to source.

If you are trying to deploy the patch, there will be some additional checks. More on that later.

&nbsp;

## Purpose

- connect to your Git repository and pull relevant commits
  - based on the commit message, commit hash or commit number(s)
  - you can request specific branch, otherwise the active will be used
- create a patch file for each schema used
  - order of the objects will be based on the patch template (see config) and object dependencies, so you don't have to worry about the correct order either
  - copy all relevant files to snapshot folder so you can keep working on the originals and you have a proof what was released
  - these files are based on files from the commit, so if you don't commit whole file, the uncommitted files wont be in patch (you can override this with -local flag which will use your local files)
  - automatically add grants for used objects
  - it also creates the release notes based on your commits
- for APEX add some scripts around to setup workspace properly
  - install shared components first, pages as last
  - delete installed pages if they exist
  - change page creation/audit columns to patch code and date so you know by which patch was the page changed
  - change application version to current date and patch code (via patch template)
  - set requested authentication scheme, keep sessions alive...
  - you can set pre/post APEX scripts through patch template folder (see below)

&nbsp;

## Patch template & scripts

You can create a patch template, which is a list of folders and files which will be added to each your patch at specific point, which depends on object type/group and timing (before, after). All files and subfolders will be sorted alpabethically.

You can change the order of objects via the patch_map in your config file.
Typically it would go in this order:

```
patch_map:
    sequences:          # group name
        - SEQUENCE      # object type
    tables:
        - TABLE
    types:
        - TYPE
        - TYPE BODY
    synonyms:
        - SYNONYM
    objects:
        - VIEW
        - PROCEDURE
        - FUNCTION
        - PACKAGE
        - PACKAGE BODY
    triggers:
        - TRIGGER
    mviews:
        - MVIEW LOG
        - MATERIALIZED VIEW
    indexes:
        - INDEX
    data:
        - DATA
    grants:
        - GRANT
    jobs:
        - JOB
```

So in your `patch_template/` folder you can create subfolders like `tables_before/`, `tables_after/`, `objects_after/`...

Same logic is used for `patch_scripts/{$CARD_NUMBER}/`, you just need to add the folder matching your card number.

&nbsp;

## Issues

If you just change the objects grants and not the object itself, the grants will not make it to do patch. In that case, you can add your whole grant file to patch_scripts folder for the specific patch or into patch template for all patches. Symbolic links are not supported yet.

