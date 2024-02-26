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

        # connect to the database
        self.conn = self.db_connect(ping_sqlcl = False)

        # show objects overview
        print('RECOMPILING')
        #
        objects = {}
        args = {
            'object_name'   : self.args.name,
            'object_type'   : self.args.type,
        }
        data = self.conn.fetch_assoc(query.overview, **args)
        for row in data:
            objects[row.object_type] = [row.total, row.invalid or 0]
            if self.args.force:
                objects[row.object_type][1] = 0

        # get objects to recompile
        data_todo = self.conn.fetch_assoc(query.objects_to_recompile, force = 'Y' if self.args.force else '', **args)
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
                self.conn.execute(q)
            except Exception:
                pass
        #
        if not self.debug:
            print()
        print()

        # calculate difference
        data = self.conn.fetch_assoc(query.overview, **args)
        for row in data:
            if not self.args.force:
                objects[row.object_type][1] = objects[row.object_type][1] - (row.invalid or 0)
            if objects[row.object_type][1] == 0:
                objects[row.object_type][1] = ''
            objects[row.object_type].append(row.invalid or '')

        # show to user
        util.print_header('OBJECTS OVERVIEW:')
        util.print_table(data,
            columns     = self.conn.cols,
            right_align = ['total', 'fixed', 'invalid'],
        )

        # reconnect due to some unforseen recompilation issues
        self.conn.disconnect()
        self.conn = self.db_connect(ping_sqlcl = False, silent = True)

        # show invalid objects
        errors  = self.conn.fetch_assoc(query.objects_errors_summary, **args)
        data    = self.conn.fetch_assoc(query.objects_to_recompile, force = '', **args)
        if len(data) > 0:
            # enrich the original list with some numbers
            for i, row in enumerate(data):
                data[i]['errors'] = 0
                for row in errors:
                    if data[i]['object_name'] == row['object_name'] and data[i]['object_type'] == row['object_type']:
                        data[i] = {**data[i], **row}  # merge dictionaries
                        break
            #
            util.print_header('INVALID OBJECTS:')
            util.print_table(data)



if __name__ == "__main__":
    # parse arguments
    parser = argparse.ArgumentParser()

    # actions and flags
    parser.add_argument('-debug',       help = 'Turn on the debug/verbose mode',    default = False, nargs = '?', const = True)
    parser.add_argument('-key',         help = 'Key or key location to encypt passwords')
    parser.add_argument('-schema',      help = 'Schema/connection name')
    parser.add_argument('-env',         help = 'Target environment')

    # limit scope by object type and name (prefix)
    parser.add_argument('-type',        help = 'Object type')
    parser.add_argument('-name',        help = 'Object name/prefix')

    # compilation flags
    parser.add_argument('-force',       help = '', default = False, nargs = '?', type = bool, const = True)
    parser.add_argument('-level',       help = '',                  nargs = '?', type = int)
    parser.add_argument('-interpreted', help = '', default = False, nargs = '?', type = bool, const = True)
    parser.add_argument('-native',      help = '', default = False, nargs = '?', type = bool, const = True)
    parser.add_argument('-scope',       help = '',                  nargs = '*')
    parser.add_argument('-warnings',    help = '',                  nargs = '*')
    #
    Recompile(parser)

