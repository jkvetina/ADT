# Patch

The idea behind is to focus on your job as a developer and don't worry on mundane tasks like creating patch files manually.
So the workflow is:

- you will do your changes on database objects and/or APEX applications as usual
- you will commit your changes in Git (ideally with the card number and description)
- whenever you want to release the changes, you will run patch.py and this little magic script will create a patch file for you
- multiple schemas are supported and there are plenty of config options available to customize this

There is just one assumption to make this work, you must be using Git for your project.

&nbsp;

## More details

- connect to your Git repository
- pull relevant commits
  - based on the commit message, commit number(s) or calendar days (multiple inputs are supported)
  - you can request specific branch
- go through all relevant files and sort them by schema
- create a patch file for each schema based on the patch template (see config) and object dependencies
  - copy all relevant files to snapshot folder so you can keep working on the originals
- for APEX add some scripts around to setup workspace properly
  - install pages as last
  - delete installed pages if they exists
  - change page creation to patch code and date so you know by which patch was the page changed
  - change application version to current date and patch code
  - set requested authentication scheme
- automatically add grants for used objects

