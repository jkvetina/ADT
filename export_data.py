# coding: utf-8
import sys, os, re, argparse, datetime, csv
#
import config
from lib import util
from lib import queries as query
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

class Export_Data(config.Config):

    def __init__(self, args = None):
        self.parser = argparse.ArgumentParser(add_help = False)

        # actions and flags
        group = self.parser.add_argument_group('MAIN ACTIONS')
        group.add_argument('-name',         help = 'Object name/prefix (you can use LIKE syntax)',                      nargs = '?')

        # env details
        group = self.parser.add_argument_group('SPECIFY ENVIRONMENT DETAILS')
        group.add_argument('-schema',       help = '',                                                                  nargs = '?')
        group.add_argument('-env',          help = 'Source environment (for overrides)',                                nargs = '?')
        group.add_argument('-key',          help = 'Key or key location for passwords',                                 nargs = '?')

        super().__init__(self.parser, args)

        # setup env and paths
        self.init_config()
        self.conn           = self.db_connect(ping_sqlcl = False)
        self.target_root    = self.repo_root + self.get_path(self.config.path_objects)
        #
        self.objects_prefix = self.connection.get('prefix') or ''
        self.objects_ignore = self.connection.get('ignore') or ''

        # get objects
        folder, file_ext    = self.config.object_types['DATA']
        self.tables_dir     = self.target_root + folder
        self.tables_curr    = []
        self.tables_desc    = {}
        self.tables_cols    = {}

        # find existing table names
        for file in util.get_files(self.tables_dir + '*' + file_ext):
            table_name = os.path.basename(file).split('.')[0].upper()
            self.tables_curr.append(table_name)

        # find requested table(s)
        self.get_requested_tables()

        # show exporting objects
        util.print_header('EXPORT TABLE DATA:', '({})'.format(len(self.tables_curr)))
        for table_name in self.tables_curr:
            file = self.get_object_file(object_type = 'DATA', object_name = table_name)
            self.export_table(table_name, file)
        print()



    def get_requested_tables(self):
        args = {
            'object_name'       : self.args.name        or '',
            'object_type'       : 'TABLE',
            'recent'            : None,
            'objects_prefix'    : self.objects_prefix   or '',
            'objects_ignore'    : self.objects_ignore   or '',
        }
        #
        for row in self.conn.fetch_assoc(query.matching_objects, **args):
            if not (row.object_name in self.tables_curr):
                self.tables_curr.append(row.object_name)

        # get table columns and data types
        for table_name in self.tables_curr:
            self.tables_desc[table_name] = {}
            self.tables_cols[table_name] = []
            #
            for row in self.conn.fetch_assoc(query.csv_columns, table_name = table_name):
                self.tables_desc[table_name][row.column_name] = row
                self.tables_cols[table_name].append(row.column_name)



    def export_table(self, table_name, file):
        if not os.path.exists(os.path.dirname(file)):
            os.makedirs(os.path.dirname(file))
        #
        csv_file    = open(file, 'wt', encoding = 'utf-8', newline = '\n')
        writer      = csv.writer(csv_file, delimiter = ';', lineterminator = '\n', quoting = csv.QUOTE_NONNUMERIC)
        #
        columns         = self.tables_cols[table_name]
        where_filter    = ''
        order_by        = ''

        # fetch data from table
        try:
            query   = 'SELECT {}\nFROM {}{}\nORDER BY {}'.format(', '.join(columns), table_name, where_filter, order_by or 'ROWID')
            data    = self.conn.fetch_assoc(query)
        except Exception:
            util.raise_error()

        # save as CSV
        writer.writerow(columns)    # headers
        for row in data:
            row_append = []
            for col in columns:
                row_append.append(row[col.lower()])
            writer.writerow(row_append)
        csv_file.close()



if __name__ == "__main__":
    Export_Data()

