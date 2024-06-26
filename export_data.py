# coding: utf-8
import sys, os, re, argparse, csv
#
import config
from lib import util
from lib import queries as query

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
        group.add_argument('-name',         help = 'Object name/prefix (you can use LIKE syntax)',                      nargs = '*')

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
        if not self.args.name:
            # if name is not provided, export existing tables
            self.args.name = []
            for file in util.get_files(self.tables_dir + '*' + file_ext):
                table_name = os.path.basename(file).split('.')[0].upper()
                self.tables_curr.append(table_name)
                self.args.name.append(table_name)

        # find requested table(s)
        self.get_requested_tables()

        # show exporting objects
        util.print_header('EXPORT TABLE DATA:', '({})'.format(len(self.tables_curr)))
        for table_name in sorted(self.tables_curr):
            print('  - {}'.format(table_name))
            file = self.get_object_file(object_type = 'DATA', object_name = table_name).replace('.sql', '.csv')
            self.export_table(table_name, file)
        print()



    def get_requested_tables(self):
        args = {
            'object_name'       : ','.join(self.args.name or ['%']).upper(),
            'object_type'       : 'TABLE',
            'recent'            : None,
            'objects_prefix'    : self.objects_prefix   or '%',
            'objects_ignore'    : self.objects_ignore   or '',
        }
        #
        for row in self.conn.fetch_assoc(query.matching_objects, **args):
            if not (row.object_name in self.tables_curr) and row.object_type == 'TABLE':
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
        writer      = csv.writer(csv_file, delimiter = self.config.csv_delimiter or ';', lineterminator = '\n', quoting = csv.QUOTE_NONNUMERIC)
        #
        columns         = self.tables_cols[table_name]
        where_filter    = ''
        order_by        = []

        # remove ignored columns
        for column_name in self.config.ignored_columns:
            if column_name in columns:
                columns.remove(column_name)

        # filter table rows if requested
        where_filter = self.get_where_filter(table_name, columns)

        # order data by primary key or first unique key
        order_by = self.get_primary_columns(table_name, columns)
        order_by = ', '.join(order_by) or 'ROWID'

        # fetch data from table
        try:
            stmt    = 'SELECT {}\nFROM {}{}\nORDER BY {}'.format(', '.join(columns), table_name, where_filter, order_by)
            data    = self.conn.fetch_assoc(stmt)
        except Exception:
            util.raise_error('EXPORT_FAILED')

        # save as CSV
        writer.writerow(columns)    # attach headers
        for row in data:
            row_append = []
            for col in columns:
                row_append.append(row[col.lower()])

                # adjust data types
                #if isinstance(col, float):
                #    row[idx] = str(col).replace('.', ',')

            writer.writerow(row_append)
        csv_file.close()

        # create also the .sql file
        self.get_merge_from_csv(file, where_filter)



    def get_where_filter(self, table_name, columns):
        where_filter = ''
        where_cols = {
            **self.config.tables_global.get('where', {}),
            **self.config.tables.get(table_name.upper(), {}).get('where', {})
        }
        for column_name in list(where_cols.keys()):
            if not (column_name.upper() in columns) and column_name in where_cols:
                where_cols.pop(column_name)
        #
        if len(where_cols) > 0:
            where_filter = '\nWHERE 1 = 1'
            for column_name, value in where_cols.items():
                where_filter += '\n    AND {} {}'.format(column_name, value)
        #
        return where_filter



    def get_primary_columns(self, table_name, columns):
        pk, uq, out = {}, {}, []
        #
        for column_name, row in self.tables_desc[table_name.upper()].items():
            if column_name in columns:
                if row['pk']: pk[row['pk']] = column_name
                if row['uq']: uq[row['uq']] = column_name
        #
        if len(out) == 0:
            for idx in sorted(pk.keys()):
                out.append(pk[idx])
        #
        if len(out) == 0:
            for idx in sorted(uq.keys()):
                out.append(uq[idx])
        #
        return out



    def get_merge_from_csv(self, file, where_filter):
        table_name      = os.path.basename(file).split('.')[0].lower()
        columns         = []
        csv_rows        = 0
        csv_select      = {}
        update_cols     = []
        batch_size      = 10000     # split large files into several statements
        batch_id        = 0

        # flags to disable parts of the query
        skip_insert     = ''
        skip_update     = ''
        skip_delete     = ''

        # parse CSV file and create WITH table
        with open(file, mode = 'rt', encoding = 'utf-8') as csv_file:
            csv_reader = csv.DictReader(csv_file, delimiter = self.config.csv_delimiter or ';', lineterminator = '\n', quoting = csv.QUOTE_NONNUMERIC)
            for idx, row in enumerate(csv_reader):
                batch_id = idx // batch_size
                csv_rows += 1
                cols = []
                for col_name, col_value in row.items():
                    if not isinstance(col_value, (int, float)):
                        col_value = '\'{}\''.format(col_value.replace('\'', '\'\''))
                    cols.append('{} AS {}'.format(col_value, col_name))
                #
                if not(batch_id in csv_select):
                    csv_select[batch_id] = []
                csv_select[batch_id].append('SELECT {} FROM DUAL'.format(', '.join(cols)))
                #
                if not len(columns):
                    columns = list(row.keys())

        # ignore empty files
        if csv_rows == 0:
            return

        # get primary key cols for merge
        primary_cols = self.get_primary_columns(table_name, columns)
        if len(primary_cols) == 0:
            return

        # lowercase column names
        primary_cols    = ','.join(primary_cols).lower().split(',')
        columns         = ','.join(columns).lower().split(',')

        # construct primary key joiner
        primary_cols_set = []
        for col in primary_cols:
            primary_cols_set.append('t.{} = s.{}'.format(col, col))
        primary_cols_set = '\n    ' + '\n    AND '.join(primary_cols_set) + '\n'

        # get other columns
        for col in columns:
            if not (col in primary_cols):
                update_cols.append('t.{} = s.{}'.format(col, col))
        update_cols = ',\n{}        '.format(skip_update).join(update_cols)
        #
        all_cols    = 't.' + ',\n        t.'.join(columns)
        all_values  = 's.' + ',\n        s.'.join(columns)

        # proceeed in batches
        payload = ''
        for batch_id, data in csv_select.items():
            stmt = query.template_csv_merge.lstrip().format (
                table_name              = table_name,
                primary_cols_set        = primary_cols_set,
                csv_content_query       = ' UNION ALL\n    '.join(data),
                non_primary_cols_set    = update_cols,
                all_cols                = all_cols,
                all_values              = all_values,
                skip_insert             = skip_insert,
                skip_update             = skip_update,
                skip_delete             = skip_delete if (batch_id == 0) else False,
                where_filter            = where_filter
            )

            # some fixes
            stmt = stmt.replace('\'\' AS ', 'NULL AS ')
            stmt = stmt.replace('.0 AS ', ' AS ')
            stmt = stmt.replace('\n    )\n;\n', '\n    );\n')
            #
            payload += stmt + '--\nCOMMIT;\n'
        #
        util.write_file(file.replace('.csv', '.sql'), payload)



if __name__ == "__main__":
    Export_Data()

