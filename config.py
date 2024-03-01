# coding: utf-8
import sys, os, re, argparse, datetime, timeit, pickle
import yaml         # pip3 install pyyaml       --upgrade
import git          # pip3 install GitPython    --upgrade
#
from lib import wrapper
from lib import util

#
#                                                      (R)
#                      ---                  ---
#                    #@@@@@@              &@@@@@@
#                    @@@@@@@@     .@      @@@@@@@@
#          -----      @@@@@@    @@@@@@,   @@@@@@@      -----
#       &@@@@@@@@@@@    @@@   &@@@@@@@@@.  @@@@   .@@@@@@@@@@@#
#           @@@@@@@@@@@   @  @@@@@@@@@@@@@  @   @@@@@@@@@@@
#             \@@@@@@@@@@   @@@@@@@@@@@@@@@   @@@@@@@@@@
#               @@@@@@@@@   @@@@@@@@@@@@@@@  &@@@@@@@@
#                 @@@@@@@(  @@@@@@@@@@@@@@@  @@@@@@@@
#                  @@@@@@(  @@@@@@@@@@@@@@,  @@@@@@@
#                  .@@@@@,   @@@@@@@@@@@@@   @@@@@@
#                   @@@@@@  *@@@@@@@@@@@@@   @@@@@@
#                   @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@.
#                    @@@@@@@@@@@@@@@@@@@@@@@@@@@@@
#                    @@@@@@@@@@@@@@@@@@@@@@@@@@@@
#                     .@@@@@@@@@@@@@@@@@@@@@@@@@
#                       .@@@@@@@@@@@@@@@@@@@@@
#                            jankvetina.cz
#                               -------
#
# Copyright (c) Jan Kvetina, 2024
# https://github.com/jkvetina/ADT
#

