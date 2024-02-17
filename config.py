# coding: utf-8
import sys, os, re, argparse, datetime, timeit, yaml, git
from lib import oracle_wrapper

class Attributed(dict):

    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__



class Config(Attributed):

    def __init__(self, parser):
        self.start_timer = timeit.default_timer()

        # arguments from command line
        self.args = vars(parser.parse_args())
        self.args = Attributed(self.args)
        #
        if self.args.debug:
            self.header('ARGS:')
            self.debug_dots(self.args, 24)

        # set project info from arguments
        self.info_client    = self.args.client
        self.info_project   = self.args.project
        self.info_env       = self.args.env
        self.info_repo      = self.fix_path(self.args.repo or os.path.abspath(os.path.curdir))
        self.info_branch    = self.args.branch

        # get the platform
        self.platform       = 'unix' if os.path.pathsep == ':' else 'win'
        self.root           = self.fix_path(os.path.dirname(os.path.realpath(__file__)))

        # if we are using ADT repo for connection file, we have to know these too
        if self.info_repo == self.root:
            assert self.args.client is not None
            assert self.args.project is not None
            assert self.args.env is not None

        # list connection files, where to search for DB connections
        self.connection_files = [
            '{$ROOT}config/{$INFO_CLIENT}/connections.yaml',
            '{$ROOT}config/{$INFO_CLIENT}/connections_{$INFO_PROJECT}.yaml',
            '{$INFO_REPO}config/connections.yaml',                                      # repo
        ]

        # default location for new connections
        self.connection_default = '{$INFO_REPO}config/connections.yaml'

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

        # create connection file
        if self.args.create:
            self.create_connection() and self.quit()

        # check connection file
        self.init_connections()

        # check config file, rerun this when specific schema is processed to load schema overrides
        self.init_config()




    def __del__(self):
        print('\nTIME: {}s\n'.format(round(timeit.default_timer() - self.start_timer, 2)))



    def init_connections(self):
        self.track_connections = {}

        # search for connection file
        for file in self.replace_tags(list(self.connection_files)):  # copy, dont change original
            if not ('{$' in file) and os.path.exists(file):
                with open(file, 'rt', encoding = 'utf-8') as f:
                    self.track_connections[file] = {}
                    content = list(yaml.load_all(f, Loader = yaml.loader.SafeLoader))
                    if len(content) > 0:
                        for key, value in content[0].items():
                            setattr(self, key, value)
                            self.track_connections[file][key] = value
        #
        if self.args.debug:
            for file in self.config_files:
                if file in self.track_connections:
                    self.header('CONNECTION:', file)
                    self.debug_dots(self.track_connections[file], 24)

        # check presence, at least one file is required
        if len(self.track_connections) == 0:
            self.header('CONNECTION FILE REQUIRED:')
            for file in self.connection_files:
                print('   {}'.format(file))
            print()



    def create_connection(self):
        self.init_repo()

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
            self.raise_error('CAN\'T CONTINUE')

        self.header('CREATING {} CONNECTION:'.format(found_type.upper()))
        self.debug_dots(passed_args[found_type], 24)
        print('')

        # prepare target folder
        file    = self.replace_tags(self.connection_default)
        dir     = os.path.dirname(file)
        #
        if not os.path.exists(dir):
            os.makedirs(dir)
        #
        payload = {}
        payload[self.info_env] = passed_args[found_type]

        # store connection parameters in the yaml file
        with open(file, 'wt', encoding = 'utf-8') as f:
            yaml.dump(payload, f, allow_unicode = True, default_flow_style = False)
            self.header('FILE CREATED:')
            print('   {}\n'.format(file))



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
        if self.args.debug:
            for file in self.config_files:
                if file in self.track_config:
                    self.header('CONFIG:', file)
                    self.debug_dots(self.track_config[file], 24)
                    print()

        # connect to repo
        self.init_repo()



    def init_repo(self):
        self.assert_(self.info_repo is not None, 'MISSING REPO ARGUMENT')

        # setup and connect to the repo
        self.info_repo = self.replace_tags(self.info_repo)
        prev_repo = self.info_repo
        #
        if self.info_repo != prev_repo:
            self.repo           = git.Repo(self.info_repo)
            self.repo_url       = self.repo.remotes[0].url
            self.repo_commits   = 200



    def apply_config(self, file):
        with open(file, 'rt', encoding = 'utf-8') as f:
            self.track_config[file] = {}
            for key, value in list(yaml.load_all(f, Loader = yaml.loader.SafeLoader))[0].items():
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



    def fix_path(self, dir):
        return os.path.normpath(dir).replace('\\', '/').rstrip('/') + '/'



    def debug_dots(self, payload, length):
        for key, value in payload.items():
            if isinstance(value, dict):
                print('   {}:'.format(key))
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, list):
                        sub_value = ' | '.join(sub_value)
                    print('      {} {} {}'.format(sub_key, '.' * (length - 3 - len(sub_key)), sub_value or ''))
            #
            elif isinstance(value, list):
                print('   {} {} {}'.format(key, '.' * (length - len(key)), ' | '.join(value)))
            #
            else:
                print('   {} {} {}'.format(key, '.' * (length - len(key)), value or ''))
        print()



    def header(self, message, append = ''):
        print('\n{}\n{}'.format(message, '-' * len(message)), append)



    def quit(self, message = ''):
        if len(message) > 0:
            print(message)
        sys.exit()



    def raise_error(self, message = ''):
        message = 'ERROR: {}'.format(message)
        self.quit('\n{}\n{}'.format(message, '-' * len(message)))



    def assert_(self, condition, message = ''):
        if not condition:
            message = 'ERROR: {}'.format(message)
            self.quit('\n{}\n{}'.format(message, '-' * len(message)))



if __name__ == "__main__":
    # parse arguments
    parser = argparse.ArgumentParser()

    # actions and flags
    parser.add_argument(        '-create',      '--create',         help = 'Create new connection',             default = False, nargs = '?', const = True)
    parser.add_argument(        '-update',      '--update',         help = 'Update existing connection',        default = False, nargs = '?', const = True)
    parser.add_argument('-d',   '-debug',       '--debug',          help = 'Turn on the debug/verbose mode',    default = False, nargs = '?', const = True)

    # to specify environment
    parser.add_argument('-c',   '-client',      '--client',         help = 'Client name')
    parser.add_argument('-p',   '-project',     '--project',        help = 'Project name')
    parser.add_argument('-e',   '-env',         '--env',            help = 'Environment name, like DEV, UAT, LAB1...', default = 'DEV')
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
    #
    config = Config(parser)

