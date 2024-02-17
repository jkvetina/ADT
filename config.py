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
            print('ARGS:')
            print('-----')
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

        #
        # load parameters from config file
        #

        # setup Git repo
        self.repo       = Repo(self.repo_path)
        self.repo_url   = self.repo.remotes[0].url
        # prepare date formats
        self.today              = datetime.datetime.today().strftime('%Y-%m-%d')            # YYYY-MM-DD
        self.today_full         = datetime.datetime.today().strftime('%Y-%m-%d %H:%M')      # YYYY-MM-DD HH24:MI
        self.today_full_raw     = datetime.datetime.today().strftime('%Y%m%d%H%M') + '00'






    def __del__(self):
        print('\nTIME: {}s\n'.format(round(timeit.default_timer() - self.start_timer, 2)))






    def replace_tags(self, payload, obj = None):
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
            # replace all tags "{$_____}" with values from passed object
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
                    print('      {} {} {}'.format(sub_key, '.' * (24 - 3 - len(sub_key)), sub_value or ''))
            #
            elif isinstance(value, list):
                print('   {} {} {}'.format(key, '.' * (24 - len(key)), ' | '.join(value)))
            #
            else:
                print('   {} {} {}'.format(key, '.' * (24 - len(key)), value or ''))
        print()



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

