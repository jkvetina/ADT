# coding: utf-8
import sys, os, re, shutil, subprocess, argparse, glob
#
import config
import deploy
from lib import util
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

class Patch(config.Config):

    def __init__(self, parser):
        super().__init__(parser)

        # process arguments and reinitiate config
        util.assert_(self.args.target, 'MISSING ARGUMENT: TARGET ENV')
        #
        self.patch_code         = self.args.patch
        self.patch_seq          = self.args.seq or ''
        self.search_message     = self.args.search or [self.patch_code]
        self.info.branch        = self.args.branch or self.config.repo_branch or self.info.branch or self.repo.active_branch
        self.add_commits        = self.args.add
        self.ignore_commits     = self.args.ignore
        self.search_depth       = self.args.depth or self.config.repo_commits
        self.full_exports       = self.args.full
        #
        self.init_config()

        # prepare internal variables
        self.patch_files        = []
        self.patch_files_apex   = []
        self.patch_file         = ''
        self.patch_grants       = self.repo_root + self.config.path_objects + self.config.patch_grants
        self.patch_folder       = self.repo_root + self.config.patch_root   + self.config.patch_folder
        self.patch_folders      = {}
        self.patch_sequences    = []
        self.patch_current      = {}
        self.all_commits        = {}
        self.relevant_commits   = {}
        self.relevant_count     = {}
        self.relevant_files     = {}
        self.diffs              = {}
        self.head_commit        = None
        self.first_commit       = None
        self.last_commit        = None
        self.postfix_before     = '_before'
        self.postfix_after      = '_after'

        # set current commit to the head and search through recent commits
        self.current_commit_obj = self.repo.commit('HEAD')
        self.current_commit     = self.current_commit_obj.count()
        self.patch_folder       = self.replace_tags(self.patch_folder)  # replace tags in folder

        # fetch changes in Git
        if self.args.fetch:
            self.fetch_changes()

        # go through patch folders
        self.patch_folder_splitter = '-'
        self.get_patch_folders()

        # reuse info from Deploy script
        self.deploy             = deploy.Deploy(parser, ignore_timer = True)
        self.available_ref      = self.deploy.available_ref

        # archive old patches and quit
        if self.args.archive != None:
            self.archive_patches(self.args.archive)
            util.quit()

        # create patch
        if self.patch_code != None and len(self.patch_code) > 0:
            util.print_header('BUILDING PATCH FOR: {}'.format(self.patch_code))
            util.print_help('use -search    to adjust the matched commits')
            util.print_help('use -depth     to adjust the number of recent commits searched')
            util.print_help('use -add #     to limit which commits will be processed')
            util.print_help('use -ignore #  to limit which commits will not be processed')
            print()

        # show matching patches
        existing_patches = []
        for ref in sorted(self.available_ref.keys(), reverse = True):
            info = self.available_ref[ref]
            if (self.patch_code == None or self.patch_code in info['patch_name']):
                existing_patches.append({
                    'ref'           : info['ref'],
                    'patch_name'    : info['patch_name'],
                    'files'         : len(info['files']),
                    'deployed_at'   : info['deployed_at'],
                    'result'        : info['result'],
                })

        # check patch code
        if self.patch_code == None or len(self.patch_code) == 0:
            util.print_header('EXISTING PATCHES:')
            util.print_table(existing_patches)
            #
            util.assert_(self.patch_code, 'MISSING ARGUMENT: PATCH CODE')

        # create patch
        if self.patch_code != None and len(self.patch_code) > 0:
            # get through commits for specific patch name/code
            self.get_patch_commits()
            #
            if self.patch_seq != '':
                # create patch for requested name and seq
                self.create_patch()
            else:
                # show recent commits for selected patch
                # show more details if we have them
                self.show_recent_commits()
                #
                util.print_header('EXISTING PATCHES:')
                util.print_table(existing_patches)

                # show help for processing specific commits
                if self.patch_seq == '':
                    if self.patch_current['day'] in self.patch_folders:
                        data = []
                        for folder, info in self.patch_folders[self.patch_current['day']].items():
                            data.append({
                                #'folder'    : folder
                                'day'           : info['day'],
                                'seq'           : info['seq'],
                                'patch_code'    : info['patch_code'],
                            })
                        #
                        util.print_header('TODAY\'S FOLDERS:')
                        util.print_table(data)

                # offer/hint next available sequence
                if self.patch_code != None:
                    try:
                        next = max(self.patch_sequences)
                        next = str(int(next) + 1) if next.isnumeric() else '#'
                    except:
                        next = '1'
                    #
                    util.print_header('FOR NEW PATCH SPECIFY SEQUENCE:', next)
                    util.print_help('add -seq #     to actually create a new patch files')
                    print()



    def create_patch(self):
        util.print_header('CREATING PATCH:', self.patch_code + (' (' + self.patch_seq + ')').replace(' ()', ''))
        print()

        # show commits and files
        for commit in sorted(self.relevant_commits.keys()):
            data = self.relevant_commits[commit]
            print('  {}) {}'.format(commit, data.summary))  # data.author.email, data.authored_datetime
        print()

        # show summary
        short = self.patch_folder.replace(self.repo_root, './')
        util.assert_(not ('{$' in self.patch_folder), 'LEFOVER TAGS IN FOLDER', short)
        #
        summary = []
        for order, schema_with_app in enumerate(sorted(self.relevant_files.keys())):
            schema, app_id, _ = (schema_with_app + '..').split('.', maxsplit = 2)
            summary.append({
                'order'     : order + 1,
                'file'      : schema_with_app + '.sql',
                'schema'    : schema,
                'app_id'    : int(app_id) if app_id.isnumeric() else '',
                'commits'   : len(self.relevant_count[schema_with_app]),
                'files'     : len(self.relevant_files[schema_with_app]),
            })
        util.print_header('PATCH CREATED:', short)
        util.print_table(summary, right_align = ['app_id'])

        # create snapshot folder
        if not os.path.exists(self.patch_folder):
            os.makedirs(self.patch_folder)
        else:
            # delete everything in patch folder
            shutil.rmtree(self.patch_folder, ignore_errors = True, onerror = None)

        # create patch files
        self.create_patch_files()



    def get_patch_folders(self):
        # split current folder
        curr_folder         = self.patch_folder.replace(self.repo_root + self.config.patch_root, '')
        self.patch_current  = dict(zip(['day', 'seq', 'patch_code'], curr_folder.split(self.patch_folder_splitter, maxsplit = 2)))

        # get more ifno from folder name
        for folder in sorted(glob.glob(self.repo_root + self.config.patch_root + '*')):
            folder  = folder.replace(self.repo_root + self.config.patch_root, '')
            info    = dict(zip(['day', 'seq', 'patch_code'], folder.split(self.patch_folder_splitter, maxsplit = 2)))
            #
            if info['day'] == self.patch_current['day'] and not (info['seq'] in self.patch_sequences):
                self.patch_sequences.append(info['seq'])
            #
            if not (info['day'] in self.patch_folders):
                self.patch_folders[info['day']] = {}
            self.patch_folders[info['day']][folder] = info

        # check clash on patch sequence
        if self.patch_current['patch_code'] != self.patch_code and self.patch_current['seq'] in self.patch_sequences:
            util.raise_error('CLASH ON PATCH SEQUENCE'
                'you should select a different -seq #')



    def get_patch_commits(self):
        # loop through all recent commits
        print('\nSEARCHING REPO:')
        progress_target = self.search_depth
        progress_done   = 0
        #
        for commit in list(self.repo.iter_commits(self.info.branch, max_count = self.search_depth, skip = 0)):
            self.all_commits[commit.count()] = commit
            progress_done = util.print_progress(progress_done, progress_target)
        progress_done = util.print_progress(progress_target, progress_target)
        print('\n')

        # add or remove specific commits from the queue
        for _, commit in self.all_commits.items():
            if self.head_commit == None:
                self.head_commit = commit.count()

            # skip non requested commits
            if len(self.add_commits) > 0:
                commits     = '|{}|'.format('|'.join(self.add_commits))
                search_for  = '|{}|'.format(commit.count())
                #
                if not (search_for in commits):
                    continue

            # skip ignored commits
            if len(self.ignore_commits) > 0:
                commits     = '|{}|'.format('|'.join(self.ignore_commits))
                search_for  = '|{}|'.format(commit.count())
                #
                if search_for in commits:
                    continue

            # skip non relevant commits
            if self.search_message != '':
                found_match = False
                for word in [word for word in self.search_message if word is not None]:
                    if word in commit.summary:
                        found_match = True
                        break
                if not found_match:
                    continue

            # store relevant commit
            self.relevant_commits[commit.count()] = commit

            # process files in commit
            for file in commit.stats.files.keys():
                # process just the listed extensions (in the config)
                if os.path.splitext(file)[1] != '.sql':
                    continue

                # process just database and APEX exports
                if not (file.startswith(self.config.path_objects)) and not (file.startswith(self.config.path_apex)):
                    continue

                # get APEX app info from the yaml file
                schema  = self.info.schema
                app_id  = None
                #
                if self.config.path_apex in file:
                    search = re.search('^f(\d+)[/]', file.replace(self.config.path_apex, ''))
                    if search:
                        app_id = int(search.group(1))       # get app_id from APEX folder
                        schema += '.{}'.format(app_id)      # append app_id to separate APEX files
                #
                if not (schema in self.relevant_files):
                    self.relevant_files[schema] = []
                    self.relevant_count[schema] = []
                if not (file in self.relevant_files[schema]):
                    self.relevant_files[schema].append(file)
                if not (commit.count() in self.relevant_count[schema]):
                    self.relevant_count[schema].append(commit.count())

        # check number of commits
        if len(self.relevant_commits.keys()) == 0:
            util.raise_error('NO COMMITS FOUND',
                'please adjust your parameters')

        # get last version (max) and version before first change (min)
        self.first_commit   = min(self.relevant_commits) - 1
        self.last_commit    = max(self.relevant_commits)
        #
        if not (self.first_commit in self.all_commits):
            self.all_commits = min(self.all_commits)
        #
        self.first_commit_obj   = self.all_commits[self.first_commit]
        self.last_commit_obj    = self.all_commits[self.last_commit]



    def show_recent_commits(self):
        # pivot commits
        commits_map = {}
        for ref in sorted(self.available_ref.keys()):
            for commit in self.available_ref[ref]['commits']:
                commits_map[commit] = ref

        # show relevant recent commits
        depth   = 'DEPTH: {}/{}'.format(self.head_commit - self.first_commit + 1, self.search_depth) if self.args.get('depth') else ''
        header  = 'REQUESTED' if (self.args.add != [] or self.args.ignore != []) else 'RECENT'
        data    = []
        #
        for commit in sorted(self.relevant_commits.keys(), reverse = True):
            summary = self.relevant_commits[commit].summary
            data.append({
                'commit'        : commit,
                'summary'       : (summary[:50] + '..') if len(summary) > 50 else summary,
                'patch_ref'     : commits_map.get(commit, ''),
            })
        #
        util.print_header('{} COMMITS FOR "{}":'.format(header, ' '.join(self.search_message)), depth)
        util.print_table(data)



    def create_patch_files(self):
        # simplify searching for ignored files
        skip_apex_files = '|{}|'.format('|'.join(self.config.apex_files_ignore))

        # process files per schema
        for schema_with_app in self.relevant_files.keys():
            target_schema, app_id, _ = (schema_with_app + '..').split('.', maxsplit = 2)
            payload = []

            # generate patch file name for specific schema
            self.patch_file      = '{}/{}.sql'.format(self.patch_folder, schema_with_app)
            self.patch_spool_log = './{}.log'.format(schema_with_app)  # must start with ./ and ends with .log for proper function

            # generate patch header
            payload.extend([
                '--',
                '-- {:>16} | {}'.format('PATCH CODE', self.patch_code),
                '-- {:>16} | {}'.format('SCHEMA', target_schema),
                '-- {:>16} | {}'.format('APP ID', app_id) if app_id else None,
                '--',
            ])

            # get differences in between first and last commits
            # also fill the self.diffs() with files changed in commits
            # in self.relevant_files we can have files which were deleted
            payload.extend(self.get_differences(self.relevant_files[schema_with_app]))

            # need to map files to object types & sort them by dependencies
            # (1) self.diffs.keys() with committed files
            # (2) self.patch_templates with template files (only if some files were changed), before and after (1)
            # (3) self.patch_script with adhoc files (add every time), before and after (1)
            #
            files_processed     = []
            files_to_process    = {}
            #
            for file in self.diffs.keys():
                files_to_process[file] = File(file, config = self.config)

            # processed groups one by one in order defined by patch_map
            for group in self.config.patch_map.keys():
                if self.debug:
                    print('  -', group)
                #
                for object_type in self.config.patch_map[group]:
                    # scenario (1)
                    files = []
                    for file in list(files_to_process.keys()):  # copy
                        obj = files_to_process[file]
                        if obj.is_object and obj.object_type == object_type:
                            if not (file in files_processed):
                                files.append(file)
                                files_to_process.pop(file, '')
                    #
                    scripts_before  = self.get_script_before_files()    if not app_id else []
                    scripts_after   = self.get_script_after_files()     if not app_id else []

                    # need to sort these files by dependencies
                    #
                    #
                    #

                    # dont process template folder if there are no group related files
                    if len(files) == 0 and len(scripts_before) == 0 and len(scripts_after) == 0:
                        continue
                    #
                    if self.debug:
                        print('    -', object_type)

                    # (2) before template
                    if len(files) > 0:
                        for file in self.get_template_files(group + self.postfix_before):
                            if not (file in files_processed):
                                files_processed.append(file)
                                if self.debug:
                                    print('        >>', file)

                    # (3) before script
                    for file in scripts_before:
                        if '/{}{}/'.format(group, self.postfix_before) in file:
                            files_processed.append(file)
                            if self.debug:
                                print('        >>>', file)

                    # (1) add changed objects to the list
                    for file in files:
                        files_processed.append(file)
                        files_to_process.pop(file, '')
                        if self.debug:
                            print('        >', file)

                    # (3) after script
                    for file in scripts_after:
                        if '/{}{}/'.format(group, self.postfix_after) in file:
                            files_processed.append(file)
                            if self.debug:
                                print('        >>>', file)

                    # (2) after template
                    if len(files) > 0:
                        for file in self.get_template_files(group + self.postfix_after):
                            if not (file in files_processed):
                                files_processed.append(file)
                                if self.debug:
                                    print('        >>', file)

            # attach APEX files
            if app_id:
                for file in list(files_to_process.keys()):  # copy
                    files_processed.append(file)
            #
            elif len(files_to_process.keys()) > 0:
                util.raise_error('NOT ALL FILES PROCESSED')

            # create snapshot files
            for file in files_processed:
                self.create_file_snapshot(file, app_id = app_id)
            #
            self.create_snapshots(app_id)

            # set defaults in case they are not specified in init file
            # spool output to the file
            payload.extend([
                'SET DEFINE OFF',
                'SET TIMING OFF',
                'SET SQLBLANKLINES ON',
                '--',
                'WHENEVER OSERROR  EXIT ROLLBACK;',
                'WHENEVER SQLERROR EXIT ROLLBACK;',
                '--',
                'SPOOL "{}" APPEND;'.format(self.patch_spool_log),
                ''
            ])

            # add properly sorted files (objects by dependencies) to the patch
            if app_id and app_id in self.full_exports:
                # attach the whole application for full imports
                payload.extend([
                    '--',
                    '-- APPLICATION {}'.format(app_id),
                    '--',
                    'SET SERVEROUTPUT OFF',
                    '@"./{}f{}/f{}.sql";'.format(self.config.path_apex, app_id, app_id),
                    'SET SERVEROUTPUT ON',
                    '',
                ])
            #
            else:
                # load init files, for database or APEX
                payload.extend(self.attach_files(self.get_template_files('apex_init' if app_id else 'db_init'), category = 'INIT'))

                # attach APEX starting file for partial APEX exports
                if app_id:
                    # attach the whole application for full imports (as a fallback)
                    payload.extend([
                        'SET DEFINE OFF',
                        'SET TIMING OFF',
                        '--',
                        'PROMPT --;',
                        'PROMPT -- APEX FULL EXPORT',
                        'PROMPT --;',
                        '--@"./{}f{}/f{}.sql";'.format(self.config.path_apex, app_id, app_id),
                        '',
                    ])

                    # attach starting file
                    file = '{}f{}/{}'.format(self.config.path_apex, app_id, 'application/set_environment.sql')
                    payload.extend(self.attach_file(file, header = 'APEX COMPONENTS START', category = 'FIXED'))

                # go through files
                apex_pages = []
                for file in files_processed:
                    if app_id == '':
                        pass
                        # load type related files for database objects
                        #
                        #
                        #

                    # modify list of APEX files
                    if app_id:
                        try:
                            short_file = '/application/' + file.split('/application/')[1]
                        except:
                            short_file = ''

                        # move APEX pages to the end + create script to delete them in patch
                        search = re.search('/pages/page_(\d+)\.sql', file)
                        if search:
                            apex_pages.append(file)
                            continue

                        # skip full APEX exports
                        if len(re.findall('/f\d+/f\d+\.sql$', file)) > 0:
                            continue

                        # skip file if it should be ignored in the patch (but keep it in snapshot folder)
                        if short_file in skip_apex_files:
                            continue

                    # attach file reference
                    payload.extend(self.attach_file(file, category = 'COMMIT'))

                # attach APEX pages to the end
                if len(apex_pages) > 0:
                    payload.extend(self.fix_apex_pages(apex_pages))
            #
            payload.append('')

            # attach APEX ending file for partial APEX exports
            if app_id and not (app_id in self.full_exports):
                if not (app_id in self.full_exports):
                    file = '{}f{}/{}'.format(self.config.path_apex, app_id, 'application/end_environment.sql')
                    payload.extend(self.attach_file(file, header = 'APEX END', category = 'FIXED'))

            # add grants made on referenced objects
            payload.extend([
                'PROMPT --;',
                'PROMPT -- GRANTS',
                'PROMPT --;',
            ])
            payload.extend(self.get_grants_made())

            # load final files, for database or APEX
            payload.extend(self.attach_files(self.get_template_files('apex_end' if app_id else 'db_end'), category = 'END'))

            # add flag so deploy script can evaluate it as successful
            payload.extend([
                'PROMPT --;',
                'PROMPT -- SUCCESS',
                'PROMPT --;',
                'SPOOL OFF;',           # spool output end
                '',
            ])

            # store payload in file
            self.create_patch_file(payload, app_id = app_id)



    def get_differences(self, rel_files):
        self.diffs      = {}    # cleanup
        payload         = []
        new_files       = []
        deleted_files   = []
        modifed_files   = []
        #
        for diff in self.first_commit_obj.diff(self.last_commit_obj):
            file = diff.b_path.replace('\\', '/').replace('//', '/')
            # 'a_blob', 'a_mode', 'a_path', 'a_rawpath', 'b_blob', 'b_mode', 'b_path', 'b_rawpath', 'change_type',
            # 'copied_file', 'deleted_file', 'diff', 'new_file', 'raw_rename_from', 'raw_rename_to', 're_header',
            # 'rename_from', 'rename_to', 'renamed', 'renamed_file', 'score'
            #print(dir(x))

            # skip deleted files
            if 'file deleted in rhs' in str(diff):
                continue

            # process file and sort to show the file status
            if file in rel_files and not (file in self.diffs):
                self.diffs[file] = diff
                #
                if diff.new_file:
                    new_files.append(file)
                elif diff.deleted_file:
                    deleted_files.append(file)
                else:
                    modifed_files.append(file)

        # show commits only with relevant files
        payload.append('-- COMMITS:')
        for commit_number, commit in self.relevant_commits.items():
            files_found = False
            for file in commit.stats.files:
                if file in rel_files:
                    files_found = True
                    break
            #
            if files_found:
                payload.append('--   {}) {}'.format(commit_number, commit.summary))

        # split files by the change type
        if len(new_files) > 0:
            payload.append('--\n-- NEW FILES:')
            for file in sorted(new_files):
                payload.append('--   {}'.format(file))  # self.diffs[file].change_type
        #
        if len(deleted_files) > 0:
            payload.append('--\n-- DELETED FILES:')
            for file in sorted(deleted_files):
                payload.append('--   {}'.format(file))  # self.diffs[file].change_type
        #
        if len(modifed_files) > 0:
            payload.append('--\n-- MODIFIED FILES:')
            for file in sorted(modifed_files):
                payload.append('--   {}'.format(file))  # self.diffs[file].change_type
        #
        payload.append('--')
        #
        return payload



    def get_script_before_files(self):
        folder = '{}*{}/*.sql'.format(self.config.patch_scripts_dir, self.postfix_before)
        return list(sorted(glob.glob(folder)))



    def get_script_after_files(self):
        folder = '{}*/*.sql'.format(self.config.patch_scripts_dir, self.postfix_after)
        return list(sorted(glob.glob(folder)))



    def get_template_files(self, folder):
        return list(sorted(glob.glob('{}{}/*.sql'.format(self.config.patch_template_dir, folder))))



    def attach_file(self, file, header = '', category = ''):
        attach_type = ''
        if category != '':
            attach_type = category
        if self.config.patch_template_dir in file:
            attach_type = 'TEMPLATE'
        elif self.config.patch_scripts_dir in file:
            attach_type = 'SCRIPT'
        #
        file = self.create_file_snapshot(file)
        file = file.replace(self.patch_folder, '')       # replace first, full path
        file = file.replace(self.repo_root, '')
        file = file.replace(self.config.patch_template_dir, '')
        #
        payload = []
        if header != '':
            payload = [
                'PROMPT --;',
                'PROMPT -- {}'.format(header),
                'PROMPT --;',
            ]
        payload.extend([
            'PROMPT -- {}: {}'.format(attach_type or 'FILE', file),
            '@"./{}";'.format(file.lstrip('/')),
            '',
        ])
        return payload



    def attach_files(self, files, category = ''):
        if isinstance(files, str):
            files = sorted(glob.glob(files))
        #
        payload = []
        for file in files:
            payload.extend(self.attach_file(file, category = category))
        return payload



    def create_snapshots(self, app_id):
        # copy some files even if they did not changed
        if app_id != None and str(app_id) != '':
            path = '{}f{}/'.format(self.config.path_apex, app_id).replace('//', '/')
            for file in self.config.apex_files_copy:
                file = path + file
                if os.path.exists(file):
                    # get copied files from directory
                    with open(file, 'rt') as f:
                        self.create_file_snapshot(file, file_content = f.read(), app_id = app_id)

            # attach full export
            file = '{}f{}.sql'.format(path, app_id)
            self.create_file_snapshot(file, app_id = app_id)



    def create_patch_file(self, payload, app_id):
        payload = '\n'.join([line for line in payload if line != None])

        # save in schema patch file
        with open(self.patch_file, 'wt', encoding = 'utf-8', newline = '\n') as w:
            w.write(payload)
        #
        if app_id:
            self.patch_files_apex.append(self.patch_file)
        else:
            self.patch_files.append(self.patch_file)



    def create_file_snapshot(self, file, file_content = None, app_id = None):
        # create folders and copy files
        target_file = '{}/{}'.format(self.patch_folder, file).replace('//', '/')

        # shorten target folder for template files
        if self.config.patch_template_dir in target_file:
            target_file = target_file.replace(self.config.patch_scripts_dir,  self.config.patch_template_snap)
            target_file = target_file.replace(self.config.patch_template_dir, self.config.patch_template_snap)
            with open(file, 'rt') as f:
                file_content = self.replace_tags(f.read())

        # get file content from commit, not local file
        if file_content == None:
            file_content = self.get_file_from_commit(file, commit = str(self.last_commit_obj))

        # change page audit columns
        if self.config.replace_audit and app_id != None:
            if ('/application/pages/page_' in file or '/f{}/f{}.sql'.format(app_id, app_id) in file):
                file_content = re.sub(r",p_last_updated_by=>'([^']+)'",         ",p_last_updated_by=>'{}'".format(self.patch_code), file_content)
                file_content = re.sub(r",p_last_upd_yyyymmddhh24miss=>'(\d+)'", ",p_last_upd_yyyymmddhh24miss=>'{}'".format(self.config.today_full_raw), file_content)

        # save file
        target_folder = os.path.dirname(target_file)
        if not os.path.exists(target_folder):
            os.makedirs(target_folder)
        with open(target_file, 'wt', encoding = 'utf-8') as w:
            w.write(file_content)
        #
        return target_file



    def fix_apex_pages(self, apex_pages):
        payload = [
            '',
            'PROMPT --;',
            'PROMPT -- APEX PAGES',
            'PROMPT --;',
            'BEGIN',
        ]
        #
        for file in apex_pages:
            search = re.search('/pages/page_(\d+)\.sql', file)
            if search:
                page_id = int(search.group(1))
                payload.append('    wwv_flow_imp_page.remove_page(p_flow_id => wwv_flow.g_flow_id, p_page_id => {});'.format(page_id))
        #
        payload.extend([
            'END;',
            '/',
            '--',
        ])

        # recreate requested pages
        for file in apex_pages:
            payload.append(self.config.patch_file_link.replace('{$FILE}', file))
        #
        return payload



    def get_grants_made(self):
        payload = []

        # grab the file with grants made
        with open(self.patch_grants, 'rt', encoding = 'utf-8') as f:
            file_content = f.readlines()
            for line in file_content:
                if line.startswith('--'):
                    continue

                # find match on object name
                find_name = re.search('\sON\s+(.*)\s+TO\s', line)
                if find_name:
                    find_name = find_name.group(1).lower()
                #
                for file in self.diffs:
                    object_name = os.path.basename(file).split('.')[0].lower()
                    if object_name == find_name:
                        payload.append(line.strip())
                        break
        #
        payload.append('')
        return payload



    def get_file_from_commit(self, file, commit):
        # run command line and capture the output, text file is expected
        command = 'git show {$REV}:{$FILE}'
        command = command.replace('{$REV}',  commit)
        command = command.replace('{$FILE}', file)
        #
        result  = subprocess.run(command, shell = True, capture_output = True, text = True)
        return (result.stdout or '')



    def fetch_changes(self):
        self.repo.git.checkout()
        self.repo.git.pull()










    def archive_patches(self, above_ref = 10):
        archive_folder = self.repo_root + self.config.patch_archive
        if not (os.path.exists(archive_folder)):
            os.makedirs(archive_folder)

        # find folders to archive
        data = []
        for ref in sorted(self.available_ref.keys(), reverse = True):
            if ref < int(above_ref):
                break
            data.append({
                'ref'           : ref,
                'patch_name'    : self.available_ref[ref]['patch_name'],
            })
        #
        util.print_header('ARCHIVING PATCHES:')
        util.print_table(data)
        #
        for row in data:
            source_folder = self.repo_root + self.config.patch_root + row['patch_name']
            shutil.make_archive(
                base_name   = archive_folder + row['patch_name'],
                format      = 'zip',
                root_dir    = archive_folder,
                base_dir    = source_folder         # zip whole folder
            )
            shutil.rmtree(source_folder, ignore_errors = True, onerror = None)