class Config(util.Attributed):

    # some arguments could be set on the OS level
    os_prefix       = 'ADT_'
    os_args         = ['REPO', 'CLIENT', 'PROJECT', 'ENV', 'BRANCH', 'SCHEMA', 'KEY']

    # list connection files, where to search for DB connections
    connection_files = [
        #'{$ROOT}config/{$INFO_CLIENT}/connections.yaml',
        #'{$ROOT}config/{$INFO_CLIENT}/connections_{$INFO_PROJECT}.yaml',
        '{$INFO_REPO}config/connections.yaml',                                      # repo
    ]

    # default location for new connections
    connection_default = '{$INFO_REPO}config/connections.yaml'
    connection         = {}    # active connection

    # search for config files in current folder
    config_files = [
        #'{$ROOT}config/default_config.yaml',
        #'{$ROOT}config/{$INFO_CLIENT}/config.yaml',
        #'{$ROOT}config/{$INFO_CLIENT}/config_{$INFO_PROJECT}.yaml',
        #'{$ROOT}config/{$INFO_CLIENT}/config_{$INFO_PROJECT}_{$INFO_ENV}.yaml',
        '{$INFO_REPO}config/config.yaml',                                           # repo
        '{$INFO_REPO}config/config_{$INFO_ENV}.yaml',                               # repo
    ]

    # when schema is set, run init_config again to allow wchema overrides
    config_overrides = [
        #'{$ROOT}config/{$INFO_CLIENT}/config_{$INFO_PROJECT}_{$INFO_SCHEMA}.yaml',
        #'{$ROOT}config/{$INFO_CLIENT}/config_{$INFO_PROJECT}_{$INFO_SCHEMA}_{$INFO_ENV}.yaml',
        '{$INFO_REPO}config/config_{$INFO_SCHEMA}.yaml',
        '{$INFO_REPO}config/config_{$INFO_SCHEMA}_{$INFO_ENV}.yaml',                # repo
    ]

    # define and categorize arguments
    required_args = {
        'normal'    : ['env', 'user', 'pwd', 'hostname', 'port', 'service'],
        'legacy'    : ['env', 'user', 'pwd', 'hostname', 'port', 'sid'],
        'cloud'     : ['env', 'user', 'pwd',                     'service', 'wallet', 'wallet_pwd'],
    }
    common_args = [
        'env',
        'lang',
        'hostname',
        'port',
        'service',
        'sid',
        'wallet',
        'wallet_pwd',
        'wallet_encrypted',
    ]
    schema_args = [
        'user',
        'pwd',
        'pwd_encrypted',
        'prefix',           # specify the major things (differences) in connections.yaml
        'ignore',           # but adjust the details in config.yaml
        'folder',
        'workspace',
        'app',
    ]
    password_args = [
        'key',
        'pwd',
        'wallet_pwd'
    ]
    password_flags = {
        'pwd'           : 'pwd_encrypted',
        'wallet_pwd'    : 'wallet_encrypted',
    }

    # move some command line args to info group
    info_attributes = [
        'repo',
        'client',
        'project',
        'env',
        'branch',
        'schema',
        'workspace',
    ]



    def __init__(self, parser, ignore_timer = False):
        self.ignore_timer = ignore_timer
        if not (self.ignore_timer):
            self.start_timer = timeit.default_timer()

        # parse arguments from command line
        self.args = vars(parser.parse_args())
        if not ('decrypt' in self.args):
            self.args['decrypt'] = False

        # merge with environment variables
        for arg in self.os_args:
            if not (arg.lower() in self.args) or self.args[arg.lower()] == None:
                self.args[arg.lower()] = os.getenv(self.os_prefix + arg.upper())
        #
        if self.args['env'] == None:
            self.args['env'] = 'DEV'
        #
        self.args   = util.Attributed(self.args)    # for passed attributes
        self.config = util.Attributed({})           # for user config
        self.info   = util.Attributed({})           # for info group
        self.debug  = self.args.debug
        #
        if self.debug:
            util.print_header('ARGS:')
            util.print_args(self.args, skip_keys = self.password_args)

        # set info group from command line arguments
        for arg in self.info_attributes:
            setattr(self.info, arg, self.args.get(arg, '') or '')

        # repo attributes
        self.root           = util.fix_path(os.path.dirname(os.path.realpath(__file__)))
        self.repo_root      = util.fix_path(self.args.repo or os.path.abspath(os.path.curdir))
        self.repo           = None      # set through init_repo()
        self.conn           = None      # database connection object

        # if we are using ADT repo for connection file, we have to know these too
        if self.repo_root == self.root:
            util.assert_(self.args.client,  'MISSING ARGUMENT: CLIENT')
            util.assert_(self.args.project, 'MISSING ARGUMENT: PROJECT')
            util.assert_(self.args.env,     'MISSING ARGUMENT: ENV')

        # connect to repo, we need valid repo for everything
        # check connections before config, since we can change schema here
        # check config file, rerun this when specific schema is processed to load schema overrides
        self.init_repo()
        if __name__ != "__main__":
            self.init_connection()
        self.init_config()
        #
        if self.debug:
            util.print_header('INFO GROUP:')
            util.print_args(self.info)

        # different flow for direct call
        if __name__ == "__main__":
            # import OPY connection file, basically adjust input arguments and then create a connection
            if 'opy' in self.args and self.args.opy:
                self.import_connection()

            # create or update connection file
            elif self.args.create:
                self.create_connection()

            # check connection file and test connectivity
            self.init_connection()
            self.conn = self.db_connect()

            # check APEX args (show matching apps)
            if self.connection.get('app') != None or self.connection.get('workspace'):
                self.check_apex()



    def __del__(self):
        if not (self.ignore_timer):
            print('\nTIMER: {}s\n'.format(int(round(timeit.default_timer() - self.start_timer + 0.5, 0))))



    def init_connection(self, env_name = '', schema_name = ''):
        if env_name == '':
            env_name = self.info.env
        if schema_name == '':
            schema_name = self.info.schema or ''

        # search for connection file
        for file in self.replace_tags(list(self.connection_files)):  # copy, dont change original
            if ('{$' in file or not os.path.exists(file)):
                continue
            #
            with open(file, 'rt', encoding = 'utf-8') as f:
                data = dict(util.get_yaml(f, file))

                # check environment
                if not (env_name in data):
                    if self.args.create:
                        data[env_name] = {'schemas' : {schema_name : {}}}
                if not (env_name in data):
                    util.raise_error('UNKNOWN ENVIRONMENT NAME')

                # make yaml content more flat
                self.connection = {}
                self.connection['file'] = file
                self.connection['key']  = self.args.key
                #
                for env, args in data.items():
                    if env != env_name:
                        continue
                    #
                    for arg, value in args.items():
                        if not isinstance(value, dict):
                            self.connection[arg] = value

                    # find first schema
                    if schema_name == '' and 'schemas' in data[env_name]:
                        schema_name = list(data[env_name]['schemas'].keys())[0]
                        self.info.schema = schema_name
                    break

                # process schema overrides
                if 'schemas' in data[env_name] and self.info.schema != None:
                    schema_name = schema_name or self.info.schema
                    if not (schema_name in data[env_name]['schemas']):
                        util.raise_error('UNKNOWN SCHEMA - {}'.format(schema_name), '{}\n'.format(file))
                #
                self.info.schema = schema_name
                for arg, value in data[env_name]['schemas'].get(schema_name, {}).items():
                    self.connection[arg] = value

                # fix wallet paths
                if 'wallet' in self.connection:
                    wallet = self.connection['wallet']
                    if not os.path.exists(wallet):
                        wallet = os.path.dirname(file) + '/' + wallet
                        if os.path.exists(wallet):
                            self.connection['wallet'] = wallet

                # description for the screen
                self.connection['desc'] = '{}, {}'.format(schema_name or self.connection['user'], env_name)
        #
        if self.debug:
            util.print_header('CONNECTION:')
            util.print_args(self.connection, skip_keys = self.password_args)

        # check presence, at least one file is required
        if self.connection.get('file', '') == '':
            util.raise_error('CONNECTION FILE REQUIRED:', '\n'.join(self.connection_files))

        # if key is a file, retrieve content and use it as a key
        if (not ('key' in self.connection) or self.connection['key'] == None):
            self.connection['key'] = self.args.key or ''
        if self.connection['key'] != '':
            if os.path.exists(self.connection['key']):
                with open(self.connection['key'], 'rt', encoding = 'utf-8') as f:
                    self.connection['key'] = f.read().strip()



    def create_connection(self, output_file = None):
        env_name        = self.info.env
        schema_name     = self.args.schema or self.args.user
        #
        util.assert_(env_name,      'MISSING ARGUMENT: ENV')
        util.assert_(schema_name,   'MISSING ARGUMENT: SCHEMA')
        #
        missing_args    = {}
        passed_args     = {
            'schemas'   : {schema_name : {}},
            'lang'      : '.AL32UTF8',          # default lang
            'thick'     : self.args.thick,
        }

        # check required arguments
        for type, arguments in self.required_args.items():
            missing_args[type]  = []
            for arg in arguments:
                if not (arg in self.args) or self.args[arg] == None or self.args[arg] == '':
                    missing_args[type].append(arg)

        # create guidance for missing args
        found_type = None
        for type, arguments in missing_args.items():
            if len(arguments) == 0:
                found_type = type
                break
        #
        if not found_type:
            for type, arguments in missing_args.items():
                if type != found_type and len(arguments) > 0:
                    print('MISSING ARGUMENTS FOR {} CONNECTION:'.format(type.upper()))
                    for arg in arguments:
                        print('   - {}'.format(arg))
                    print()
            #
            util.raise_error('CAN\'T CONTINUE')

        # create config structure
        for arg in self.args:
            value = self.args[arg]
            if value == '' or value == None:
                continue

            # encrypt passwords and set correct flags
            flag = ''
            if arg in self.password_flags:
                flag = self.password_flags[arg]
                if not (self.args.decrypt) and arg in self.password_args:
                    value = util.encrypt(value, self.args.key)

            # add to the proper node
            for arg in [arg, flag]:
                if arg == flag:
                    value = 'Y' if not self.args.decrypt else ''
                if value != '':
                    if arg in self.common_args:
                        passed_args[arg] = value
                    elif arg in self.schema_args:
                        passed_args['schemas'][schema_name][arg] = value
                        passed_args.pop(arg, None)

        # prepare target folder
        file    = self.replace_tags(output_file or self.connection_default)
        dir     = os.path.dirname(file)
        #
        if not os.path.exists(dir):
            os.makedirs(dir)

        # load current file
        connections = {}
        if os.path.exists(file):
            with open(file, 'rt', encoding = 'utf-8') as f:
                data = util.get_yaml(f, file)
                for env, arguments in data:
                    connections[env] = arguments

        # merge = overwrite root attributes, but keep other schemas
        backup_schemas = {}
        if env_name in connections:
            backup_schemas = connections[env_name].get('schemas', {})
        connections[env_name] = dict(passed_args)   # copy
        for schema, data in backup_schemas.items():
            if schema != schema_name:
                connections[env_name]['schemas'][schema] = data

        # show parameters
        util.print_header('CREATING {} CONNECTION:'.format(found_type.upper()))
        print('{}\n'.format(file))

        # store connection parameters in the yaml file
        with open(file, 'wt', encoding = 'utf-8') as f:
            # convert dict to yaml string
            payload = yaml.dump(connections, allow_unicode = True, default_flow_style = False, indent = 4) + '\n'
            payload = util.fix_yaml(payload)
            f.write(payload)



    def import_connection(self):
        # find OPY pickle file
        pickle_file = self.args.opy
        if not os.path.exists(pickle_file) and os.path.splitext(pickle_file)[1] != '.conf':
            util.raise_error('MISSING OR INVALID OPY FILE')

        # check the file content
        args = {}
        try:
            with open(pickle_file, 'rb') as f:
                args = pickle.load(f).items()
        except Exception:
            util.raise_error('INVALID OPY FILE',
                'expecting .conf file created by OPY tool')

        # import data as arguments
        for arg, value in args.items():
            arg = arg.replace('host',   'hostname')
            arg = arg.replace('target', 'repo')
            #
            self.args[arg] = value

        # need to set the repo to have correct paths
        self.repo_root = self.args['repo']

        # create new file as user would actually pass these arguments
        self.create_connection()



    def db_connect(self, ping_sqlcl = False, silent = False):
        return wrapper.Oracle(dict(self.connection), debug = self.debug, ping_sqlcl = ping_sqlcl, silent = silent)



    def check_apex(self):
        args = {
            'workspace' : self.connection.get('workspace'),
            'apps'      : ',{},'.format(self.connection.get('app')).replace(',,', ''),
        }
        data = self.conn.fetch_assoc("""
            SELECT a.workspace, a.owner, a.application_id AS app_id, a.alias, a.version
            FROM apex_applications a
            WHERE (a.workspace = :workspace OR :workspace IS NULL)
                AND (:apps LIKE '%,' || TO_CHAR(a.application_id) || ',%' OR :apps IS NULL)
        """, **args)
        #
        if len(data) > 0:
            util.print_header('APEX APPLICATIONS:')
            util.print_table(data, self.conn.cols)



    def init_config(self):
        self.track_config = {}
        if self.debug:
            util.print_header('SEARCHING FOR CONFIG FILE')

        # search for config file(s)
        for file in self.replace_tags(list(self.config_files)):  # copy
            if not ('{$' in file) and os.path.exists(file):
                self.apply_config(file)

        # allow schema overrides
        if self.info.schema:
            for file in self.replace_tags(list(self.config_overrides)):  # copy
                if not ('{$' in file) and os.path.exists(file):
                    self.apply_config(file)

        # reconnect to repo, it could change the location
        if self.debug:
            print()



    def apply_config(self, file):
        if self.debug:
            print(file, '\n')
        #
        with open(file, 'rt', encoding = 'utf-8') as f:
            self.track_config[file] = {}
            for key, value in util.get_yaml(f, file):
                #setattr(self.config, key, value)
                self.config[key]                = value
                self.track_config[file][key]    = self.config[key]

                # convert date formats to dates
                if key.startswith('today'):
                    try:
                        self.config[key] = datetime.datetime.today().strftime(value)
                    except:
                        util.raise_error('INVALID DATE FORMAT', key + '=' + value)

            # translate tags in multiple loops to fix possible issues with wrong order and inner tags
            self.config = self.replace_tags(self.config, loops = 3)



    def init_repo(self):
        util.assert_(self.repo_root, 'MISSING ARGUMENT: REPO')
        if self.debug:
            util.print_header('SEARCHING FOR GIT REPO')

        # setup and connect to the repo
        try:
            self.repo       = git.Repo(self.repo_root)
            self.repo_url   = self.repo.remotes[0].url
            if self.repo.bare:
                raise Exception()
        except:
            util.raise_error('INVALID GIT REPO',
                'change current folder to the repo you would like to use.',
                'or specify repo in args or system arguments')

        # get current account
        with self.repo.config_reader() as git_config:
            self.repo_user_name = git_config.get_value('user', 'name')
            self.repo_user_mail = git_config.get_value('user', 'email')
        #
        if self.debug:
            util.print_args({
                'REPO'      : self.repo_url,
                'BRANCH'    : self.repo.active_branch,
                'USER'      : self.repo_user_name,
            })



    def replace_tags(self, payload, obj = None, ignore_missing = True, loops = 2):
        if obj == None:
            obj = self

        # if payload is a list/dict, process all items individually
        if isinstance(payload, list):
            for i, item in enumerate(payload):
                payload[i] = self.replace_tags(item, obj = obj, ignore_missing = ignore_missing)
            return payload
        #
        elif isinstance(payload, dict):
            for key, value in payload.items():
                payload[key] = self.replace_tags(value, obj = obj, ignore_missing = ignore_missing)
            return payload

        # replace just strings
        if not isinstance(payload, str):
            return payload

        # check passed argument types
        is_object   = str(type(obj)).startswith("<class '__main__.")
        is_dict     = isinstance(obj, dict)

        # extract keys from replacement object/dict (possible tags)
        passed_keys = []
        if is_dict:
            passed_keys = obj.keys()                # get dictionary keys
        elif is_object:
            passed_keys = obj.__dict__.keys()       # get object attributes

        # extract unique tags
        found_tags = list(dict.fromkeys(re.findall('\{\$[A-Z0-9_]+\}', payload)))
        if len(found_tags) > 0:
            for tag in found_tags:
                if tag in payload:
                    attribute   = tag.lower().replace('{$', '').replace('}', '')    # just the name
                    value       = tag                                               # keep original as fallback

                    # search in info & config first
                    for group in ['info', 'config']:
                        attr = attribute.replace('info_', '')
                        if group in obj and attr in obj[group]:
                            # find value in config first
                            if attr in obj[group]:
                                value = obj[group][attr]
                    #
                    if value == tag:
                        # find value in passed object
                        if is_object and attribute.lower() in passed_keys:
                            value = str(getattr(obj, attribute.lower()))
                        elif is_dict and attribute.lower() in passed_keys:
                            value = obj[attribute.lower()]

                    # replace all tags "{$...}" with passed object attribute values
                    if value != None:
                        payload = payload.replace(tag, value)

        # verify left over tags
        payload = payload.strip().rstrip('-').rstrip('_').strip()
        if '{$' in payload:
            if loops > 0:
                return self.replace_tags(payload, obj = obj, ignore_missing = ignore_missing, loops = loops - 1)
            if not ignore_missing:
                util.raise_error('LEFTOVER TAGS', payload)
        #
        return payload



    def replace_dict(self, payload, translation):
        regex = re.compile('|'.join(map(re.escape, translation)))
        return regex.sub(lambda match: translation[match.group(0)], payload)



