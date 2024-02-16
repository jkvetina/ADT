# Patch

The idea behind this is to focus on your job as a developer and don't worry about mundane tasks like creating patch files manually.
This feature does not connect to the database, it gets all the information from your Git repo, the folders and the config file.
So to make this work, you must be using Git. In future the BitBucket will be also supported.

Multiple schemas are supported and there are plenty of config options available to customize patching.

&nbsp;

## Workflow

- you will do your changes on database objects and/or APEX applications as usual in any tool you prefer
- you will [export](./export.md) and commit your changes in Git (ideally with the card number and meaningful description for release notes)
- whenever you want to release the changes, you will run [patch.py](../patch.py) and this little magic script will create a patch file for you
- if you need to do some data changes you have to write the script for that yourself, except tracked data files (see [export_data](./export_data.md))

&nbsp;

## Purpose

- connect to your Git repository and pull relevant commits
  - based on the commit message, commit number(s) or calendar days (multiple inputs are supported)
  - you can request specific branch, otherwise the active will be used
- create a patch file for each schema used
  - order of the objects will be based on the patch template (see config) and object dependencies, so you don't have to worry about the correct order either
  - copy all relevant files to snapshot folder so you can keep working on the originals
  - automatically add grants for used objects
  - it also creates the release notes based on your commits
- for APEX add some scripts around to setup workspace properly
  - install shared components first, pages as last
  - delete installed pages if they exist
  - change page creation/audit columns to patch code and date so you know by which patch was the page changed
  - change application version to current date and patch code
  - set requested authentication scheme, keep sessions alive...
  - you can set pre/post APEX scripts through patch template folder (see below)

&nbsp;

## Issues

The changes in patch are based on commits, but changed files are copied from the current files (which might include uncommitted changes). So just be aware of that.

Also if you just change the objects grants and not the object itself, the grants will not make it to do patch.

