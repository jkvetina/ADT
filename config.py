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

    def __init__(self, parser):
        self.start_timer = timeit.default_timer()

        # parse arguments from command line
        self.args = vars(parser.parse_args())
        if not ('decrypt' in self.args):
            self.args['decrypt'] = False

        # merge with environment variables
        os_args = ['REPO', 'CLIENT', 'PROJECT', 'ENV', 'BRANCH', 'KEY']
        for arg in os_args:
            if not (arg.lower() in self.args) or self.args[arg.lower()] == None:
                self.args[arg.lower()] = os.getenv('ADT_' + arg.upper())
        if self.args['env'] == None:
            self.args['env'] = 'DEV'
        #
        self.args   = util.Attributed(self.args)     # dict with attributes
        self.debug  = self.args.debug
        #
        if self.debug:
            util.header('ARGS:')
            util.debug_table(self.args)

        # set project info from arguments
        self.info_client    = self.args.client
        self.info_project   = self.args.project
        self.info_env       = self.args.env
        self.info_repo      = util.fix_path(self.args.repo or os.path.abspath(os.path.curdir))
        self.info_branch    = self.args.branch
        #
        self.root           = util.fix_path(os.path.dirname(os.path.realpath(__file__)))
        self.db             = None

        # repo attributes
        self.repo           = None      # set through init_repo()
        self.repo_url       = ''        # set through init_repo()
        self.repo_commits   = 200       # depth for the commit history

        # if we are using ADT repo for connection file, we have to know these too
        if self.info_repo == self.root:
            util.assert_(self.args.client   is not None, 'MISSING CLIENT ARGUMENT')
            util.assert_(self.args.project  is not None, 'MISSING PROJECT ARGUMENT')
            util.assert_(self.args.env      is not None, 'MISSING ENV ARGUMENT')

        # list connection files, where to search for DB connections
        self.connection_files = [
            '{$ROOT}config/{$INFO_CLIENT}/connections.yaml',
            '{$ROOT}config/{$INFO_CLIENT}/connections_{$INFO_PROJECT}.yaml',
            '{$INFO_REPO}config/connections.yaml',                                      # repo
        ]

        # default location for new connections
        self.connection_default = '{$INFO_REPO}config/connections.yaml'
        self.connections        = {}    # all connections
        self.connection         = {}    # active connection

        # search for config files in current folder
        self.config_files = [
            '{$ROOT}config/default_config.yaml',
            '{$ROOT}config/{$INFO_CLIENT}/config.yaml',
            '{$ROOT}config/{$INFO_CLIENT}/config_{$INFO_PROJECT}.yaml',
            '{$ROOT}config/{$INFO_CLIENT}/config_{$INFO_PROJECT}_{$INFO_ENV}.yaml',
            '{$INFO_REPO}config/config.yaml',                                           # repo
            '{$INFO_REPO}config/config_{$INFO_ENV}.yaml',                               # repo
        ]

        # when schema is set, run init_config again to allow wchema overrides
        self.config_overrides = [
            '{$ROOT}config/{$INFO_CLIENT}/config_{$INFO_PROJECT}_{$INFO_SCHEMA}.yaml',
            '{$ROOT}config/{$INFO_CLIENT}/config_{$INFO_PROJECT}_{$INFO_SCHEMA}_{$INFO_ENV}.yaml',
            '{$INFO_REPO}config/config_{$INFO_SCHEMA}.yaml',
            '{$INFO_REPO}config/config_{$INFO_SCHEMA}_{$INFO_ENV}.yaml',
        ]

        # prepare date formats
        self.today              = datetime.datetime.today().strftime('%Y-%m-%d')            # YYYY-MM-DD
        self.today_full         = datetime.datetime.today().strftime('%Y-%m-%d %H:%M')      # YYYY-MM-DD HH24:MI
        self.today_full_raw     = datetime.datetime.today().strftime('%Y%m%d%H%M') + '00'

        # connect to repo, we need valid repo for everything
        self.init_repo()

        # different flow for config call
        if __name__ == "__main__":
            # import OPY connection file, basically adjust input arguments and then create a connection
            if 'opy' in self.args and self.args.opy:
                self.import_connection()

            # create or update connection file
            elif self.args.create:
                self.create_connection()

            # check connection file and test connectivity
            self.init_connections()
            self.db_connect(ping_sqlcl = True)

            # check config file, rerun this when specific schema is processed to load schema overrides
            self.init_config()

            # create or update config file
            pass

        else:
            # check connection file and test connectivity
            self.init_connections()

            # check config file, rerun this when specific schema is processed to load schema overrides
            self.init_config()



    def __del__(self):
        print('\nTIME: {}s\n'.format(round(timeit.default_timer() - self.start_timer, 2)))



    def init_connections(self):
        # search for connection file
        for file in self.replace_tags(list(self.connection_files)):  # copy, dont change original
            if not ('{$' in file) and os.path.exists(file):
                with open(file, 'rt', encoding = 'utf-8') as f:
                    data = util.get_yaml(f, file)
                    for env_name, arguments in data:
                        # create description
                        desc = '{}, {}'.format(arguments['user'], env_name)
                        #
                        self.connections[env_name]          = arguments
                        self.connections[env_name]['file']  = file
                        self.connections[env_name]['desc']  = desc
                        self.connections[env_name]['plain'] = self.args.decrypt

        # decrypt passwords
        if self.args.decrypt:
            for arg in ['pwd', 'wallet_pwd']:
                if arg in self.connections[self.info_env]:
                    self.connections[self.info_env][arg] = util.decrypt(self.connections[self.info_env][arg], self.args.key)

        # check connection
        if not (self.info_env in self.connections):
            util.raise_error('UNKNOWN CONNECTION FOR {}'.format(self.info_env))
        #
        self.connection         = self.connections[self.info_env]
        self.connection['key']  = self.args.key
        #
        if self.debug:
            util.header('CONNECTION:')
            util.debug_table(self.connection)

        # check presence, at least one file is required
        if len(self.connections) == 0:
            util.header('CONNECTION FILE REQUIRED:')
            for file in self.connection_files:
                print('   {}'.format(file))
            print()
            util.quit()

        # check connection for current env
        if not (self.info_env in self.connections):
            util.raise_error('MISSING CONNECTION FOR {}'.format(self.info_env))

        # if key is a file, retrieve content and use it as a key
        if 'key' in self.connection and self.connection['key'] != None:
            if os.path.exists(self.connection['key']):
                with open(self.connection['key'], 'rt', encoding = 'utf-8') as f:
                    self.connection['key'] = f.read().strip()



    def create_connection(self, output_file = None):
        # check required arguments
        required_args = {
            'normal'    : ['env', 'user', 'pwd', 'hostname', 'port', 'service'],
            'legacy'    : ['env', 'user', 'pwd', 'hostname', 'port', 'sid'],
            'cloud'     : ['env', 'user', 'pwd',                     'service', 'wallet', 'wallet_pwd'],
        }
        #
        passed_args     = {}
        missing_args    = {}
        #
        for type, arguments in required_args.items():
            passed_args[type]   = {}
            missing_args[type]  = []
            #
            for arg in arguments:
                if not (arg in self.args) or self.args[arg] == None or self.args[arg] == '':
                    missing_args[type].append(arg)
                else:
                    passed_args[type][arg] = self.args[arg]

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

        # append some stuff
        passed_args[found_type]['lang'] = '.AL32UTF8'   # default language

        # encrypt passwords
        for arg in ['pwd', 'wallet_pwd']:
            if arg in passed_args[found_type] and not (self.args.decrypt):
                if not ('key' in self.args) or self.args.key == None:
                    util.raise_error('NEED KEY TO ENCRYPT PASSWORDS!')
                original = passed_args[found_type][arg]
                passed_args[found_type][arg] = util.encrypt(original, self.args.key)
                if original != util.decrypt(passed_args[found_type][arg], self.args.key):
                    util.raise_error('ENCRYPTION FAILED!')
                original = ''

        # request thick mode, pass instant client path
        if self.args.thick:
            passed_args[found_type]['thick'] = self.args.thick

        # show parameters
        util.header('CREATING {} CONNECTION:'.format(found_type.upper()))
        util.debug_table(passed_args[found_type], mask_keys = [] if self.args.decrypt else ['pwd', 'wallet_pwd'])

        # prepare target folder
        file    = self.replace_tags(output_file or self.connection_default)
        dir     = os.path.dirname(file)
        #
        if not os.path.exists(dir):
            os.makedirs(dir)
        #
        connections = {}
        connections[self.info_env] = passed_args[found_type]

        # merge with current file on env level
        if os.path.exists(file):
            with open(file, 'rt', encoding = 'utf-8') as f:
                data = util.get_yaml(f, file)
                for env_name, arguments in data:
                    if not (env_name in connections):
                        connections[env_name] = arguments

        # store connection parameters in the yaml file
        with open(file, 'wt', encoding = 'utf-8') as f:
            # convert dict to yaml string
            payload = yaml.dump(connections, allow_unicode = True, default_flow_style = False, indent = 4) + '\n'
            payload = util.fix_yaml(payload)
            f.write(payload)
            util.header('FILE CREATED:', ', '.join(sorted(connections.keys())))
            print('   {}\n'.format(file))



    def import_connection(self):
        # find OPY pickle file
        pickle_file = self.args.opy
        if not os.path.exists(pickle_file) and os.path.splitext(pickle_file)[1] != '.conf':
            util.raise_error('MISSING OR INVALID OPY FILE!')

        # check the file content
        args = {}
        try:
            with open(pickle_file, 'rb') as f:
                args = pickle.load(f).items()
        except Exception:
            util.raise_error('INVALID OPY FILE!',
                '   - expecting .conf file created by OPY tool\n'
            )

        # import data as arguments
        for arg, value in args.items():
            arg = arg.replace('host',   'hostname')
            arg = arg.replace('target', 'repo')
            #
            self.args[arg] = value

        # need to set the repo to have correct paths
        self.info_repo = self.args['repo']

        # create new file as user would actually pass these arguments
        self.create_connection()



    def db_connect(self, ping_sqlcl = False):
        # check connectivity
        self.db = wrapper.Oracle(self.connection, debug = self.debug, ping_sqlcl = ping_sqlcl)



    def init_config(self):
        self.track_config = {}

        # search for config file(s)
        for file in self.replace_tags(list(self.config_files)):           # copy
            if not ('{$' in file) and os.path.exists(file):
                self.apply_config(file)

        # allow schmea overrides
        if self.info_schema:
            for file in self.replace_tags(list(self.config_overrides)):   # copy
                if not ('{$' in file) and os.path.exists(file):
                    self.apply_config(file)

        # show source of the parameters
        if self.debug:
            for file in self.config_files:
                if file in self.track_config:
                    util.header('CONFIG:', file)
                    util.debug_dots(self.track_config[file], 24)

        # reconnect to repo, it could change the location
        self.init_repo()



    def init_repo(self):
        util.assert_(self.info_repo is not None, 'MISSING REPO ARGUMENT')

        # setup and connect to the repo
        self.info_repo  = self.replace_tags(self.info_repo)
        prev_repo       = self.info_repo
        #
        if (self.info_repo != prev_repo or self.repo == None):
            try:
                self.repo       = git.Repo(self.info_repo)
                self.repo_url   = self.repo.remotes[0].url
            except Exception:
                util.raise_error('INVALID GIT REPO!',
                    '   - change current folder to the repo you would like to use.\n' +
                    '   - or specify repo in args or system arguments\n'
                )



    def apply_config(self, file):
        with open(file, 'rt', encoding = 'utf-8') as f:
            self.track_config[file] = {}
            data = util.get_yaml(f, file)
            for key, value in data:
                setattr(self, key, value)
                self.track_config[file][key] = value






    def replace_tags(self, payload, obj = None):
        if obj == None:
            obj = self

        # if payload is a list, process all items individually
        if isinstance(payload, list):
            for i, item in enumerate(payload):
                payload[i] = self.replace_tags(item, obj)
            return payload

        # check passed argument types
        is_object   = str(type(obj)).startswith("<class '__main__.")
        is_dict     = isinstance(obj, dict)

        # extract keys from payload
        passed_keys = []
        if is_dict:
            passed_keys = obj.keys()
        elif is_object:
            passed_keys = obj.__dict__.keys()  # get object attributes
        #
        if len(passed_keys) > 0:
            # replace all tags "{$_____}" with passed object attribute values
            for tag in re.findall('\{\$[A-Z0-9_]+\}', payload):
                if tag in payload:
                    attribute   = tag.lower().replace('{$', '').replace('}', '')
                    value       = tag
                    #
                    if is_object and attribute in passed_keys:
                        value = str(getattr(obj, attribute))
                    elif is_dict and attribute in passed_keys:
                        value = obj[attribute]
                    #
                    payload = payload.replace(tag, value)

            # if there are tags left, try to fill them from the config
            if '{$' in payload:
                for tag in re.findall('\{\$[A-Z0-9_]+\}', payload):
                    if tag in payload:
                        attribute = tag.lower().replace('{$', '').replace('}', '')
                        try:
                            value = str(getattr(self, attribute))
                        except Exception:
                            value = tag
                        #
                        payload = payload.replace(tag, value)
        #
        return payload



    def replace_dict(self, payload, translation):
        regex = re.compile('|'.join(map(re.escape, translation)))
        return regex.sub(lambda match: translation[match.group(0)], payload)



