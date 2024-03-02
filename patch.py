# coding: utf-8
import sys, os, re, shutil, subprocess, argparse, glob
#
import config
import deploy
from lib import util
from lib import queries_patch as query          # ditch for template folder

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
        self.info.branch        = self.args.branch or self.info.branch or self.repo.active_branch
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
        self.apex_app_id        = ''
        self.all_commits        = {}
        self.relevant_commits   = {}
        self.relevant_count     = {}
        self.relevant_files     = {}
        self.relevant_objects   = {}
        self.diffs              = {}
        self.head_commit        = None
        self.first_commit       = None
        self.last_commit        = None

        # set current commit to the head and search through recent commits
        self.current_commit_obj = self.repo.commit('HEAD')
        self.current_commit     = self.current_commit_obj.count()
        self.patch_folder       = self.replace_tags(self.patch_folder)  # replace tags in folder

        # go through patch folders
        self.patch_folder_splitter = '-'
        self.get_patch_folders()

        # reuse info from Deploy script
        self.deploy             = deploy.Deploy(parser, ignore_timer = True)
        self.available_ref      = self.deploy.available_ref

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
        util.print_header('PATCH CREATED:', short)
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
        for folder in glob.glob(self.repo_root + self.config.patch_root + '*'):
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

                # get info about the file
                self.relevant_objects[file] = self.get_file_object(file)
                schema = self.relevant_objects[file]['schema']
                app_id = self.relevant_objects[file]['apex_app_id']
                if app_id != None:
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
        for schema_with_app, rel_files in self.relevant_files.items():
            target_schema, app_id, _ = (schema_with_app + '..').split('.', maxsplit = 2)

            # generate patch file name for specific schema
            self.patch_file      = '{}/{}.sql'.format(self.patch_folder, schema_with_app)
            self.patch_spool_log = './{}.log'.format(schema_with_app)  # must start with ./ and ends with .log for proper function

            # generate patch header
            payload = '--\n'
            payload += '-- {:>16} | {}\n'.format('PATCH CODE', self.patch_code)
            payload += '-- {:>16} | {}\n'.format('SCHEMA', target_schema)
            if app_id:
                payload += '-- {:>16} | {}\n'.format('APP ID', app_id)
            payload += '--\n'

            # get differences in between first and last commits
            payload += self.get_differences(rel_files, target_schema)

            # create snapshot files
            self.create_snapshots(app_id)

            payload += 'SET DEFINE OFF\n'
            payload += 'SET TIMING OFF\n'
            payload += 'SET SQLBLANKLINES ON\n'
            payload += '--\n'
            payload += 'WHENEVER OSERROR EXIT ROLLBACK;\n'
            payload += 'WHENEVER SQLERROR EXIT ROLLBACK;\n'
            payload += '--\n'

            # spool output to the file
            if self.config.spooling:
                payload += 'SPOOL "{}" APPEND;\n\n'.format(self.patch_spool_log)

            # add properly sorted files (objects by dependencies) to the patch
            if app_id != '' and app_id in self.full_exports:
                # attach the whole application for full imports
                payload += 'SET SERVEROUTPUT OFF\n'
                payload += '--\n'
                payload += '-- APPLICATION {}\n'.format(app_id)
                payload += '--\n'
                payload += '@"./{}f{}/f{}.sql";\n'.format(self.config.path_apex, app_id, app_id)
                payload += 'SET SERVEROUTPUT ON\n'
            #
            else:
                if app_id != '':
                    payload += self.fix_apex_start(app_id)
                #
                apex_pages = []
                for file in self.dependencies_sorted():
                    # modify list of APEX files
                    if app_id != '':
                        try:
                            short_file = '/application/' + file.split('/application/')[1]
                        except:
                            short_file = ''

                        # move APEX pages to the end + create script to delete them in patch
                        search = re.search('/pages/page_(\d+)\.sql', file)
                        if search:
                            apex_pages.append(file)
                            continue

                        # ignore full APEX exports
                        if len(re.findall('/f\d+/f\d+\.sql$', file)) > 0:
                            continue

                        # skip file if it should be ignored in the patch (but keep it in snapshot folder)
                        if short_file in skip_apex_files:
                            continue

                    # attach file reference
                    payload += 'PROMPT --;\n'
                    payload += 'PROMPT -- FILE: {};\n'.format(file)
                    payload += 'PROMPT --;\n'
                    payload += self.config.patch_file_link.replace('{$FILE}', file) + '\n'
                    payload += 'PROMPT ;\n'

                # attach APEX pages to the end
                if len(apex_pages) > 0:
                    payload += self.fix_apex_pages(apex_pages)

                # for APEX patches add some queries
                if app_id != '':
                    payload += self.fix_apex_end(app_id)

            payload += '\n'

            # add grants
            payload += 'PROMPT --;\n'
            payload += 'PROMPT -- GRANTS;\n'
            payload += 'PROMPT --;\n'
            payload += self.get_grants_made()

            # add flag so deploy script can evaluate it as successful
            payload += 'PROMPT --;\n'
            payload += 'PROMPT -- SUCCESS;\n'
            payload += 'PROMPT --;\n'

            # spool output end
            if self.config.spooling:
                payload += 'SPOOL OFF;\n'

            # store payload in file
            self.create_patch_file(payload, target_schema)



    def get_differences(self, rel_files, target_schema):
        self.diffs      = {}    # cleanup
        payload         = ''
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

                # detect APEX application
                if self.config.path_apex in file and self.apex_app_id == '':
                    obj = self.get_file_object(file)
                    #
                    self.apex_app_id            = obj['apex_app_id']
                    self.config.apex_workspace  = obj['apex_workspace']

        # show commits only with relevant files
        payload += '-- COMMITS:\n'
        payload += '-- --------\n'
        for commit_number, commit in self.relevant_commits.items():
            files_found = False
            for file in commit.stats.files:
                if file in rel_files:
                    files_found = True
                    break
            #
            if files_found:
                payload += '--   {}) {}\n'.format(commit_number, commit.summary)

        # split files by the change type
        if len(new_files) > 0:
            payload += '--\n'
            payload += '-- NEW FILES:\n'
            payload += '-- ----------\n'
            for file in sorted(new_files):
                payload += '--   {}\n'.format(file)  # self.diffs[file].change_type
        #
        if len(deleted_files) > 0:
            payload += '--\n'
            payload += '-- DELETED FILES:\n'
            payload += '-- --------------\n'
            for file in sorted(deleted_files):
                payload += '--   {}\n'.format(file)  # self.diffs[file].change_type
        #
        if len(modifed_files) > 0:
            payload += '--\n'
            payload += '-- MODIFIED FILES:\n'
            payload += '-- ---------------\n'
            for file in sorted(modifed_files):
                payload += '--   {}\n'.format(file)  # self.diffs[file].change_type
        #
        payload += '--\n\n'
        #
        return payload



    def dependencies_sorted(self):
        files = self.diffs.keys()
        #
        # @TODO:
        #
        # follow the patch template + sort relevant files by dependencies
        return files



    def create_snapshots(self, app_id):
        # copy changed files
        process_files = list(self.diffs.keys())
        if len(self.diffs.keys()) > 0:
            for file in process_files:
                self.create_file_snapshot(file)

        # copy some files even if they did not changed
        if app_id != None and str(app_id) != '':
            path = '{}f{}/'.format(self.config.path_apex, app_id).replace('//', '/')
            for file in self.config.apex_files_copy:
                file = path + file
                if not (file in process_files) and os.path.exists(file):
                    # get copied files from directory
                    with open(file, 'rt') as f:
                        self.create_file_snapshot(file, file_content = f.read())


            # attach full export
            file = '{}f{}.sql'.format(path, app_id)
            self.create_file_snapshot(file)



    def create_patch_file(self, payload, target_schema):
        # save in schema patch file
        with open(self.patch_file, 'wt', encoding = 'utf-8', newline = '\n') as w:
            w.write(payload)
        #
        if self.apex_app_id != '':
            self.patch_files_apex.append(self.patch_file)
        else:
            self.patch_files.append(self.patch_file)



    def create_file_snapshot(self, file, file_content = None):
        # create folders and copy files
        target_file     = '{}/{}'.format(self.patch_folder, file).replace('//', '/')
        target_folder   = os.path.dirname(target_file)
        #
        if file_content == None:
            file_content = self.get_file_from_commit(file, commit = str(self.last_commit_obj))

        # change page audit columns
        if self.config.replace_audit and self.apex_app_id != '' and '/application/pages/page' in file:
            file_content = re.sub(r",p_last_updated_by=>'([^']+)'",         ",p_last_updated_by=>'{}'".format(self.patch_code), file_content)
            file_content = re.sub(r",p_last_upd_yyyymmddhh24miss=>'(\d+)'", ",p_last_upd_yyyymmddhh24miss=>'{}'".format(self.config.today_full_raw), file_content)

        # save file
        if not os.path.exists(target_folder):
            os.makedirs(target_folder)
        with open(target_file, 'wt', encoding = 'utf-8') as w:
            w.write(file_content)



    def fix_apex_start(self, app_id):
        util.assert_(app_id,                        'MISSING ARGUMENT: APEX APP')
        util.assert_(self.config.apex_workspace,    'MISSING ARGUMENT: APEX WORKSPACE')
        payload = ''

        # set proper workspace
        payload += self.replace_tags(query.query_apex_version, ignore_missing = False) + '\n'

        # start APEX import
        payload += 'SET DEFINE OFF\n'
        payload += 'SET TIMING OFF\n'
        payload += '--\n'

        # attach the whole application for full imports
        payload += 'PROMPT --;\n'
        payload += 'PROMPT -- APEX FULL EXPORT\n'
        payload += 'PROMPT --;\n'
        payload += '--@"./{}f{}/f{}.sql";\n'.format(self.config.path_apex, app_id, app_id)

        # attach starting file
        payload += 'PROMPT --;\n'
        payload += 'PROMPT -- APEX COMPONENTS\n'
        payload += 'PROMPT --;\n'
        payload += '@"./{}f{}/{}";\n'.format(self.config.path_apex, app_id, 'application/set_environment.sql')
        payload += '--\n'
        #
        return payload



    def fix_apex_end(self, app_id):
        payload = '--\n'

        # attach ending file
        if not (app_id in self.full_exports):
            file = '{}f{}/{}'.format(self.config.path_apex, app_id, 'application/end_environment.sql')
            payload += '@"./{}";\n'.format(file.replace(self.repo_root, '').lstrip('/'))
        #
        return payload



    def fix_apex_pages(self, apex_pages):
        payload = '\n'
        payload += 'PROMPT --;\n'
        payload += 'PROMPT -- APEX PAGES\n'
        payload += 'PROMPT --;\n'
        payload += 'BEGIN\n'
        #
        for file in apex_pages:
            search = re.search('/pages/page_(\d+)\.sql', file)
            if search:
                page_id = int(search.group(1))
                payload += '    wwv_flow_imp_page.remove_page(p_flow_id => wwv_flow.g_flow_id, p_page_id => {});\n'.format(page_id)
        payload += 'END;\n'
        payload += '/\n'

        # recreate requested pages
        payload += '--\n'
        for file in apex_pages:
            payload += self.config.patch_file_link.replace('{$FILE}', file) + '\n'
        #
        return payload



    def get_grants_made(self):
        payload         = ''
        grants_found    = False

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
                    object_name = self.get_file_object_name(file).lower()
                    if object_name == find_name:
                        payload += line
                        grants_found = True
                        break
        #
        if grants_found:
            payload += '\n'
        #
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





    #
    # class File
    #

    def get_file_object_type(self, file):
        return ''



    def get_file_object_name(self, file):
        return os.path.basename(file).split('.')[0]



    def get_file_object(self, file):
        file = file.replace('\\', '/').replace('//', '/')
        #
        find_app    = re.search('/f(\d+)/', file)
        find_page   = re.search('/f\d+/application/pages/page_(\d+)\.sql$', file)
        app_id      = int(find_app.group(1))  if find_app  else None
        page_id     = int(find_page.group(1)) if find_page else None
        #
        return {
            'file'              : file,
            'object_type'       : self.get_file_object_type(file),
            'object_name'       : self.get_file_object_name(file),
            'schema'            : self.info.schema if not app_id else self.config.apex_schema,
            'apex_app_id'       : app_id,
            'apex_page_id'      : page_id,
            'apex_workspace'    : self.config.apex_workspace,
            #'patch_file'  : '',
            #'group'       : '',  subfolders
            #'shortcut'    : '',
            #'hash_old'    : '',
            #'hash_new'    : ''
        }



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
    parser.add_argument('-full',        help = 'Specify APEX app(s) where to use full export ',                 default = [],   nargs = '*')
    #
    Patch(parser)

