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

class Search_APEX(config.Config):

    def __init__(self, parser):
        super().__init__(parser)

        # setup env and paths
        self.init_config()

        #
        # PARSE REFERENCED OBJECTS FROM EMBEDDED CODE REPORT, THE SCHEMA PREFIX HELPS A LOT
        # SO YOU NEED TO REFRESH THE EMBEDDED CODE REPORTS FIRST
        #
        # TRANSLATE OBJECT NAMES TO FILES
        # COPY REFERENCED FILES TO PATCH FOLDER /patch_scripts/$PATCH_CODE/refs/
        #
        #   --> WE ARE MISING INVOKE API REFERENCES, NEED TO PARSE APEX_APPS_REGIONS VIEW
        #   --> IF WE DONT HAVE SCHEMA PREFIX, SEARCH FOR KNOWN OBJECT NAMES
        #
        self.patch_code     = self.args.patch or ''
        self.limit_app_id   = self.args.app
        self.limit_schema   = self.args.schema or ''
        self.limit_pages    = self.args.page or []
        self.limit_type     = self.args.type or []
        self.limit_name     = self.args.name or []
        #
        self.refs_name      = 'refs/'
        self.append_name    = 'append/'
        #
        self.source_dir     = self.repo_root + self.config.path_apex + 'f{}/'.format(self.limit_app_id)
        self.target_dir     = self.repo_root + self.config.patch_scripts_dir.replace('{$PATCH_CODE}', self.patch_code) + self.refs_name
        self.append_dir     = self.repo_root + self.config.patch_scripts_dir.replace('{$PATCH_CODE}', self.patch_code) + self.append_name
        self.obj_not_found  = []

        # parse all embedded code files for object names based by schema prefix
        page_tags   = {}
        found_files = []
        found_obj   = []
        unknown     = []
        data        = []
        objects     = self.repo_objects.keys()
        #
        for file in util.get_files('{}embedded_code/**/*.sql'.format(self.source_dir)):
            # search for specific pages
            limit_pages = []
            for page in self.limit_pages:
                limit_pages.append('page_{}.sql'.format(str(page).rjust(5, '0')))
            #
            if not util.get_match(os.path.basename(file), limit_pages):
                continue

            # search for object names
            with open (file, 'rt', encoding = 'utf-8') as f:
                # prepare list of objects
                if not self.limit_schema:
                    objects = []
                    for obj_code in self.repo_objects.keys():
                        object_type, object_name = obj_code.split('.')
                        object_type = object_type.replace(' BODY', '')
                        #
                        if not util.get_match(object_type, self.limit_type):
                            continue
                        if not util.get_match(object_name, self.limit_name):
                            continue
                        #
                        if object_type in ('TABLE', 'VIEW', 'PACKAGE', 'PROCEDURE', 'FUNCTION', 'SEQUENCE', 'TYPE', 'SYNONYM', 'MATERIALIZED VIEW'):
                            objects.append(object_name)
                    #
                    objects = '|'.join(sorted(objects, reverse = True))

                # parse lines in file
                for line in f.readlines():
                    if self.limit_schema:
                        # more precise, if we have schema prefix
                        tags    = re.findall(self.limit_schema + r'\.([A-Z0-9\$_-]+)', line.upper())
                    else:
                        # less precise, but ok if we have unique object names
                        tags    = re.findall('(' + objects + ')\W|(' + objects + ')$', line.upper())
                        tags    = list(filter(None, [j for i in tags for j in i]))

                    # map found tags to pages
                    for object_name in  list(set(tags)):
                        if '.' in object_name:
                            object_name = object_name.split('.')[1]
                        if not util.get_match(object_name, self.limit_name):
                            continue
                        #
                        page_id = util.extract_int('/page_(\d+)\.sql', file)
                        if not (object_name in page_tags):
                            page_tags[object_name] = []
                        if page_id != None and not (page_id in page_tags[object_name]):
                            page_tags[object_name].append(page_id)

        # connect to database to get list of referenced objects
        schema = self.connection.get('schema_apex') or self.connection.get('schema_db')
        self.init_connection(schema_name = schema)
        self.conn = self.db_connect(ping_sqlcl = False, silent = True)
        self.info['schema'] = self.connection.get('schema_db')  # to have proper grants
        #
        for row in self.conn.fetch_assoc(query.referenced_objects, app_id = self.limit_app_id):
            if len(self.limit_pages) > 0 and not (row.page_id in self.limit_pages):
                continue
            if not util.get_match(row.object_name, self.limit_name):
                continue
            #
            obj = self.get_object(object_name = row.object_name)
            if not util.get_match(obj.object_type, self.limit_type):
                continue
            #
            if not (row.object_name in page_tags):
                page_tags[row.object_name] = []
            if row.page_id != None and not (row.page_id in page_tags[row.object_name]):
                page_tags[row.object_name].append(row.page_id)

        # create overview
        for object_name in sorted(page_tags.keys()):
            obj = self.get_object(object_name = object_name)
            if obj == {}:
                data.append({
                    'object_name'   : object_name,
                    'type'          : '?',
                    'pages'         : page_tags[object_name],
                })
                continue

            # limit scope
            if not util.get_match(obj['object_type'].replace(' BODY', ''), self.limit_type) and not util.get_match(obj['object_type'], self.limit_type):
                continue

            # need to add specification too
            if ' BODY' in obj['object_type']:
                spec = self.get_object(object_name = obj['object_name'], object_type = obj['object_type'].replace(' BODY', ''))
                if not (spec['file'] in found_files):
                    found_files.append(spec['file'])
            #
            if not (obj['file'] in found_files):
                found_files.append(obj['file'])
            #
            obj_code = '{}.{}'.format(obj['object_type'].replace(' BODY', ''), obj['object_name'])
            found_obj.append(obj_code)
            data.append({
                'object_name'   : obj['object_name'],
                'type'          : obj['object_type'].replace(' BODY', ''),
                'pages'         : page_tags[obj['object_name']],
            })

        # append files from append folder
        # so you can attach any files you want before they get sorted
        # and also you dont have to care about the grants
        if len(self.limit_pages) == 0:
            for file in util.get_files(self.append_dir + '**/*.sql'):
                obj         = File(file, config = self.config)
                obj_code    = '{}.{}'.format(obj['object_type'], obj['object_name'])
                #
                if not (obj_code in found_obj) and not (obj_code.replace(' BODY.', '.') in found_obj):
                    found_obj.append(obj_code)
                    found_files.append(file)
                    data.append({
                        'object_name'   : obj['object_name'],
                        'type'          : obj['object_type'],
                        'pages'         : None,
                    })

        # adjust overview
        for i, row in enumerate(data):
            if row['type'] == '?':
                unknown.append(row['object_name'])
            #
            data[i]['pages'] = str(sorted(row.get('pages') or []))[1:-1]
            if len(self.limit_pages) == 0:
                data[i].pop('type')

        # show overview
        util.print_header('{} OBJECTS FROM EMBEDDED CODE:'.format(self.limit_schema).strip(), '({})'.format(len(data)))
        util.print_table(data)

        # without patch code just show overview on screen
        if not self.patch_code:
            return

        # copy files to patch scripts folder
        if self.debug:
            util.print_header('SORTED FILES BY DEPENDENCIES:')
        util.delete_folder(self.target_dir)
        os.makedirs(self.target_dir, exist_ok = True)
        #
        script = [
            'SET TIMING OFF',
            ''
            '--',
            '-- REFERENCED OBJECTS',
            '--',
        ]
        for source_file in self.sort_files_by_deps(found_files):
            if self.config.patch_scripts_snap in source_file:
                source_file = source_file.replace(self.append_dir, self.append_name)
                script.extend([
                    '',
                    'PROMPT "";',
                    'PROMPT "-- APPEND: {}";'.format(os.path.basename(source_file)),
                    '@"./{}"'.format(source_file),
                ])
                #
                if self.debug:
                    print('  - {}'.format(source_file.replace(self.append_name, '')))
            else:
                short       = source_file.replace(self.repo_root + self.config.path_objects, '').replace('/', '.')
                target_file = self.target_dir + short
                script.extend([
                    '',
                    'PROMPT "";',
                    'PROMPT "-- REF: {}{}";'.format(self.refs_name, short),
                    '@"./{}{}"'.format(self.refs_name, short),
                ])
                #
                if os.path.exists(target_file):
                    os.remove(target_file)
                util.copy_file(source_file, target_file)
                #
                if self.debug:
                    print('  - {}'.format(short))
        if self.debug:
            print()

        # append object grants
        objects = []
        for row in data:
            objects.append(row['object_name'])
        #
        grants = self.get_grants_made(object_names = list(set(objects)))
        if len(grants) > 0:
            script.extend([
                '',
                '--',
                '-- RELATED GRANTS',
                '--',
            ])
            for grant in grants:
                script.append(grant)

        # create script to install objects in proper oder
        script_file = self.target_dir.replace(self.refs_name, self.refs_name.rstrip('/') + '.sql')
        util.write_file(script_file, script)

        # show leftovers
        if len(unknown) > 0:
            util.print_header('UNKNOWN OBJECTS:')
            for object_name in unknown:
                print('  - {}'.format(object_name))
            print()



if __name__ == "__main__":
    # parse arguments
    parser = argparse.ArgumentParser(add_help = False)
    #
    group = parser.add_argument_group('MAIN ACTIONS')
    group.add_argument('-patch',        help = 'Patch code (name for the patch files)',                             nargs = '?')
    group.add_argument('-schema',       help = 'Schema prefix')
    #
    group = parser.add_argument_group('LIMIT SCOPE')
    group.add_argument('-app',          help = 'Limit the the scope to specific app',       type = int)
    group.add_argument('-page',         help = 'To limit APEX pages',                       type = int,             nargs = '*', default = [])
    group.add_argument('-type',         help = 'To limit object types',                                             nargs = '*', default = [])
    group.add_argument('-name',         help = 'To limit object name',                                              nargs = '*', default = [])
    #
    Search_APEX(parser)

