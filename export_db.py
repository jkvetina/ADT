# coding: utf-8
import sys, os, re, argparse
#
import config
from lib import util
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

class Export_DB(config.Config):

    def __init__(self, args = None):
        self.parser = argparse.ArgumentParser(add_help = False)

        # actions and flags
        group = self.parser.add_argument_group('MAIN ACTIONS')
        group.add_argument('-recent',       help = 'Show objects changed in # days',        type = util.is_boolstr, nargs = '?')

        # env details
        group = self.parser.add_argument_group('SPECIFY ENVIRONMENT DETAILS')
        group.add_argument('-schema',       help = '',                                                              nargs = '?')
        group.add_argument('-env',          help = 'Source environment (for overrides)',                            nargs = '?')
        group.add_argument('-key',          help = 'Key or key location for passwords',                             nargs = '?')

        super().__init__(self.parser, args)

        # setup env and paths
        self.target_root    = self.repo_root + self.config.path_objects
        #
        self.init_config()
        self.conn = self.db_connect(ping_sqlcl = False)

        # store object dependencies for several purposes
        self.get_dependencies()
        self.all_objects_sorted = self.sort_objects(self.dependencies.keys())
        payload = {
            'dependencies'  : self.dependencies,
            'sorted'        : self.all_objects_sorted,
        }
        #
        with open(self.dependencies_file, 'wt', encoding = 'utf-8', newline = '\n') as w:
            util.store_yaml(w, payload = payload)

        # detect deleted objects
        for file, obj in self.repo_files.items():
            if obj.is_object and obj.object_type and not (obj.object_type in ('GRANT',)):
                obj_code = obj['object_code']
                if not (obj_code in self.dependencies):
                    print(obj_code)



if __name__ == "__main__":
    Export_DB()

