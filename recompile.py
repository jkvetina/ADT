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
        self.args.target = self.args.target or self.args.env
        util.assert_(self.args.target, 'MISSING ARGUMENT: TARGET ENV')
        #
        self.init_connection(env_name = self.args.target)
        #
        self.conn = self.db_connect(ping_sqlcl = False)

        # show objects overview
        if self.args.verbose:
            util.print_header('RECOMPILING:')
        else:
            print('\nRECOMPILING')
        #
        objects = {}
        args = {
            'object_name'   : self.args.name or self.connection.get('prefix', '') + '%',
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
        troublemakers   = []
        #
        try:
            for row in data_todo:
                q = self.build_query(row)
                if self.args.force:
                    objects[row.object_type][1] += 1

                # show progress
                if self.args.verbose:
                    print('  - {}'.format(row.object_name))
                else:
                    progress_done = util.print_progress(progress_done, progress_target)

                # recompile object
                try:
                    self.conn.execute(q)
                except Exception:
                    troublemakers.append(row)
                #
        except KeyboardInterrupt:
            print('\n')
            return
        util.print_progress_done()

        # if there are some leftovers, try to recompile them
        if len(troublemakers) > 0:
            # reconnect due to some unforseen recompilation issues
            self.conn = self.db_connect(ping_sqlcl = False, silent = True)

            # go backwards
            for row in reversed(troublemakers):
                q = self.build_query(row)
                try:
                    self.conn.execute(q)
                except Exception:
                    pass

        # reconnect due to some unforseen recompilation issues
        self.conn = self.db_connect(ping_sqlcl = False, silent = True)

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

            # create message for team
            title       = '{} - {} invalid object{}'.format(self.args.target, len(data), 's' if len(data) > 1 else '')
            message     = ''
            blocks      = []
            #
            blocks.extend(self.build_table(
                data        = data,
                columns     = ['object_type', 'object_name', 'errors'],
                widths      = [2, 5, 1],  # as a ratio in between columns
                right_align = ['errors']
            ))
            #
            self.notify_team(title, message, blocks = blocks)



    def build_query(self, row):
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
        return 'ALTER {} {} COMPILE{} {}'.format(type_family, row.object_name, type_body, extras)



if __name__ == "__main__":
    # parse arguments
    parser = argparse.ArgumentParser(add_help = False)
    #
    group = parser.add_argument_group('SPECIFY ENVIRONMENT DETAILS')
    group.add_argument('-target',       help = 'Target environment',                                                nargs = '?')
    group.add_argument('-schema',       help = 'Schema/connection name',                                            nargs = '?')
    group.add_argument('-key',          help = 'Key or key location for passwords',                                 nargs = '?')

    # limit scope by object type and name (prefix)
    group = parser.add_argument_group('LIMIT SCOPE')
    group.add_argument('-type',         help = 'Object type (you can use LIKE syntax)',                             nargs = '?')
    group.add_argument('-name',         help = 'Object name/prefix (you can use LIKE syntax)',                      nargs = '?')

    # compilation flags
    group = parser.add_argument_group('COMPILATION FLAGS')
    group.add_argument('-force',        help = 'Recompile even valid objects',              type = util.is_boolean, nargs = '?', const = True,  default = False)
    group.add_argument('-level',        help = 'Level of PL/SQL optimization',                                      nargs = '?', type = int)
    group.add_argument('-interpreted',  help = 'Interpreted or native compilation',         type = util.is_boolean, nargs = '?', const = True,  default = False)
    group.add_argument('-native',       help = 'Interpreted or native compilation',         type = util.is_boolean, nargs = '?', const = True,  default = False)
    group.add_argument('-scope',        help = 'Gather identifiers',                                                nargs = '*',                default = None)
    group.add_argument('-warnings',     help = 'Allow PL/SQL warnings',                                             nargs = '*',                default = None)
    #
    Recompile(parser)

