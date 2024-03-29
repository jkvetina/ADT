# coding: utf-8
import sys, os, re, argparse
#
import config
from lib import util

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
        self.patch_code     = self.args.patch
        self.limit_app_id   = self.args.app
        self.limit_schema   = self.args.schema or ''
        self.limit_pages    = self.args.page or []
        self.limit_type     = self.args.type or []
        self.limit_name     = self.args.name or []
        #
        self.patch_ref_dir  = 'refs/'
        self.source_dir     = self.repo_root + self.config.path_apex + 'f{}/'.format(self.limit_app_id)
        self.target_dir     = self.repo_root + self.config.patch_scripts_dir.replace('{$PATCH_CODE}', self.patch_code) + self.patch_ref_dir
        #
        if self.limit_schema:
            self.patch_grants = self.patch_grants.replace('/.', '/{}.'.format(self.limit_schema))

        # parse all embedded code files for object names based by schema prefix
        all_tags = {}
        ref_tags = {}
        for file in util.get_files('{}embedded_code/**/*.sql'.format(self.source_dir)):
            # search for specific pages
            if len(self.limit_pages) > 0:
                found = False
                for page in self.limit_pages:
                    page = '/pages/page_{}.sql'.format(str(page).rjust(5, '0'))
                    if page in file:
                        found = True
                        break
                if not found:
                    continue

            # search for object names
            file_tags = {}
            with open (file, 'rt', encoding = 'utf-8') as f:
                for line in f.readlines():
                    for tag in re.findall(self.limit_schema + r'\.[A-Z0-9\$_-]+', line.upper()):
                        found = False
                        if len(self.limit_name) > 0:
                            for name in self.limit_name:
                                name = '^(' + name.replace('%', '.*') + ')$'
                                if util.extract(name, tag):
                                    found = True
                                    break
                            if not found:
                                continue
                        #
                        if not (tag in file_tags):
                            file_tags[tag] = 0
                        file_tags[tag] += 1
                        if not (tag in all_tags):
                            all_tags[tag] = 0
                        all_tags[tag] += 1
                        #
                        if not (tag in ref_tags):
                            ref_tags[tag] = []
                        if not (file in ref_tags[tag]):
                            ref_tags[tag].append(file)

        # create overview
        found_files = []
        data        = []
        objects     = self.repo_objects.keys()
        #
        for tag in sorted(all_tags.keys()):
            object_name     = tag.split('.')[1]
            object_found    = False
            #
            for obj_code in objects:
                if obj_code.endswith('.' + object_name):
                    obj = self.repo_objects[obj_code]
                    if not (obj['file'] in found_files):
                        found_files.append(obj['file'])
                    #
                    object_type     = obj['object_type']
                    object_found    = True
                    #
                    if len(self.limit_type) > 0:
                        found = False
                        for type_ in self.limit_type:
                            type_ = '^(' + type_.replace('%', '.*') + ')$'
                            if util.extract(type_, object_type):
                                found = True
                                break
                        if not found:
                            continue
                    #
                    if ' BODY' in object_type:      # dont show bodies
                        continue
                    #
                    data.append({
                        'object_name'   : object_name,
                        'object_type'   : object_type,
                        'pages'         : len(ref_tags[tag]),
                        'references'    : all_tags[tag],
                    })
            #
            if not object_found:
                data.append({
                    'object_name'   : object_name,
                    'object_type'   : '?',
                    'pages'         : len(ref_tags[tag]),
                    'references'    : all_tags[tag],
                })
        #
        util.print_header('{} OBJECTS FROM EMBEDDED CODE:'.format(self.limit_schema), ' ({})'.format(len(data)))
        util.print_table(data)

        # copy files to patch scripts folder
        #util.print_header('SORTED FILES BY DEPENDENCIES:')
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
            short       = source_file.replace(self.repo_root + self.config.path_objects, '').replace('/', '.')
            target_file = self.target_dir + short
            #
            script.extend([
                '',
                'PROMPT "";',
                'PROMPT "-- REF: {}{}";'.format(self.patch_ref_dir, short),
                '@"./{}{}"'.format(self.patch_ref_dir, short),
            ])
            #
            if os.path.exists(target_file):
                os.remove(target_file)
            util.copy_file(source_file, target_file)
            #
            #print('  - {}'.format(short))
        #print()

        # append object grants
        objects = []
        for row in data:
            objects.append(row['object_name'])
        #
        script.extend([
            '',
            '--',
            '-- RELATED GRANTS',
            '--',
        ])
        grants = self.get_grants_made(object_names = list(set(objects)))
        for grant in grants:
            script.append(grant)

        # create script to install objects in proper oder
        script_file = self.target_dir.replace(self.patch_ref_dir, self.patch_ref_dir.rstrip('/') + '.sql')
        with open(script_file, 'wt') as w:
            w.write('\n'.join(script) + '\n')

        # show leftovers
        unknown = []
        for row in data:
            if row['object_type'] == '?':
                unknown.append(row['object_name'])
        #
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

