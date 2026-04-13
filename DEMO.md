# Prerequisites

- create 2 environments (DEV, UAT = DEV23, DEV24)
- create DEMO Git repo
- use existing schema
  - use the Trips Planning app


# #1 – Extract Database Objects

- show the table structure
  - cleanup files from the junk code
- pull database objects
- show different shortcuts like -recent, -type, -name...
- create new objects in database, change objects
  - export & commit


# #2 – Extract APEX

- export existing app
  - show different formats
  - show progress
- create APEX page, LOV with view...
  - export & commit
  - CHECK/FIX FULL APP DEPLOY
- make changes to objects
  - change a table -> auto alter
- apex page signatures – changed by/at
  - app version


# #3 – Export Data

- create a data changes


# #4 – Patching

- create a patch for DB objects, deploy
  - manual patch verification & changes
    - committed files warning
  - show files sorted by dependencies
  - redo existing patch
  - create another patch
- patch scripts, generated diffs
- patch templates


# #5 – Config

- show config, connection file
  - CARD-#, adjust in config.yaml
  - objects prefix
  - patch cards prefix
- other programs
  - calendar, recompile...
  - live upload
  - search repo, search APEX