if __name__ == "__main__":
    # parse arguments
    parser = argparse.ArgumentParser()

    # actions and flags
    parser.add_argument(        '-create',      '--create',         help = 'Create or update connection',       default = False, nargs = '?', const = True)
    parser.add_argument('-d',   '-debug',       '--debug',          help = 'Turn on the debug/verbose mode',    default = False, nargs = '?', const = True)
    parser.add_argument(        '-opy',         '--opy',            help = 'To import connection details from OPY file')
    parser.add_argument(        '-decrypt',     '--decrypt',        help = 'Show passwords decypted',           default = False, nargs = '?', const = True, type = bool)

    # to specify environment
    parser.add_argument('-c',   '-client',      '--client',         help = 'Client name')
    parser.add_argument('-p',   '-project',     '--project',        help = 'Project name')
    parser.add_argument('-e',   '-env',         '--env',            help = 'Environment name, like DEV, UAT, LAB1...')
    parser.add_argument('-r',   '-repo',        '--repo',           help = 'Path to your project repo')
    parser.add_argument('-b',   '-branch',      '--branch',         help = 'Repo branch')

    # key or key location to encrypt passwords
    parser.add_argument('-k',   '-key',         '--key',            help = 'Key or key location to encypt passwords')

    # for database connections
    parser.add_argument('-u',   '-user',        '--user',           help = 'User name')
    parser.add_argument(        '-pwd',         '--pwd',            help = 'User password')
    parser.add_argument('-m',   '-hostname',    '--hostname',       help = 'Hostname')
    parser.add_argument('-o',   '-port',        '--port',           help = 'Port',                        type = int, default = 1521)
    parser.add_argument('-s',   '-service',     '--service',        help = 'Service name')
    parser.add_argument(        '-sid',         '--sid',            help = 'SID')
    parser.add_argument('-w',   '-wallet',      '--wallet',         help = 'Wallet file')
    parser.add_argument('-wp',  '-wallet_pwd',  '--wallet_pwd',     help = 'Wallet password')
    parser.add_argument(        '-thick',       '--thick',          help = 'Thick client path, \'Y\' for auto resolve')
    #
    Config(parser)

