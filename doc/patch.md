# Patch

The idea behind this is to focus on your job as a developer and don't worry about mundane tasks like creating patch files manually.

This feature does not connect to the database at all, it gets all the information from your Git repo, the folders, files and the config file.
So to make this work, you must be using Git (BitBucket is supported).

Multiple schemas are supported. Each achema and each APEX application gets its own patch file.
There are plenty of config options available to customize patching.

&nbsp;

## Workflow

- you will do your changes on database objects and/or APEX applications as usual in any tool you prefer
- you will [export](./export.md) and commit your changes in Git (ideally with the card number and meaningful description for release notes, you will use this card number later to identify which commits will be part of your patch)
- whenever you want to release the changes, you will run [patch.py](../patch.py) and this little magic script will create a patch file for you
- you can specify patch templates which basically adds template files to specific points in each patch file (for example to setup NLS at start, recompile invalid objects before mviews, or increase APEX app version after APEX deployment...)
- you can specify patch scripts for spacific card numbers, these scripts will be added to a specific point in patch file just for this card (typically used for ALTER statements after tables or DML statements before APEX installation...)
- if you need to do some data changes you have to write the script for that yourself, except tracked data files (see [export_data](./export_data.md))

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