if __name__ == "__main__":
    # parse arguments
    parser = argparse.ArgumentParser()

    # actions and flags
    parser.add_argument('-debug',       help = 'Turn on the debug/verbose mode',    default = False, nargs = '?', const = True)
    parser.add_argument('-key',         help = 'Key or key location to encypt passwords')
    parser.add_argument('-schema',      help = 'Schema/connection name')
    #
    parser.add_argument('-target',      help = 'Target environment')
    parser.add_argument('-patch',       help = 'Patch code (name for the patch files)')
    parser.add_argument('-seq',         help = 'Sequence in patch folder, {$PATCH_SEQ}')
    parser.add_argument('-search',      help = 'Search string for Git to search just for relevant commits',     default = None, nargs = '*')
    parser.add_argument('-add',         help = 'Process just specific commits',                                 default = [],   nargs = '*')
    parser.add_argument('-ignore',      help = 'Ignore specific commits',                                       default = [],   nargs = '*')
    parser.add_argument('-branch',      help = 'To override active branch',                                     default = None)
    parser.add_argument('-depth',       help = 'Number of recent commits to search',                            default = None,               type = int)
    parser.add_argument('-full',        help = 'Specify APEX app(s) where to use full export',                  default = [],   nargs = '*')
    parser.add_argument('-archive',     help = 'To archive patches older than passed #',                        default = None, nargs = '?')
    parser.add_argument('-fetch',       help = 'Fetch Git changes before patching',                             default = False, nargs = '?', const = True)
    #
    Patch(parser)

