# Install guide

## How to install

- clone this repo (lets say you clone it here: ~/Documents/ADT/)
- install any Git client, go for [GitHub Desktop](https://desktop.github.com) if you are new to this
- install [Python 3.11](https://www.python.org/downloads/release/python-3118/) (and not 3.12 or higher)
- install [SQLcl 23.4](https://www.oracle.com/database/sqldeveloper/technologies/sqlcl/download/)
- install [Instant Client 19.16](https://www.oracle.com/database/technologies/instant-client/downloads.html) (for thick connections only, you might need Java too)
- make sure you have executables of Python, Git, Instant Client and SQLcl in your path
- install Python modules (like OracleDB) used by the ADT:

```
pip3 install --upgrade pip
pip3 install -r ~/Documents/ADT/requirements.txt --upgrade
```

- open your `.zshrc` or `.bash_profile` and add lines from .zshrc section below

&nbsp;

## Modify your .zshrc file

- if you are on Windows, you have to create equivalent of this
- adjust paths to your locations

```
#export LANG=en_US.UTF-8
#export ARCH=x86_64
export ORACLE_HOME=~/instantclient_19_16
export DYLD_LIBRARY_PATH=$ORACLE_HOME
export LD_LIBRARY_PATH=$ORACLE_HOME
export OCI_LIB_DIR=$ORACLE_HOME
export OCI_INC_DIR=$ORACLE_HOME
export PATH=$PATH:$ORACLE_HOME:~/sqlcl/bin
export DBVERSION=19

alias python=/Library/Frameworks/Python.framework/Versions/3.11/bin/python3

export ADT_KEY=PASSWORD     # your password for encrypting/decrypting connections
export ADT_ENV=DEV          # your default environment name

function adt {              # add function so you can keep your prompts clean
    script=$1
    shift
    clear; python ~/Documents/ADT/$script.py "$@"
}
```

&nbsp;

## Configure ADT

- create connection to your database

```
cd ~/Documents/YOUR_PROJECT_REPO/; adt config -version
cd ~/Documents/YOUR_PROJECT_REPO/; adt config
```

&nbsp;

## Explore actions

- explore other actions (all .py files in the ADT root)
- if you run any program without parameters, it will show you the help

Some examples:

```
# recompile invalid objects on DEV
cd ~/Documents/YOUR_PROJECT_REPO/; adt recompile -target DEV

# export APEX application 100
cd ~/Documents/YOUR_PROJECT_REPO/; adt export_apex -app 100 -split -full
```

