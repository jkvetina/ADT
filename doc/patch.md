# Patch

The idea behind is to focus on your job as a developer and don't worry on mundane tasks like creating patch files manually.
Multiple schemas are supported and there are plenty of config options available to customize this.

There is just one assumption to make this work, you must be using Git for your project. In future I plan to support also the BitBucket.

&nbsp;

## Workflow

- you will do your changes on database objects and/or APEX applications as usual
- you will commit your changes in Git (ideally with the card number and description)
- whenever you want to release the changes, you will run patch.py and this little magic script will create a patch file for you

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
  - delete installed pages if they exists
  - change page creation/audit columns to patch code and date so you know by which patch was the page changed
  - change application version to current date and patch code
  - set requested authentication scheme

