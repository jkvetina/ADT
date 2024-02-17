# Config parameters

The config file can contain either connections info or repo settings or both and it can be stored on several places depending on how much of it would you like to reuse.
The structure below allows you to set settings for the client and then override what you need for specific projects, schemas or/and environments.
You can store the config files either together with your project or in the ADT repo (or you can split them however you like, to keep connections in ADT repo and other settings together with your project).

Passwords used for connecting to the database are encrypted by a key, which can be an command line argument, a runtime prompt or a path to a key file. You can store and share your config files safely.

The config files are processed in this order:

- `{$ROOT}config/default_config.yaml`
- `{$ROOT}config/{$INFO_CLIENT}/{}.yaml`
- `{$ROOT}config/{$INFO_CLIENT}/{}_{$INFO_PROJECT}.yaml`
- `{$ROOT}config/{$INFO_CLIENT}/{}_{$INFO_PROJECT}_{$INFO_ENV}.yaml`
- `{$ROOT}config/{$INFO_CLIENT}/{}_{$INFO_PROJECT}_{$INFO_SCHEMA}.yaml`
- `{$ROOT}config/{$INFO_CLIENT}/{}_{$INFO_PROJECT}_{$INFO_SCHEMA}_{$INFO_ENV}.yaml`
- `{$INFO_REPO}config/{}.yaml`
- `{$INFO_REPO}config/{}_{$INFO_ENV}.yaml`
- `{$INFO_REPO}config/{}_{$INFO_SCHEMA}.yaml`
- `{$INFO_REPO}config/{}_{$INFO_SCHEMA}_{$INFO_ENV}.yaml`

For each connection you will have to provide these:

- project name, client name, environment name, repo branch name (optional)
- schema and password
- for on premise - hostname, port, service name or sid
- for cloud - wallet path, password, service name
