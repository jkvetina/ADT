# Config

Config script helps you to setup your project. You have to use it at the start, but there is generally no need to use it after that.

Main use is to setup a connection to your environment. You can connect to both on-premise and OCI. It will kind of guide you to ask for missing parameters.
When you have everything, it will connect and print SYSDATE.

```
adt config
adt config -create
```

For each connection you will have to provide these:

- project name, client name, environment name, repo branch name (optional)
- schema and password
- for on premise - hostname, port, service name or sid
- for cloud - wallet path, password, service name

Passwords used for connecting to the database can be encrypted by a key, which can be an command line argument or OS variable.
If value is a valid path to a file, than the file content is used as a key. You can store and share your config files safely.
Once you encrypt your connections, you have to pass the key to each script.

You can encrypt (and decrypt) database and wallet passwords with a passed key:
```
adt config -create -key {PASSWORD}
```

But I would recommend to store your key in ADT_KEY OS variable, then you dont have to pass it at all.
```
export ADT_KEY = SECRET_PASSWORD_TO_ENCRYPT_OTHER_PASSWORDS
adt config -create
```

If you are using wallet, you have to copy it zipped and unzipped into yout project config/ folder.

## Config folder

Whole application use .yaml files for all internal files, so you should be able to edit them directly on your own.
All config things and some temp files are stored in the config/ folder.

`config/connections.yaml` - contains all your connections for project\
`config/config.yaml` - contains settings specific for your project, what is missing will be taken from same file in ADT repo\
`config/patch_template/` - is a folder used for patching, check patch.md for more details

There are some other files in config repo, don't worry about them now.

## Version check

You can check version of components used by ADT:
```
adt config -version
```

## Variables

In these .yaml files you can use following variables.
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
| `info_env`     | current environment
| `info_repo`    | current repo
| `info_branch`  | current branch

And finally some date formats (adjustable in the config file):

| Variable       | Description
| :------------- | :----------
| `date_today`   | YYYY-MM-DD
| `date_time`    | YYYY-MM-DD_HH24-MI
| `date_custom`  | whatever you decide...

