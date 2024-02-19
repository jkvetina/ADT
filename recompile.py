# coding: utf-8
import sys, argparse
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

        # show objects overview
        print('RECOMPILING')
        #
        objects = {}
        data = self.db.fetch_assoc(query.overview, object_name = self.args.name)
        for row in data:
            objects[row.object_type] = [row.object_count, row.invalid or 0]
            if self.args.force:
                objects[row.object_type][1] = 0

        # get objects to recompile
        data_todo = self.db.fetch_assoc(query.objects_to_recompile, object_type = self.args.type, object_name = self.args.name, force = 'Y' if self.args.force else '')
        #
        progress_target = len(data_todo)
        progress_done   = 0
        #
        for row in data_todo:
            type_body   = ' BODY' if 'BODY' in row.object_type else ''
            type_family = row.object_type.replace(' BODY', '')
            extras      = ''

            # extra stuff for code objects
            if row.object_type in ('PACKAGE', 'PACKAGE BODY', 'PROCEDURE', 'FUNCTION', 'TRIGGER',):
                extras += ' PLSQL_CODE_TYPE = ' + ('NATIVE' if self.args.native else 'INTERPRETED')

                # setup optimize level
                if 'level' in self.args:
                    if self.args.level != None and self.args.level >= 1 and self.args.level <= 3:
                        extras += ' PLSQL_OPTIMIZE_LEVEL = ' + str(self.args.level)

                # setup scope
                if 'scope' in self.args and isinstance(self.args['scope'], list):
                    scope = ''
                    scope += 'IDENTIFIERS:ALL,'  if ('IDENTIFIERS' in self.args.scope or 'ALL' in self.args.scope) else ''
                    scope += 'STATEMENTS:ALL,'   if ('STATEMENTS'  in self.args.scope or 'ALL' in self.args.scope) else ''
                    #
                    extras += ' PLSCOPE_SETTINGS = \'' + scope.rstrip(',') + '\''

                # setup warnings
                if 'warnings' in self.args and isinstance(self.args['warnings'], list):
                    warnings = ''
                    warnings += 'ENABLE:SEVERE,'        if ('SEVERE'  in self.args.warnings) else ''
                    warnings += 'ENABLE:PERFORMANCE,'   if ('PERF'    in self.args.warnings or 'PERFORMANE'     in self.args.warnings) else ''
                    warnings += 'ENABLE:INFORMATIONAL,' if ('INFO'    in self.args.warnings or 'INFORMATIONAL'  in self.args.warnings) else ''
                    #
                    extras += ' PLSQL_WARNINGS = \'' + warnings.strip(',').replace(',', '\',\'') + '\''
                #
                extras += ' REUSE SETTINGS'

            # build query
            q = 'ALTER {} {} COMPILE{} {}'.format(type_family, row.object_name, type_body, extras)
            if self.args.force:
                objects[row.object_type][1] += 1

            # show progress
            if self.debug:
                print('  - {}'.format(row.object_name))
            else:
                progress_done += 1
                perc = progress_done / progress_target
                dots = int(70 * perc)
                sys.stdout.write('\r' + ('.' * dots) + ' ' + str(int(perc * 100)) + '%')
                sys.stdout.flush()

            # recompile object
            try:
                self.db.execute(q)
            except Exception:
                pass
        #
        if not self.debug:
            print()
        print()
        util.header('DATABASE OBJECTS:')

        # calculate difference
        data = self.db.fetch_assoc(query.overview, object_name = self.args.name)
        for row in data:
            if not self.args.force:
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
    parser.add_argument('-force',           '--force',          help = '', default = False, nargs = '?', type = bool, const = True)
    parser.add_argument('-level',           '--level',          help = '',                  nargs = '?', type = int)
    parser.add_argument('-interpreted',     '--interpreted',    help = '', default = False, nargs = '?', type = bool, const = True)
    parser.add_argument('-native',          '--native',         help = '', default = False, nargs = '?', type = bool, const = True)
    parser.add_argument('-scope',           '--scope',          help = '',                  nargs = '*')
    parser.add_argument('-warnings',        '--warnings',       help = '',                  nargs = '*')

    # key or key location to encrypt passwords
    parser.add_argument('-k',   '-key',         '--key',        help = 'Key or key location to encypt passwords')
    #
    Recompile(parser)

