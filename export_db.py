# coding: utf-8
import sys, os, re, argparse, datetime
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
        self.comments       = {}
        self.comments_col   = {}
        #
        self.init_config()
        self.conn           = self.db_connect(ping_sqlcl = False)
        self.remove_schema  = self.conn.tns.schema
        #
        self.objects_prefix = self.connection.get('prefix',     '')
        self.objects_ignore = self.connection.get('ignore',     '')
        self.objects_folder = self.connection.get('subfolder',  '')

        # store object dependencies for several purposes
        self.get_dependencies(prefix = self.objects_prefix, ignore = self.objects_ignore)
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
            'object_name'       : self.args.name        or '%',
            'object_type'       : self.args.type        or '%',
            'recent'            : self.args.recent      or '',
            'objects_prefix'    : self.objects_prefix   or '',
            'objects_ignore'    : self.objects_ignore   or '',
        }
        #
        show_recent     = str(datetime.datetime.today() - datetime.timedelta(days = int(self.args.recent) - 1))[0:10] if self.args.recent else ''
        show_header     = 'CHANGED SINCE ' + show_recent if show_recent else 'OVERVIEW'
        show_filter     = (' ' + args['object_name'] + ' ').replace(' % ', ' ').strip()
        #
        util.print_header('OBJECTS {}: {}'.format(show_header, show_filter).rstrip())

        # get objects to recompile
        for row in self.conn.fetch_assoc(query.matching_objects, **args):
            if not (row.object_type in self.objects):
                self.objects[row.object_type] = {}
                self.overview[row.object_type] = 0
            self.objects[row.object_type][row.object_name] = row
            self.overview[row.object_type] += 1
        #
        objects_overview = []
        for object_type in sorted(self.objects.keys()):
            objects_overview.append({'object_type' : object_type, 'count' : self.overview[object_type]})
            self.objects_total += self.overview[object_type]
        #objects_overview.append({'object_type' : '', 'count' : self.objects_total})  # add total
        util.print_table(objects_overview)

        # get comments
        for row in self.conn.fetch_assoc(query.pull_comments, **args):
            if not (row.table_name in self.comments):
                self.comments[row.table_name]       = {}
                self.comments_col[row.table_name]   = []
            if row.column_name != None:
                self.comments_col[row.table_name].append(row.column_name)
            self.comments[row.table_name][row.column_name or ''] = row



    def export(self):
        if self.args.verbose:
            util.print_header('EXPORTING OBJECTS:', '({})'.format(self.objects_total))
            print()
        else:
            print('\nEXPORTING OBJECTS', '({})'.format(self.objects_total))

        # minimize the clutter in exports
        self.conn.execute(query.setup_dbms_metadata)

        # export objects one by one
        progress_target = self.objects_total
        progress_done   = 0
        recent_type     = ''
        #
        for object_type in sorted(self.objects.keys()):
            for object_name in sorted(self.objects[object_type].keys()):
                if self.args.verbose:
                    show_type   = object_type if object_type != recent_type else ''
                    recent_type = object_type
                    print('{:>20} | {:<54}'.format(show_type, util.get_string(object_name, 54)))
                else:
                    progress_done = util.print_progress(progress_done, progress_target)

                # export object from database and save in file
                payload     = self.export_object(object_type, object_name)
                object_file = self.get_object_file(object_type, object_name)
                util.write_file(object_file, payload)

            # show extra line in between different object types
            if self.args.verbose:
                if len(self.objects[object_type].keys()) > 0:
                    print('{:>20} |'.format(''))
        #
        if not self.args.verbose:
            util.print_progress_done()
        else:
            util.beep(sound = 1)
        #
        print()



    def export_object(self, object_type, object_name, object_file = ''):
        # export object from database through DBMS_METADATA package
        payload     = self.get_object_payload(object_type, object_name)
        lines       = []

        # cleanup all objects
        if len(payload) > 0:
            payload = re.sub('\t', '    ', payload.strip())  # replace tabs with 4 spaces
            lines   = payload.splitlines()
            #
            if len(lines) > 0:
                lines = self.cleanup_general(lines, object_name, object_type)

            # call specialized function to cleanup the rest
            cleanup_fn = 'clean_' + object_type.replace(' ', '_').lower()
            if hasattr(self.__class__, cleanup_fn) and callable(getattr(self, cleanup_fn)):
                lines = getattr(self, cleanup_fn)(lines = lines, object_name = object_name, config = self.config)
        #
        payload = util.replace('\n'.join(lines), r';\n;', ';') + '\n\n'
        return payload



    def cleanup_general(self, lines, object_name, object_type):
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
        lines[0] = self.unquote_object_name(lines[0], remove_schema = self.remove_schema)

        # simplify end of objects
        last_line = len(lines) - 1
        if lines[last_line].upper().startswith('END ' + object_name.upper() + ';'):
            lines[last_line] = lines[last_line][0:3] + ';'

        # if object ends with comment, push ";" to the next line
        if '--' in lines[last_line] and last_line > 0:
            lines.append(';')
            last_line += 1

        # fix terminator
        if not lines[last_line].rstrip().endswith(';'):
            lines[last_line] += ';'
        if not (object_type in ['TABLE', 'INDEX']):
            lines.append('/')
        #
        return lines



    def clean_table(self, lines, object_name = '', config = {}):
        # fix first bracket
        lines[0] += ' ('
        lines[1] = lines[1].lstrip().lstrip('(').lstrip()

        # extract columns
        columns         = []
        column_types    = {}
        column_extras   = {}
        #
        for (i, line) in enumerate(lines):
            if i > 0:
                line = line.replace(' (', '(')
                line = line.replace(' CHAR)', '|CHAR)').replace(' BYTE)', '|BYTE)')
                #
                column_name, data_type, extras = (line.strip().strip(',').strip() + '  ').split(' ', 2)
                #
                if column_name.startswith('"'):
                    column_name = self.cleanup_names(column_name)
                    data_type   = data_type.replace('|', ' ')                   # recover space
                    data_type   = data_type.replace('NUMBER(*,0)', 'INTEGER')   # simplify
                    extras      = ' ' + extras.replace(' ENABLE', '')           # remove obvious things

                    # remove sequences clutter
                    extras      = extras.replace(' MINVALUE 1', '')
                    extras      = extras.replace(' MAXVALUE 9999999999999999999999999999', '')
                    extras      = extras.replace(' INCREMENT BY 1', '')
                    extras      = extras.replace(' START WITH 1', '')
                    extras      = extras.replace(' NOORDER', '')
                    extras      = extras.replace(' NOCYCLE', '')
                    extras      = extras.replace(' NOKEEP',  '')
                    extras      = extras.replace(' NOSCALE', '')
                    extras      = extras.replace(' CACHE 20', '')
                    extras      = util.replace(extras, r'([\s]{2,})', ' ')
                    #
                    columns.append(column_name)
                    column_types[column_name]   = data_type
                    column_extras[column_name]  = extras
                    #
                    line = '    {:<30}  {:<20} {}'.format(column_name, data_type, extras).rstrip() + ','
                    lines[i] = line
                    continue

                # fix constraints
                if line.lstrip().startswith('CONSTRAINT'):
                    line = self.unquote_object_name(line)
                    line = line.replace('     CONSTRAINT', '    CONSTRAINT')
                    line = line.replace(' CHECK(',          '\n        CHECK (\n            ')
                    line = line.replace(' PRIMARY KEY(',    '\n        PRIMARY KEY (')
                    line = line.replace(' FOREIGN KEY(',    '\n        FOREIGN KEY (')
                    line = line.replace(' UNIQUE(',         '\n        UNIQUE (')

                    # fix checks
                    if not (' CHECK (' in line):
                        line = self.split_columns(line)
                    else:
                        line = line.replace(') ENABLE',     '\n        )')
                        line = line.replace(') DISABLE',    '\n        ) DISABLE')
                    line = '    --\n    ' + line.strip()
                #

                    # just align check start, we dont want to touch the content
                    if line.lstrip().startswith('CHECK'):
                        line = line.replace(') ENABLE',     '\n    )')
                        line = line.replace(') DISABLE',    '\n    ) DISABLE')
                        #
                        line = line.replace(' CHECK(', '--\n    CHECK (\n        ')

                # finish up the foreign keys
                if line.lstrip().startswith('REFERENCES'):
                    line = line.strip().replace(' ENABLE', '').replace('"("', '" ("')
                    line = '        ' + self.unquote_object_name(line, remove_schema = self.remove_schema)
                    line = self.split_columns(line)
                #
                line = line.replace(' DEFERRABLE', '\n        DEFERRABLE')

                # fix different indexes
                if 'USING INDEX' in line:
                    line = line.strip().replace('USING INDEX  ENABLE', '')
                    if 'USING INDEX' in line:
                        line = '        ' + line

                # fix temp tables
                if line.startswith(') ON COMMIT'):
                    line = line.replace(') ON COMMIT', ')\nON COMMIT')

                # partition/index related
                line = line.replace('USING INDEX  ', '')

                lines[i] = line.rstrip()

        # remove partitions from table
        for (i, line) in enumerate(lines):
            line = line.strip()
            if line.startswith('PARTITION BY '):    # keep
                lines[i] = line
                continue
            #
            if (line.startswith('PARTITION') or line.startswith('(PARTITION')):
                lines[i] = ''

        # cleanup round
        for (i, line) in enumerate(lines):
            line = line.strip()

            # move standalone commas to previous line
            if line == ',':
                lines[i - 1] += ','
                lines[i] = ''

            # fix multiple statements
            if i > 0 and line.split(' ', 1)[0] in ('CREATE', 'ALTER'):
                lines[i] = '--\n' + line    # strip start
                if not lines[i - 1].rstrip().endswith(';'):
                    lines[i - 1] += ';'

                # reuse dedicated index cleanup
                if ('CREATE INDEX' in line or 'CREATE UNIQUE INDEX' in line):
                    index_name      = self.unquote_object_name(util.extract(r'INDEX\s+([^\s]+)', line), remove_schema = self.remove_schema)
                    index_payload   = [lines[i].replace('"("', '" ("')]
                    index_payload   = self.cleanup_general(index_payload, index_name, 'INDEX')
                    index_payload   = self.clean_index(index_payload, object_name = index_name, config = config)
                    #
                    lines[i] = '\n'.join(index_payload)

        # consolidate lines
        lines = self.rebuild_lines(lines)

        # cleanup round
        for (i, line) in enumerate(lines):
            line = line.strip()

            # remove trailing commas
            if line.startswith(')') and lines[i - 1].endswith(','):
                lines[i - 1] = lines[i - 1].rstrip(',')

            # fix end of the table definition
            if line == ');':
                lines[i] = line         # strip start

        # reformat alter statements
        lines = '\n'.join(lines)
        for i in range(1, 10):
            alter = util.extract(r'\n(ALTER TABLE ["][^;]+)[;]', lines, flags = re.M)
            if not alter:
                break
            #
            formatted = alter
            formatted = formatted.replace('("', ' ("')
            formatted = formatted.replace(' ENABLE', '')
            formatted = self.unquote_object_name(formatted, remove_schema = self.remove_schema)
            formatted = util.replace(formatted, r'\s+', ' ').strip()
            #
            formatted = formatted.replace(' ADD',       '\n    ADD')  # for create script this is enough
            formatted = formatted.replace(' PRIMARY',   '\n        PRIMARY')
            formatted = formatted.replace(' FOREIGN',   '\n        FOREIGN')
            formatted = formatted.replace(' UNIQUE',    '\n        UNIQUE')
            formatted = formatted.replace(' CHECK',     '\n        CHECK')
            formatted = formatted.replace(' USING',     '\n        USING')
            #
            lines = lines.replace(alter, formatted)
        lines = lines.splitlines()

        # add comments
        lines = self.get_object_comments(lines, object_name)


        #
        return lines



    def clean_index(self, lines, object_name = '', config = {}):
        lines[0] = self.split_columns(lines[0].replace(' ON ', '\n    ON '))

        # remove partitions from index
        for (i, line) in enumerate(lines):
            line = line.strip()
            if (line.startswith('PARTITION') or line.startswith('(PARTITION')):
                lines[i] = ''
        #
        lines = self.rebuild_lines(lines)

        # extract table name
        table_name  = util.extract(r' ON ([^\s]+)', lines[1]).upper()
        table_tblsp = (self.objects.get('TABLE', {}).get(table_name, {}).get('tablespace_name') or '').replace('"', '').lower()

        # partitioning
        last_line = len(lines) - 1
        if 'LOCAL' in lines[last_line]:
            lines[last_line] = '    LOCAL'

        # add tablespace
        index_tblsp = (self.objects.get('INDEX', {}).get(object_name, {}).get('tablespace_name') or '').replace('"', '').lower()
        if index_tblsp and index_tblsp != table_tblsp:
            lines[last_line] = '{}\n    TABLESPACE {}'.format(lines[last_line].rstrip(';'), index_tblsp)
        #
        if not (lines[last_line].endswith(';')):
            lines[last_line] += ';'
        #
        return lines



    def clean_view(self, lines, object_name = '', config = {}):
        # remove column from view definition
        # you should have correct names in the query
        lines[0] = util.replace(lines[0], r'\s*\([^)]+\)\s*AS', ' AS')                 # remove columns
        lines[0] = util.replace(lines[0], r'\s*\([^)]+\)\s*BEQUEATH', ' BEQUEATH')     # remove columns
        lines[0] = lines[0].replace(' ()  AS', ' AS')
        lines[0] = lines[0].replace('  ', ' ')

        # fix wrong indentation on first line
        lines[1] = lines[1].lstrip()

        # fix one liners, split by FROM to two lines, convert columns to lower if possible
        if len(lines) == 3 and ' FROM ' in lines[1].upper():
            lines[1] = self.cleanup_names(lines[1])
            #
            split_from = util.extract(r'(\s+FROM\s+)', lines[1], flags = re.I)
            split_line = lines[1].split(split_from)
            lines[1] = '{}\n{} {}'.format(split_line[0].rstrip(), split_from.strip(), split_line[1])
            lines = self.rebuild_lines(lines)

        # fix column names
        for (i, line) in enumerate(lines):
            indent      = util.extract(r'^(\s*)', line) or '    '
            start       = util.extract(r'^([^"]+)', line).strip()
            expanded    = []

            # fix SELECT * FROM ..., expand column names
            if util.extract(r'"([A-Z0-9_$#]+)",.*"', line):         # with table alias
                for col in re.findall(r'([^\.,"]\.)"([A-Z0-9_$#]+)"', line):
                    expanded.append('{}{}{}'.format(indent, col[0], self.cleanup_names(col[1])))
                    start = start.replace(col[0], '')
            #
            if util.extract(r'"([A-Z0-9_$#]+)","', line):           # no alias
                for col in re.findall(r'"([A-Z0-9_$#]+)"', line):
                    expanded.append('{}{}'.format(indent, self.cleanup_names(col)))
            #
            if len(expanded) > 0:
                lines[i] = (start + '\n' if start else '') + ',\n'.join(expanded)
        #
        return lines



    def clean_trigger(self, lines, object_name = '', config = {}):
        remove_lines    = []
        disabled        = ''
        #
        for (i, line) in enumerate(lines):
            # fix trigger status
            if line.startswith('ALTER TRIGGER '):
                lines[i] = ''
                remove_lines.append(i)
                #
                if line.endswith(' DISABLE;'):
                    disabled = 'ALTER TRIGGER {} DISABLE;'.format(object_name.lower())
        #
        for i in sorted(remove_lines, reverse = True):
            lines.pop(i)

        # fix trailing spaces
        lines = '\n'.join(lines).rstrip('/').rstrip().split('\n')
        #
        if disabled:
            lines.append('/\n--\n' + disabled)
        #
        lines.append('/')
        return lines



    def clean_sequence(self, lines, object_name = '', config = {}):
        lines[0] = lines[0].replace(' CACHE 20 ', ' ')
        lines[0] = lines[0].replace(' MAXVALUE 9999999999999999999999999999', '')
        lines[0] = lines[0].replace(' MAXVALUE 999999999999999999999999999', '')
        lines[0] = lines[0].replace(' INCREMENT BY 1', '')
        lines[0] = lines[0].replace(' NOORDER', '')
        lines[0] = lines[0].replace(' NOCYCLE', '')
        lines[0] = lines[0].replace(' NOKEEP', '')
        lines[0] = lines[0].replace(' NOSCALE', '')
        lines[0] = lines[0].replace(' NOPARTITION', '')
        lines[0] = lines[0].replace(' GLOBAL', '')
        #
        lines[0] = util.replace(lines[0], ' START WITH \d+ ', ' ')
        lines[0] = util.replace(lines[0], '\s+', ' ').strip()
        #
        lines[0] = lines[0].replace(' MINVALUE',  '\n    MINVALUE')
        lines[0] = lines[0].replace(' START',     '\n    START')
        lines[0] = lines[0].replace(' CACHE',     '\n    CACHE')
        #
        lines[0] = util.replace(lines[0], '\s+;', ';')
        #
        drop_obj = '-- DROP SEQUENCE {};'.format(object_name.lower())
        #
        return self.rebuild_lines([drop_obj] + lines)



    def clean_synonym(self, lines, object_name = '', config = {}):
        lines[0] = self.split_columns(lines[0].replace(' FOR ', '\n    FOR '))
        #
        return self.rebuild_lines(lines)



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



    def rebuild_lines(self, lines):
        # remove empty lines
        lines = '\n'.join(lines).rstrip().splitlines()
        lines = list(filter(None, lines))
        #
        return lines



    def split_columns(self, line, indent = 4):
        # split columns in between brackets to multiple lines
        content = util.extract('[(]([^\)]+)[)]', line)
        columns = content.replace(', ', ',').split(',')
        #
        if len(columns) > 1:
            start   = '\n' + util.extract(r'^(\s*)', line.split('\n')[-1])
            splttr  = ',' + start + (' ' * indent)
            line    = line.replace(content, splttr.lstrip(',') + splttr.join(columns) + start)
        #
        return self.cleanup_names(line)



    def cleanup_names(self, line):
        for col in re.findall(r'(\"[A-Z0-9_$#]+\")', line):
            line = line.replace(col, col.replace('"', '').lower())
        #
        return line



    def get_object_comments(self, lines, object_name):
        if object_name in self.comments:
            comment = (self.comments[object_name]['']['comments'] or '').replace('\'', '')
            lines.append('--')
            lines.append('COMMENT ON TABLE {} IS \'{}\';'.format(object_name.lower(), comment))
        #
        if object_name in self.comments_col:
            lines.append('--')
            for column_name in self.comments[object_name].keys():
                if column_name:
                    column_full = self.comments[object_name][column_name]['column_full']
                    comment     = (self.comments[object_name][column_name]['comments'] or '').replace('\'', '')
                    lines.append('COMMENT ON COLUMN {} IS \'{}\';'.format(column_full, comment))
        #
        return lines



if __name__ == "__main__":
    Export_DB()

