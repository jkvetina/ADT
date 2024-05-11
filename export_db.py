# coding: utf-8
import sys, os, re, argparse, datetime
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
        if self.args.verbose and self.args.debug:
            util.print_header('NEW DEPENDENCIES:')
            for file, obj in self.repo_files.items():
                if obj.is_object and obj.object_type and not (obj.object_type in ('GRANT',)):
                    obj_code = obj['object_code']
                    if not (obj_code in self.dependencies):
                        print('  - {}'.format(obj_code))
            print()

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
        if self.args.verbose:
            util.print_header('EXPORTING OBJECTS:', '({})'.format(self.objects_total))
            print()
        else:
            print('EXPORTING OBJECTS')

        # minimize the clutter in exports
        self.conn.execute(query.setup_dbms_metadata)

        # export objects one by one
        progress_target = self.objects_total
        progress_done   = 0
        recent_type     = ''
        #
        for object_type in sorted(self.objects.keys()):
            for object_name in self.objects[object_type]:
                show_type   = object_type if object_type != recent_type else ''
                status      = ''
                #
                if self.args.verbose:
                    print('{:>20} | {:<48} {}'.format(show_type, object_name, status))
                else:
                    progress_done = util.print_progress(progress_done, progress_target)
                #
                recent_type = object_type

                # prepare object file
                repo_obj    = self.get_object(object_type, object_name)
                folder      = self.config.object_types[object_type][0]
                file_base   = object_name.lower() + self.config.object_types[object_type][1]
                new_file    = '{}{}{}/{}'.format(self.repo_root, self.config.path_objects, folder, file_base)
                object_file = repo_obj.get('file') or new_file

                # export object from database through DBMS_METADATA package
                payload = self.get_object_payload(object_type, object_name)

                # cleanup all objects
                if len(payload) > 0:
                    payload = re.sub('\t', '    ', payload.strip())  # replace tabs with 4 spaces
                    lines   = payload.splitlines()
                    #
                    if len(lines) > 0:
                        for (i, line) in enumerate(lines):
                            lines[i] = line.rstrip()    # remove trailing spaces

                            # remove package body from specification
                            if i > 0 and line.startswith('CREATE OR REPLACE') and 'PACKAGE BODY' in line and i > 0:
                                lines = '\n'.join(lines[0:i]).rstrip().splitlines()
                                break

                        # remove editions
                        lines[0] = lines[0].replace(' EDITIONABLE', '')
                        lines[0] = lines[0].replace(' NONEDITIONABLE', '')

                        # simplify object name
                        lines[0] = self.unquote_object_name(lines[0], remove_schema = self.conn.tns.schema)

                        # simplify end of objects
                        last_line = len(lines) - 1
                        if lines[last_line].upper().startswith('END ' + object_name.upper() + ';'):
                            lines[last_line] = lines[last_line][0:3] + ';'

                        # fix terminator
                        if lines[last_line][-1:] != ';':
                            lines[last_line] += ';'
                        if not (object_type in ['TABLE', 'INDEX']):
                            lines.append('/')

                    payload = '\n'.join(lines) + '\n\n'

                # save in file
                util.write_file(object_file, payload)

            # show extra line in between different object types
            if self.args.verbose:
                if len(self.objects[object_type]) > 0:
                    print('{:>20} |'.format(''))
        #
        if not self.args.verbose:
            util.print_progress_done()
        print()



    def get_object_payload(self, object_type, object_name):
        if object_type == 'MVIEW LOG':
            object_name = 'MLOG$_' + object_name
        #
        args = {
            'object_type'   : object_type,
            'object_name'   : object_name,
        }
        q = query.describe_object

        # adjust object name
        if object_type == 'JOB':
            q = query.describe_job
        elif object_type == 'MVIEW LOG':
            q = query.describe_mview_log

        # get object from database
        try:
            result = self.conn.fetch(q, **args)
            return result[0][0]
        except:
            util.raise_error('EXPORT_FAILED', object_type, object_name)
        #
        return ''



    def unquote_object_name(self, line, remove_schema = ''):
        if remove_schema:
            line = line.replace('"{}".'.format(remove_schema), '')
        #
        line = re.sub(r'"([A-Z0-9_$#]+)"', lambda x : x.group(1).lower(), line)
        #
        return line



if __name__ == "__main__":
    Export_DB()

