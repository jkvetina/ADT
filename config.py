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
        # load parameters from config file
        #
        self.repo_path          = ''
        self.branch             = ''
        self.schema             = ''
        self.apex_schema        = ''
        self.apex_workspace     = ''
        self.path_objects       = ''
        self.path_apex          = ''
        self.git_depth          = 500

        # setup Git repo
        self.repo       = Repo(self.repo_path)
        self.repo_url   = self.repo.remotes[0].url
        # prepare date formats
        self.today              = datetime.datetime.today().strftime('%Y-%m-%d')        # YYYY-MM-DD
        self.today_full         = datetime.datetime.today().strftime('%Y-%m-%d %H:%M')  # YYYY-MM-DD HH24:MI
        self.today_full_raw     = datetime.datetime.today().strftime('%Y%m%d%H%M') + '00'






    def __del__(self):
        print('TIME: {}s\n'.format(round(timeit.default_timer() - self.start_timer, 2)))



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



if __name__ == "__main__":
    # parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-c',   '--client',       help = 'Client name')
    parser.add_argument('-p',   '--project',      help = 'Project name')
    parser.add_argument('-e',   '--env',          help = 'Environment name',            nargs = '*')  # ?
    parser.add_argument('-r',   '--repo',         help = 'Path to your project repo')
    parser.add_argument('-u',   '--user',         help = 'User name')
    parser.add_argument(        '--pwd',          help = 'User password')
    parser.add_argument('-h',   '--host',         help = 'Host')
    parser.add_argument('-o',   '--port',         help = 'Port',                        type = int, default = 1521)
    parser.add_argument('-s',   '--service',      help = 'Service name')
    parser.add_argument(        '--sid',          help = 'SID')
    parser.add_argument('-w',   '--wallet',       help = 'Wallet file')
    parser.add_argument('-wp',  '--wallet_pwd',   help = 'Wallet password')

    # create object
    start_timer = timeit.default_timer()
    #
    config = Config(parser)
    #
    config.create_config()
    #
    print('TIME: {}\n'.format(round(timeit.default_timer() - start_timer, 2)))

