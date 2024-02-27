# Install guide

## Assumptions

- you have Git installed and you are familiar using it
    - go for [GitHub Desktop](https://desktop.github.com) if needed
- you know credential for connecting to your database

&nbsp;

## How to install

- clone this repo
- install neccessary tools like Python and SQLcl and put them in your path
- for thick connections you would need Oracle Instant Client


&nbsp;

## Bash

Open your `.zshrc` or `.bash_profile` and add your password for encrypting/decrypting connections.

```
export ADT_KEY=PASSWORD
```

Also add "adt" function so you can keep your prompts clean.

```
function adt {
    script=$1
    shift
    clear; python ~/Documents/PROJECTS/ADT/$script.py "$@"
}
```

So instead of:\
`clear; python ~/Documents/PROJECTS/ADT/recompile.py -env DEV`\
you would just write:\
`adt recompile -env DEV`

&nbsp;

## Quick start guide

- run `python config.py` which will guide you through the setup
    - read more about config file if needed
- run `python export.py` to export database and/or APEX into your repo
- explore other actions

