# coding: utf-8
import collections
from lib import config
from git import Repo

class App:

    def __init__(self, parser):
        # arguments from command line
        self.args = vars(parser.parse_args())
        self.args = collections.namedtuple('ARG', self.args.keys())(*self.args.values())  # convert to named tuple

        #print('ARGS:')
        #print('-----')
        #for key, value in sorted(zip(args._fields, args)):
        #    print('{:>10} = {}'.format(key, value))
        #print()

        # config files
        self.config = config.Config()

        # Git repo
        self.repo       = Repo(self.config.repo_path)
        self.repo_url   = self.repo.remotes[0].url

