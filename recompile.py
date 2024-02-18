# coding: utf-8
import sys, os, re, shutil, argparse
#
import config
from lib import util
from lib import queries_recompile as query

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

class Recompile(config.Config):

    def __init__(self, parser):
        super().__init__(parser)

        # parse arguments from command line
        self.args = vars(parser.parse_args())
        self.args = util.Attributed(self.args)     # dict with attributes

        # connect to the database
        self.db_connect()

        #
        #
        #
        #self.db.execute('SELECT * FROM DUAL')
        #
        util.header('DATABASE OBJECTS:')
        #
        objects = {}
        data = self.db.fetch_assoc(query.overview, object_name = self.args.name)
        for row in data:
            objects[row.object_type] = [row.object_count, row.invalid or 0]

        # get objects to recompile
        data_todo = self.db.fetch_assoc(query.objects_to_recompile, object_type = self.args.type, object_name = self.args.name, force = self.args.force)
        for row in data_todo:
            obj_type    = row.object_type.split(' ')
            type_body   = ' BODY' if len(obj_type) > 1 and obj_type[1] == 'BODY' else ''
            type_family = obj_type[0]
            #
            try:
                q = 'ALTER {} {} COMPILE{} '.format(type_family, row.object_name, type_body)
            except Exception:
                pass
            #
            self.db.execute(q)

        # calculate difference
        data = self.db.fetch_assoc(query.overview, object_name = self.args.name)
        for row in data:
            objects[row.object_type][1] = objects[row.object_type][1] - (row.invalid or 0)
            if objects[row.object_type][1] == 0:
                objects[row.object_type][1] = ''
            objects[row.object_type].append(row.invalid or '')

        # show to user
        pattern = ' {:<21} | {:>7} | {:>7} | {:>7}'
        print(pattern.format('OBJECT TYPE', 'TOTAL', 'FIXED', 'INVALID'))
        for object_type, data in objects.items():
            print(pattern.format(object_type, *data))
        print()



if __name__ == "__main__":
    # parse arguments
    parser = argparse.ArgumentParser()

    # actions and flags
    parser.add_argument('-d',   '-debug',       '--debug',      help = 'Turn on the debug/verbose mode',                                default = False, nargs = '?', const = True)

    # limit scope by object type and name (prefix)
    parser.add_argument('-t',   '-type',        '--type',       help = 'Object type')
    parser.add_argument('-n',   '-name',        '--name',       help = 'Object name/prefix')

    # compilation flags
    parser.add_argument('-force',           '--force',          help = '', default = '', nargs = '?', const = True)
    parser.add_argument('-level',           '--level',          help = '', default = '', nargs = '?', const = True)
    parser.add_argument('-interpreted',     '--interpreted',    help = '', default = '', nargs = '?', const = True)
    parser.add_argument('-identifiers',     '--identifiers',    help = '', default = '', nargs = '?', const = True)
    parser.add_argument('-statements',      '--statements',     help = '', default = '', nargs = '?', const = True)
    parser.add_argument('-severe',          '--severe',         help = '', default = '', nargs = '?', const = True)
    parser.add_argument('-performance',     '--performance',    help = '', default = '', nargs = '?', const = True)
    parser.add_argument('-informational',   '--informational',  help = '', default = '', nargs = '?', const = True)

    # key or key location to encrypt passwords
    parser.add_argument('-k',   '-key',         '--key',        help = 'Key or key location to encypt passwords')
    #
    Recompile(parser)

