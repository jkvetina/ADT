# coding: utf-8
import sys, os, re, argparse
#
import config
from lib import util
from lib import queries_export_db as query
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
        group.add_argument('-recent',       help = 'Show objects changed in # days',        type = util.is_boolstr,     nargs = '?')

        # limit scope by object type and name (prefix)
        group = self.parser.add_argument_group('LIMIT SCOPE')
        group.add_argument('-type',         help = 'Object type (you can use LIKE syntax)',                             nargs = '?')
        group.add_argument('-name',         help = 'Object name/prefix (you can use LIKE syntax)',                      nargs = '?')

        # env details
        group = self.parser.add_argument_group('SPECIFY ENVIRONMENT DETAILS')
        group.add_argument('-schema',       help = '',                                                                  nargs = '?')
        group.add_argument('-env',          help = 'Source environment (for overrides)',                                nargs = '?')
        group.add_argument('-key',          help = 'Key or key location for passwords',                                 nargs = '?')

        super().__init__(self.parser, args)

        # setup env and paths
        self.target_root    = self.repo_root + self.config.path_objects
        self.objects        = {}
        self.objects_total  = 0
        self.overview       = {}
        #
        self.init_config()
        self.conn = self.db_connect(ping_sqlcl = False)

        # store object dependencies for several purposes
        self.get_dependencies(prefix = self.connection.get('prefix', ''))
        self.all_objects_sorted = self.sort_objects(self.dependencies.keys())
        payload = {
            'dependencies'  : self.dependencies,
            'sorted'        : self.all_objects_sorted,
        }
        util.write_file(self.dependencies_file, payload = payload, yaml = True, fix = False)

        # detect deleted objects
        if self.args.verbose:
            util.print_header('NEW DEPENDENCIES:')
            for file, obj in self.repo_files.items():
                if obj.is_object and obj.object_type and not (obj.object_type in ('GRANT',)):
                    obj_code = obj['object_code']
                    if not (obj_code in self.dependencies):
                        print('  - {}'.format(obj_code))

        self.show_overview()
        self.export()



    def show_overview(self):
        args = {
            'object_name'   : self.args.name    or self.connection.get('prefix', '') + '%',
            'object_type'   : self.args.type    or '',
            'recent'        : self.args.recent  or '',
        }
        util.print_header('OBJECTS OVERVIEW:', '{} {} [{}]'.format(args['object_type'], args['object_name'], args['recent']).replace(' % ', ' ').replace(' []', ''))

        # get objects to recompile
        for row in self.conn.fetch_assoc(query.matching_objects, **args):
            if not (row.object_type in self.objects):
                self.objects[row.object_type] = []
                self.overview[row.object_type] = 0
            self.objects[row.object_type].append(row.object_name)
            self.overview[row.object_type] += 1
        #
        objects_overview = []
        for object_type in sorted(self.objects.keys()):
            objects_overview.append({'object_type' : object_type, 'count' : self.overview[object_type]})
            self.objects_total += self.overview[object_type]
        objects_overview.append({'object_type' : '', 'count' : self.objects_total})  # add total
        util.print_table(objects_overview)
        print()



    def export(self):
        print('EXPORTING')
        progress_target = self.objects_total
        progress_done   = 0
        #
        for object_type in sorted(self.objects.keys()):
            for object_name in self.objects[object_type]:
                #
                #
                #
                progress_done = util.print_progress(progress_done, progress_target)
        #
        util.print_progress_done()
        print()



if __name__ == "__main__":
    Export_DB()

