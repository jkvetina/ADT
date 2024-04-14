# coding: utf-8
import sys, os, re, argparse, datetime, timeit, pickle, io, requests, copy, json
import git          # pip3 install GitPython    --upgrade
#
from lib import wrapper
from lib import util
from lib import messages
from lib import queries_recompile as query
from lib.file import File

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

    # search for config files in current folder
    config_files = [
        '{$ROOT}config/config.yaml',
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

    # map for root arguments
    args_map = {
        'db': {
            'hostname'  : 'hostname',
            'port'      : 'port',
            'service'   : 'service',
            'sid'       : 'sid',
            'lang'      : '',
            'thick'     : 'thick',
        },
        'wallet': {
            'wallet'        : 'wallet',
            'wallet_pwd'    : 'wallet_pwd',
            'wallet_pwd!'   : '',       # encrypted flag
        },
        'defaults': {
            'schema_apex'   : '',
            'schema_db'     : '',
        },
        'schemas' : {},
    }

    # map for schema argments
    args_schema = {
        'apex': {
            'workspace' : 'workspace',
            'app'       : 'app',
        },
        'db': {
            'user'      : 'user',
            'pwd'       : 'pwd',
            'pwd!'      : '',       # encrypted flag
        },
        'export': {
            'prefix'    : 'prefix',
            'subfolder' : 'subfolder',
            'ignore'    : 'ignore',
        },
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



    def __init__(self, parser = None, args = None):
        self.parser = parser or argparse.ArgumentParser(add_help = False)
        if __name__ == '__main__':
            # actions and flags
            group = self.parser.add_argument_group('MAIN ACTIONS')
            group.add_argument('-show',         help = 'Show connection details',                   type = util.is_boolean, nargs = '?', const = True, default = False)
            group.add_argument('-create',       help = 'Create or update connection',               type = util.is_boolean, nargs = '?', const = True, default = False)
            group.add_argument('-opy',          help = 'Import connection from OPY file',                                   nargs = '?')
            group.add_argument('-init',         help = 'Copy template files to repo folder',                                nargs = '?', const = True, default = False)
            group.add_argument('-version',      help = 'Show versions of used subprograms',         type = util.is_boolean, nargs = '?', const = True, default = False)
            group.add_argument('-utf',          help = 'Check repo files for UTF issues',                                   nargs = '?', const = True, default = False)
            #
            group = self.parser.add_argument_group('SPECIFY ENVIRONMENT DETAILS')
            group.add_argument('-env',          help = 'Environment name like DEV, UAT, LAB1...',                           nargs = '?')
            group.add_argument('-schema',       help = 'Schema/connection name (for multiple schemas)',                     nargs = '?')
            group.add_argument('-repo',         help = 'Path to your project repo',                                         nargs = '?')
            group.add_argument('-branch',       help = 'Repo branch',                                                       nargs = '?')
            group.add_argument('-decrypt',      help = 'Store passwords decypted',                  type = util.is_boolean, nargs = '?', const = True, default = False)
            group.add_argument('-key',          help = 'Key or key location for passwords',                                 nargs = '?')
            #
            group = self.parser.add_argument_group('LIMIT SCOPE')
            group.add_argument('-prefix',       help = 'Export objects with listed prefix(es)',                             nargs = '?')
            group.add_argument('-ignore',       help = 'Ignore objects with listed prefix(es)',                             nargs = '?')
            group.add_argument('-subfolder',    help = 'Subfolder for exported objects (for multiple schemas)',             nargs = '?')
            group.add_argument('-workspace',    help = 'Limit to specific APEX workspace',                                  nargs = '?')
            group.add_argument('-app',          help = 'APEX app(s) to export as default',                                  nargs = '?')
            #
            group = self.parser.add_argument_group('PROVIDE CONNECTION DETAILS')
            group.add_argument('-user',         help = 'User name',                                                         nargs = '?')
            group.add_argument('-pwd',          help = 'User password',                                                     nargs = '?')
            group.add_argument('-hostname',     help = 'Hostname',                                                          nargs = '?')
            group.add_argument('-port',         help = 'Port',                                      type = int,             nargs = '?', default = 1521)
            group.add_argument('-service',      help = 'Service name (provide this or SID)',                                nargs = '?')
            group.add_argument('-sid',          help = 'SID',                                                               nargs = '?')
            group.add_argument('-wallet',       help = 'Wallet file (for cloud connections)',                               nargs = '?')
            group.add_argument('-wallet_pwd',   help = 'Wallet password',                                                   nargs = '?')
            group.add_argument('-thick',        help = 'Thick client path or \'Y\' for auto resolve',                       nargs = '?')
            group.add_argument('-default',      help = 'Mark current DB/APEX schema as default',    type = util.is_boolean, nargs = '?', const = True, default = False)

        # identify program relations
        self.program        = os.path.basename(sys.argv[0]).split('.')[0]
        self.is_curr_class  = self.program == self.__class__.__name__.lower()
        self.start_timer    = timeit.default_timer() if self.is_curr_class else None

        # if we are running the main program
        if self.is_curr_class:
            util.print_header('APEX DEPLOYMENT TOOL: {}'.format(self.program.upper()))

            # add global args
            group = self.parser.add_argument_group('ADJUST SCREEN OUTPUT')
            group.add_argument('-verbose',      help = 'Show more details',                         type = util.is_boolean, nargs = '?', const = True,  default = False)
            group.add_argument('-debug',        help = 'Show even more details and exceptions',     type = util.is_boolean, nargs = '?', const = True,  default = False)
            group.add_argument('-go',           help = 'When you need to run without args',         type = util.is_boolean, nargs = '?', const = True,  default = False)

            # cleanup junk files created on Mac by iCloud sync
            util.remove_cloud_junk()

        # check if any arguments were provided
        if len(sys.argv) == 1:
            self.is_curr_class = False
            util.print_program_help(self.parser, program = self.program)

        # parse arguments from command line
        self.args = vars(self.parser.parse_args(args = args if args != None else None))
        if not ('decrypt' in self.args):
            self.args['decrypt'] = False

        # merge with environment variables
        for arg in self.os_args:
            if not (arg.lower() in self.args) or self.args[arg.lower()] == None:
                value = os.getenv(self.os_prefix + arg.upper())
                if value != None:
                    self.args[arg.lower()] = value
        #
        self.args   = util.Attributed(self.args)    # for passed attributes
        self.config = util.Attributed({})           # for user config
        self.info   = util.Attributed({})           # for info group
        self.debug  = self.args.get('debug')

        # show component versions
        if __name__ == '__main__' and self.args.get('version'):
            self.show_versions()
            util.quit()

        # repo attributes
        self.root           = util.fix_path(os.path.dirname(os.path.realpath(__file__)))
        self.repo_root      = util.fix_path(self.args.get('repo') or os.path.abspath(os.path.curdir))
        self.repo           = None      # set through init_repo()
        self.conn           = None      # database connection object

        # check all repo .sql files for wrong UTF characters
        if self.args.get('utf'):
            self.check_utf_errors()

        # set info group from command line arguments
        for arg in self.info_attributes:
            setattr(self.info, arg, self.args.get(arg, '') or '')

        # load config first
        self.init_config()
        self.info['schema'] = self.args.get('schema', '')   or self.info.get('schema', '')  or self.config.get('default_schema')
        self.info['env']    = self.args.get('env', '')      or self.info.get('env', '')     or self.config.get('default_env')

        # create temp folder
        self.config.sqlcl_root = os.path.abspath(self.config.sqlcl_root)
        if not os.path.exists(self.config.sqlcl_root):
            os.makedirs(self.config.sqlcl_root)

        # structure for dependencies
        self.patch_grants       = self.repo_root + self.config.path_objects + self.config.patch_grants
        self.repo_objects       = {}
        self.repo_files         = {}
        self.dependencies       = {}
        self.objects_todo       = []
        self.objects_processed  = []
        self.objects_path       = []
        self.all_objects_sorted = []

        # some helping files
        self.dependencies_file  = '{}/config/db_dependencies.yaml'.format(self.repo_root)
        self.timers_file        = '{}/config/apex_timers.yaml'.format(self.repo_root)
        self.developers_file    = '{}/config/apex_developers.yaml'.format(self.repo_root)

        # load dependencies from file
        if os.path.exists(self.dependencies_file):
            with open(self.dependencies_file, 'rt', encoding = 'utf-8') as f:
                self.all_objects_sorted = dict(util.get_yaml(f, self.dependencies_file))['sorted']

        # connect to repo, we need valid repo for everything
        self.init_repo()
        if __name__ != '__main__':
            self.init_connection()
            self.get_objects()

        # different flow for direct call
        if __name__ == '__main__':
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

            # copy patch templates and config file(s)
            config_file = '{}/config/config.yaml'.format(self.repo_root)
            if (self.args.init or not os.path.exists(config_file)):
                self.init_files()



    def __del__(self):
        if self.start_timer:
            print('\nTIMER: {}s\n'.format(int(round(timeit.default_timer() - self.start_timer + 0.5, 0))))



    def init_files(self):
        # copy folder structure for patching
        folders = {
            '/config/patch/'            : '/patch/',
            '/config/patch_scripts/'    : '/patch_scripts/',
            '/config/patch_template/'   : '/config/patch_template/',
        }
        for source, target in folders.items():
            source_dir = '{}{}'.format(self.root, source)
            target_dir = self.repo_root + target
            os.makedirs(target_dir, exist_ok = True)
            util.copy_folder(source_dir, target_dir)

        # copy config file
        config_file = '{}/config/config.yaml'.format(self.repo_root)
        source_file = '{}/config/config.yaml'.format(self.root)
        if not os.path.exists(config_file):
            util.copy_file(source_file, config_file)



    def init_connection(self, env_name = '', schema_name = ''):
        # use default values from environment, empty schema can be changed below
        env_name    = env_name      or self.info.env
        schema_name = schema_name   or self.info.schema or ''

        # gather connection details to a single dictionary
        self.connection, schemas = {}, {}
        for file in self.replace_tags(list(self.connection_files)):     # copy so we dont change the original
            if ('{$' in file or not os.path.exists(file)):              # skip files with tags
                continue
            #
            with open(file, 'rt', encoding = 'utf-8') as f:
                conn_src        = dict(util.get_yaml(f, file)).get(env_name, {})
                schemas_src     = {}
                if 'schemas' in conn_src:
                    schemas_src = conn_src.pop('schemas')
                self.connection = {**self.connection, **conn_src}
                schemas         = {**schemas, **schemas_src}

        # check environment
        if len(self.connection.keys()) == 0:
            util.raise_error('UNKNOWN ENVIRONMENT NAME', env_name)

        #  get schema marked as default
        if schema_name == '':
            schema_name = self.connection['defaults'].get('schema_apex' if self.program == 'export_apex' else 'schema_db', '')

        # find first schema on list
        if schema_name == '' and len(schemas.keys()) > 0:
            schema_name = list(schemas.keys())[0]

        # check schema
        if (schema_name == '' or not (schema_name in schemas.keys())):
            util.raise_error('UNKNOWN SCHEMA', schema_name)

        # merge with specific schema and adjust few things
        # flatten the config structure
        self.connection = {
            **self.connection['db'],
            **self.connection.get('defaults', {}),
            **self.connection.get('wallet', {}),
            **schemas[schema_name]['db'],
            **schemas[schema_name].get('apex', {}),
            **schemas[schema_name].get('export', {}),
        }
        self.connection['env']      = env_name
        self.connection['schema']   = schema_name
        self.connection['key']      = self.args.get('key') or ''
        self.connection['lang']     = self.connection.get('lang') or '.AL32UTF8'
        self.info.schema            = schema_name

        # if key is a file, retrieve content and use it as a key
        if self.connection['key'] != '' and os.path.exists(self.connection['key']):
            with open(self.connection['key'], 'rt', encoding = 'utf-8') as f:
                self.connection['key'] = f.read().strip()



    def create_connection(self, output_file = None):
        env_name        = self.info.env
        schema_name     = self.args.schema or self.args.user
        #
        util.assert_(env_name,      'MISSING ARGUMENT: ENV')
        util.assert_(schema_name,   'MISSING ARGUMENT: SCHEMA')
        #
        self.check_arguments()

        # prepare target folder
        file = self.replace_tags(output_file or self.connection_default)
        os.makedirs(os.path.dirname(file), exist_ok = True)

        # load current file
        connections = {}
        if os.path.exists(file):
            with open(file, 'rt', encoding = 'utf-8') as f:
                data = util.get_yaml(f, file)
                for env, arguments in data:
                    connections[env] = arguments

        # create config structure
        if not (env_name in connections):
            connections[env_name] = {}
        for group, items in self.args_map.items():
            if not (group in connections[env_name]):
                connections[env_name][group] = {}
            for name, input in items.items():
                if not (name in connections[env_name][group]):
                    connections[env_name][group][name] = self.args.get(input) or ''

                    # encrypt passwords and set correct flags
                    if name.endswith('!') and not (self.args.decrypt):
                        original    = name.rstrip('!')
                        value       = connections[env_name][group][original]
                        if value != '':
                            connections[env_name][group][original]  = util.encrypt(value, self.args.key)
                            connections[env_name][group][name]      = 'Y'

        # add schema into schemas
        if not (schema_name in connections[env_name]['schemas']):
            connections[env_name]['schemas'][schema_name] = {}
        for group, items in self.args_schema.items():
            if not (group in connections[env_name]['schemas'][schema_name]):
                connections[env_name]['schemas'][schema_name][group] = {}
            for name, input in items.items():
                if not (name in connections[env_name]['schemas'][schema_name][group]):
                    connections[env_name]['schemas'][schema_name][group][name] = self.args.get(input) or ''

                    # encrypt passwords and set correct flags
                    if name.endswith('!') and not (self.args.decrypt):
                        original    = name.rstrip('!')
                        value       = connections[env_name]['schemas'][schema_name][group][original]
                        if value != '':
                            connections[env_name]['schemas'][schema_name][group][original]  = util.encrypt(value, self.args.key)
                            connections[env_name]['schemas'][schema_name][group][name]      = 'Y'

        # remove wallet if not used
        if 'wallet' in connections[env_name]:
            if connections[env_name]['wallet']['wallet'] == '':
                connections[env_name].pop('wallet')

        # remove wallet if not used
        if 'apex' in connections[env_name]['schemas'][schema_name]:
            if connections[env_name]['schemas'][schema_name]['apex']['workspace'] == '':
                connections[env_name]['schemas'][schema_name].pop('apex')
        if 'apex' in connections[env_name]['schemas'][schema_name]:
            exp = connections[env_name]['schemas'][schema_name].get('export', {})
            if exp.get('prefix', '') == '' and exp.get('ignore', '') == '' and exp.get('subfolder', '') == '':
                connections[env_name]['schemas'][schema_name].pop('export')

        # mark default scheme
        if self.args.default:
            schema_type = 'schema_apex' if connections[env_name]['schemas'][schema_name].get('apex', {}) != {} else 'schema_db'
            connections[env_name]['defaults'][schema_type] = schema_name

        # show parameters
        print('\nCREATING {} CONNECTION:'.format(self.found_type.upper()))
        print('  - {}\n'.format(file))

        # store connection parameters in the yaml file
        util.write_file(file, payload = connections, yaml = True, fix = True)



    def import_connection(self):
        # find OPY pickle file
        pickle_file = self.args.opy
        if not os.path.exists(pickle_file) and os.path.splitext(pickle_file)[1] != '.conf':
            util.raise_error('MISSING OR INVALID OPY FILE')

        # check the file content
        args = {}
        try:
            with open(pickle_file, 'rb') as f:
                args = dict(pickle.load(f).items())
        except Exception:
            util.raise_error('INVALID OPY FILE',
                'expecting .conf file created by OPY tool')

        # import data as arguments
        for arg, value in args.items():
            arg = arg.replace('host',   'hostname')
            arg = arg.replace('target', 'repo')
            self.args[arg] = value

        # need to set the repo to have correct paths
        self.repo_root      = self.args['repo']
        self.info.env       = self.args['env']
        self.info.schema    = self.args['user']

        # create new file as user would actually pass these arguments
        self.create_connection()



    def db_connect(self, ping_sqlcl = False, silent = False):
        conn = wrapper.Oracle(
            tns         = dict(self.connection),
            config      = self.config,
            debug       = self.debug,
            ping_sqlcl  = ping_sqlcl,
            silent      = silent
        )
        self.object_prefix = (conn.tns.get('prefix') or '') + '%'
        return conn



    def get_application(self, app_id, schema = None):
        args = {
            'owner'     : schema or self.info.schema,
            'workspace' : '',
            'group_id'  : '',
            'app_id'    : app_id,
        }
        #
        if schema and schema != self.info.schema:
            self.conn.execute(query.apex_security_context, app_id = app_id)
        #
        for row in self.conn.fetch_assoc(query.apex_applications, **args):
            self.apex_apps[row.app_id] = row
        #
        if not (app_id in self.apex_apps):
            util.raise_error('APP {} NOT FOUND AT {}, {}'.format(app_id, schema or self.info.schema, self.info.env))



    def get_root(self, app_id, folders = ''):
        transl = {
            '{$APP_ID}'     : app_id,
            '{$APP_ALIAS}'  : self.apex_apps[app_id]['app_alias'],
            '{$APP_NAME}'   : self.apex_apps[app_id]['app_name'],
            '{$APP_GROUP}'  : self.apex_apps[app_id]['app_group'],
        }
        app_folder  = '/{}/'.format(util.replace(self.config.apex_path_app, transl))
        path        = self.target_path.replace(self.app_folder, app_folder) + folders
        #
        return path.replace('//', '/')



    def get_dependencies(self, prefix = ''):
        self.dependencies = {}
        for row in self.conn.fetch_assoc(query.object_dependencies, objects_prefix = prefix or self.object_prefix):
            obj_code = '{}.{}'.format(row.object_type, row.object_name)
            ref_code = '{}.{}'.format(row.referenced_type, row.referenced_name)
            #
            if not (obj_code in self.dependencies):
                self.dependencies[obj_code] = []
            if ref_code != 'None.None':
                self.dependencies[obj_code].append(ref_code)



    def get_object_type(self, file):
        file = file.replace(self.repo_root, '')

        # check type by checking all file extenstions
        folders = {}
        for object_type, info in self.config.object_types.items():
            folder, ext = info
            if '/' + folder in file:
                folders[ext] = object_type
        #
        for ext in sorted(folders.keys(), key = len, reverse = True):
            if ext in file:
                return folders[ext]
        return



    def get_object_name(self, file):
        return os.path.basename(file).split('.')[0].upper()



    def get_object(self, object_name, object_type = ''):
        objects = self.repo_objects.keys()
        for obj_code in objects:
            if (object_type == '' or obj_code.startswith(object_type + '.')) and obj_code.endswith('.' + object_name):
                return self.repo_objects[obj_code]
        return {}



    def get_objects(self):
        for file in util.get_files('{}{}**/*.sql'.format(self.repo_root, self.config.path_objects)):
            if util.extract(r'\.(\d+)\.sql$', file):
                continue
            #
            basename    = file.replace(self.repo_root, '')
            obj         = File(file, config = self.config)
            obj_code    = obj.get('object_code')
            #
            if obj_code and obj['object_type'] != '':
                self.repo_objects[obj_code] = obj
                self.repo_files[basename]   = self.repo_objects[obj_code]



    def sort_objects(self, todo = []):
        if todo != []:
            self.objects_todo = todo
        self.objects_processed  = []
        self.objects_path       = []
        #
        for obj_code in self.objects_todo:
            self.sort_objects__(obj_code)
        #
        return self.objects_processed



    def sort_objects__(self, obj_code, caller = '', level = 0):
        level = level + 1
        if caller != '':
            self.objects_path.append(caller)
        #
        for obj in self.dependencies.get(obj_code, []):
            if (obj in self.objects_path or obj in self.objects_processed or obj == caller):
                continue
            #
            self.sort_objects__(obj, caller = obj_code, level = level)
        #
        if not (obj_code in self.objects_processed):
            self.objects_processed.append(obj_code)



    def sort_files_by_deps(self, files):
        out_files = []

        # sort files by dependencies
        todo, indexes = [], []
        for file in files:
            # if file is on different path, get object from the original file
            short = file.replace(self.repo_root, '')
            if '/' in short and not (self.config.path_objects in short):
                short = self.config.path_objects + '/'.join(os.path.basename(short).split('.', maxsplit = 1))

            # get file object with some details/metadata
            obj = self.repo_files.get(short) or File(file, config = self.config)
            if obj['object_code'] in self.all_objects_sorted:
                index   = self.all_objects_sorted.index(obj['object_code'])
            else:
                index   = 1000000 + len(self.obj_not_found)
                self.obj_not_found.append(obj['object_code'])
            #
            todo.append(file)
            indexes.append(index)
        #
        for file in [x for _, x in sorted(zip(indexes, todo))]:
            if not (file in out_files):
                out_files.append(file)
        #
        return out_files



    def get_grants_made(self, object_names = [], schema = None):
        payload = []

        # get list of object names
        if object_names == [] and 'diffs' in self:
            for file in self.diffs:
                object_names.append(self.get_object_name(file))

        # grab the file with grants made
        self.patch_grants = self.repo_root + self.config.path_objects + self.config.patch_grants  # reset
        self.patch_grants = self.patch_grants.replace('#SCHEMA#', schema or self.info['schema'])
        self.patch_grants = self.patch_grants.replace('/.sql', schema or self.info['schema'])
        #
        if os.path.exists(self.patch_grants):
            with open(self.patch_grants, 'rt', encoding = 'utf-8') as f:
                file_content = f.readlines()
                for line in file_content:
                    if line.startswith('--'):
                        continue

                    # find match on object name
                    find_name = util.extract(r'\sON\s+(.*)\s+TO\s', line).upper()
                    #
                    for object_name in object_names:
                        if object_name == find_name:
                            payload.append(line.strip())
                            break
        #
        if payload != []:
            payload.append('')
        return payload



    def check_arguments(self):
        # check required arguments
        missing_args = {}
        for type, arguments in self.required_args.items():
            missing_args[type]  = []
            for arg in arguments:
                if not (arg in self.args) or self.args[arg] == None or self.args[arg] == '':
                    missing_args[type].append(arg)

        # create guidance for missing args
        self.found_type = None
        for type, arguments in missing_args.items():
            if len(arguments) == 0:
                self.found_type = type
                break
        #
        if not self.found_type:
            for type, arguments in missing_args.items():
                if type != self.found_type and len(arguments) > 0:
                    print('MISSING ARGUMENTS FOR {} CONNECTION:'.format(type.upper()))
                    for arg in arguments:
                        print('   - {}'.format(arg))
                    print()
            #
            util.raise_error('CAN\'T CONTINUE')



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

        # search for config file(s)
        for file in self.replace_tags(list(self.config_files)):  # copy
            if not ('{$' in file) and os.path.exists(file):
                self.apply_config(file)

        # allow schema overrides
        if self.info.get('schema'):
            for file in self.replace_tags(list(self.config_overrides)):  # copy
                if not ('{$' in file) and os.path.exists(file):
                    self.apply_config(file)



    def apply_config(self, file):
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
        if (not isinstance(payload, str) or payload == None):
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
        found_tags = list(dict.fromkeys(re.findall(r'\{\$[A-Z0-9_]+\}', payload)))
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
        #payload = payload.strip().rstrip('-').rstrip('_').strip()
        if '{$' in payload:
            if loops > 0:
                return self.replace_tags(payload, obj = obj, ignore_missing = ignore_missing, loops = loops - 1)
            if not ignore_missing:
                util.raise_error('LEFTOVER TAGS', payload)
        #
        return payload



    def show_versions(self):
        import oracledb

        # path check + get version
        results = {
            'Python'            : sys.version.split()[0],
            'Oracle DB module'  : oracledb.__version__,
            'SQLcl'             : '',
            'Java'              : '',
            'Instant Client'    : '',
        }

        # get instant client version
        file = os.getenv('ORACLE_HOME') + '/BASIC_README'
        if os.path.exists(file):
            with open(file, 'rt') as f:
                for line in f.readlines():
                    if 'Client Shared Library' in line:
                        results['Instant Client'] = line.split(' - ')[1].strip()

        # get versions for Java and SQLcl
        checks = {
            'Java'      : 'java --version',
            'SQLcl'     : 'sql -V',
        }
        for name, command in checks.items():
            results[name] = util.run_command(command, stop = False, silent = True).strip().replace(' Release', '')
            if 'is not recognized' in results[name]:
                results[name] = ''
                continue
            #
            if name == 'SQLcl':
                for line in results[name].splitlines():
                    if line.startswith('SQLcl:'):
                        results[name] = line.split()[1]
            elif ' ' in results[name]:
                results[name] = results[name].split()[1]

        # cleanup trailing zeroes
        for name, version in results.items():
            results[name] = util.replace(version, r'(\.0)+$', '')
        #
        util.print_header('VERSION:')
        util.print_args(results, length = 24)



    def check_utf_errors(self):
        util.print_header('FILES WITH UTF ISSUES:')
        #
        for file in util.get_files('{}**/*.sql'.format(self.repo_root)):
            try:
                with open (file, 'rt', encoding = 'utf-8') as f:
                    f.readlines()
            except:
                print('\n{}\n\n{}\n'.format('_' * 80, file.replace(self.repo_root, '')))

                # find wrong lines
                with io.open(file, encoding = 'utf-8', errors = 'replace') as f:
                    replaced = f.readlines()
                with io.open(file, encoding = 'utf-8', errors = 'ignore') as f:
                    ignored = f.readlines()
                #
                for i, line in enumerate(replaced):
                    if line != ignored[i]:
                        print('  {}) {}'.format(i, line.strip()))
        #
        print()
        util.quit()



    def create_message(self, title, message, blocks = [], mentions = {}, actions = []):
        payload = copy.deepcopy(messages.simple)

        # prepare title
        if title != '':
            payload['attachments'][0]['content']['body'].append({
                'type'      : 'TextBlock',
                'size'      : 'Large',
                'weight'    : 'Bolder',
                'text'      : title,
                'style'     : 'heading',
            })

        # prepare message
        if message != '':
            if not isinstance(message, dict):
                message = {
                    'type'  : 'TextBlock',
                    'text'  : message,
                }
            payload['attachments'][0]['content']['body'].append(message)
            message = message['text']

            # mark mentioned people
            for item in re.findall(r"(<at>[^/]+</at>)", message):
                mention     = copy.deepcopy(messages.mentions)
                user_mail   = item.replace('<at>', '').replace('</at>', '').strip()
                user_name   = mentions.get(user_mail) or self.config.mentions.get(user_mail) or ''
                #
                if '@' in user_name:            # allow multiple accounts
                    user_mail   = user_name
                    user_name   = mentions.get(user_mail) or self.config.mentions.get(user_mail) or ''
                #
                if len(user_name) > 0:
                    mention['text']              = item
                    mention['mentioned']['id']   = user_mail
                    mention['mentioned']['name'] = user_name
                    payload['attachments'][0]['content']['msteams']['entities'].append(mention)

        # add buttons
        if len(actions) > 0:
            for action_data in actions:
                for title, url in action_data.items():
                    action = copy.deepcopy(messages.action_link)
                    action['title'] = title
                    action['url']   = url
                    payload['attachments'][0]['content']['actions'].append(action)

        # add extra blocks
        for block in blocks:
            if block == '':
                block = {
                    'type'  : 'TextBlock',
                    'text'  : '&nbsp;',
                }
            payload['attachments'][0]['content']['body'].append(block)
        #
        return payload



    def build_header(self, text):
        return {
            'type'      : 'TextBlock',
            'size'      : 'Medium',
            'weight'    : 'Bolder',
            'text'      : text,
        }



    def build_mono(self, text):
        out = []
        for line in text.split('\n--\n--'):
            out.append({
                'type'      : 'TextBlock',
                'text'      : '-- ' + line.replace('\n\n', '\n&nbsp;\n').replace('\n', '\r\n'),
                'wrap'      : True,
                'fontType'  : 'Monospace',
                'sizing'    : 'Small',   # not working
            })
        return out



    def build_table(self, data, columns, widths, right_align = []):
        blocks  = []
        widths  = dict(zip(columns, widths))

        # create table header
        table_header = copy.deepcopy(messages.table_header)
        for col_name in columns:
            column = copy.deepcopy(messages.table_header_col)
            column['items'][0]['text'] = col_name.replace('_', ' ').upper()
            if col_name in right_align:
                column['items'][0]['horizontalAlignment'] = 'Right'
            column['width'] = widths[col_name]
            #
            table_header['items'][0]['columns'].append(column)
        #
        blocks.append(table_header)

        # create table body
        for row in data:
            table_row = copy.deepcopy(messages.table_row)
            for col_name in columns:
                column = copy.deepcopy(messages.table_row_col)
                column['items'][0]['text'] = row[col_name]
                if col_name in right_align:
                    column['items'][0]['horizontalAlignment'] = 'Right'
                column['width'] = widths[col_name]
                #
                table_row['columns'].append(column)
            #
            blocks.append(table_row)
        #
        return blocks



    def notify_team(self, title, message, blocks = [], mentions = {}, actions = []):
        payload = self.create_message(title, message, blocks = blocks, mentions = mentions, actions = actions)
        if not self.config.teams_webhoook:
            return
        #
        payload = json.dumps(payload, indent = None, separators = (',', ':'), ensure_ascii = True)
        result  = requests.post(self.config.teams_webhoook, data = payload, headers = {
            'Content-Type': 'application/json; charset=ascii',
        })
        #result = requests.post(self.config.teams_webhoook, json = payload)

        # debug result
        if result.text != '1' or self.debug:
            print()
            print('MESSAGE:',   payload)
            print('LENGTH:',    len(payload))
            print('CODE:',      result.status_code)
            print('RESPONSE:',  result.text)
            print()



if __name__ == '__main__':
    Config()