if __name__ == "__main__":
    # parse arguments
    parser = argparse.ArgumentParser()

    # actions and flags
    parser.add_argument('-debug',       help = 'Turn on the debug/verbose mode',    default = False, nargs = '?', const = True)
    parser.add_argument('-create',      help = 'Create or update connection',       default = False, nargs = '?', const = True)
    parser.add_argument('-opy',         help = 'To import connection details from OPY file')
    parser.add_argument('-decrypt',     help = 'Show passwords decypted',           default = False, nargs = '?', const = True, type = bool)
    parser.add_argument('-key',         help = 'Key or key location to encypt passwords')

    # to specify environment
    parser.add_argument('-client',      help = 'Client name')
    parser.add_argument('-project',     help = 'Project name')
    parser.add_argument('-env',         help = 'Environment name, like DEV, UAT, LAB1...')
    parser.add_argument('-repo',        help = 'Path to your project repo')
    parser.add_argument('-branch',      help = 'Repo branch')
    parser.add_argument('-schema',      help = 'Schema/connection name (if you are using multiple schemas)')
    #
    parser.add_argument('-prefix',      help = 'Export objects with listed prefix(es)')
    parser.add_argument('-ignore',      help = 'Ignore objects with listed prefix(es)')
    parser.add_argument('-folder',      help = 'Folder for exported objects (for multiple schemas)')
    parser.add_argument('-workspace',   help = 'APEX workspace')
    parser.add_argument('-app',         help = 'APEX app(s) to export as default')

    # for database connections
    parser.add_argument('-user',        help = 'User name')
    parser.add_argument('-pwd',         help = 'User password')
    parser.add_argument('-hostname',    help = 'Hostname')
    parser.add_argument('-port',        help = 'Port',                        type = int, default = 1521)
    parser.add_argument('-service',     help = 'Service name')
    parser.add_argument('-sid',         help = 'SID')
    parser.add_argument('-wallet',      help = 'Wallet file')
    parser.add_argument('-wallet_pwd',  help = 'Wallet password')
    parser.add_argument('-thick',       help = 'Thick client path, \'Y\' for auto resolve')
    #
    Config(parser)

