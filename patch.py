# coding: utf-8
import sys, os, re, shutil, argparse
import config
from lib import queries_patch as queries        # ditch for template folder

class Patch(config.Config):

    def __init__(self, parser):
        super().__init__(parser)

        assert self.args.patch is not None

        # make sure we have a valid repo
        self.open_repo()
        self.create_patch()



    def open_repo(self):
        # check that the repository loaded correctly
        assert not self.repo.bare

        # get current account
        with self.repo.config_reader() as git_config:
            self.user_name  = git_config.get_value('user', 'name')
            self.user_mail  = git_config.get_value('user', 'email')



    def fetch_changes(self):
        self.repo.git.checkout()
        self.repo.git.pull()



    def create_patch(self):
        self.patch_files        = []
        self.patch_files_apex   = []
        self.patch_code         = self.args.patch
        self.patch_file         = '{}/patch/{}.sql'.format(self.info_repo, self.patch_code)
        self.patch_file_curr    = ''
        self.search_message     = self.args.search or [self.patch_code]
        self.commits            = self.args.commit
        self.info_branch        = self.args.branch or self.info_branch or self.repo.active_branch
        self.file_template      = '@"./#FILE#"\n'.format(self.patch_code)
        self.grants_made        = '{}{}grants/{}.sql'.format(self.info_repo, self.path_objects, self.info_schema)
        self.spooling           = True

        # pull some variables from config
        self.path_objects       = self.path_objects
        self.path_apex          = self.path_apex

        # track changes
        self.all_commits        = {}
        self.relevant_commits   = {}
        self.relevant_files     = {}
        self.relevant_objects   = {}

        # APEX related
        self.apex_app_id        = ''
        self.apex_workspace     = ''
        self.apex_version       = '{} {}'.format(self.today, self.patch_code)
        self.apex_files_ignore  = [ # these files will not be in the patch even if they change
                                    'application/set_environment.sql',
                                    'application/end_environment.sql',
                                    'application/create_application.sql',
                                    'application/delete_application.sql',
        ]
        self.apex_files_copy    = [ # these files will always be copied to the snapshot folder
                                    'application/set_environment.sql',
                                    'application/end_environment.sql',
        ]

        # set current commit to the head and search through recent commits
        self.current_commit_obj = self.repo.commit('HEAD')
        self.current_commit     = self.current_commit_obj.count()

        print('--\n-- PATCH {}\n--\n'.format(self.patch_code))

        # workflow
        self.find_commits()
        self.create_patches()
        self.create_summary()



    def find_commits(self):
        for commit in list(self.repo.iter_commits(self.info_branch, max_count = self.repo_commits, skip = 0)):
            self.all_commits[commit.count()] = commit

            # skip non requested commits
            if self.commits != None:
                if not (str(commit) in self.commits) and not (str(commit.count()) in self.commits):
                    continue

            # skip non relevant commits
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
            files_found = []
            for file in commit.stats.files.keys():
                # process just the listed extensions (in the config)
                if os.path.splitext(file)[1] != '.sql':
                    continue

                # process just database and APEX exports
                if not (file.startswith(self.path_objects)) and not (file.startswith(self.path_apex)):
                    continue

                # get info about the file
                self.relevant_objects[file] = self.get_file_object(file)
                schema = self.relevant_objects[file]['schema']
                #
                if not (schema in self.relevant_files):
                    self.relevant_files[schema] = []
                self.relevant_files[schema].append(file)
                #
                files_found.append(file)

            # show commits and files
            if len(files_found) > 0:
                print('{}) {}'.format(commit.count(), commit.summary))  # commit.author.email, commit.authored_datetime
                for file in files_found:
                    print('  {}'.format(file))
                print()

        # check number of commits
        found_commits = self.relevant_commits.keys()
        if len(found_commits) == 0:
            print('No commits found!\n\n')
            return

        # get last version (max) and version before first change (min)
        self.first_commit       = min(self.relevant_commits) - 1
        self.first_commit_obj   = self.all_commits[self.first_commit]
        self.last_commit        = max(self.relevant_commits)
        self.last_commit_obj    = self.all_commits[self.last_commit]



    def create_patches(self):
        # simplify searching for ignored files
        skip_apex_files = ';'.join(self.apex_files_ignore)

        # process files per schema
        for target_schema, rel_files in self.relevant_files.items():
            self.apex_app_id = ''

            # prepare list of commits and attach it to patch filename for quick/additional patches
            commits_list = ''
            if self.commits != None:
                commits_list = '_{}'.format(max(self.commits))

            # generate patch file name for specific schema
            self.patch_file_curr = '{}patch/{}/{}{}.sql'.format(self.info_repo, self.patch_code, target_schema, commits_list)

            # generate patch header
            header = 'PATCH - {} - {}'.format(self.patch_code, target_schema)
            payload = ''
            payload += '--\n-- {}\n-- {}\n--'.format(header, '-' * len(header))

            # get differences in between first and last commits
            diffs           = {}
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
                if file in rel_files and not (file in diffs):
                    diffs[file] = diff
                    if diff.new_file:
                        new_files.append(file)
                    elif diff.deleted_file:
                        deleted_files.append(file)
                    else:
                        modifed_files.append(file)

                    # detect APEX application
                    if self.path_apex in file and self.apex_app_id == '':
                        obj = self.get_file_object(file)
                        #
                        self.apex_app_id    = obj['apex_app_id']
                        self.apex_workspace = obj['apex_workspace']

            # create snapshot files
            self.create_snapshots(diffs, target_schema)

            # show commits only with relevant files
            payload += '\n-- COMMITS:\n'
            for _, commit in self.relevant_commits.items():
                files_found = False
                for file in commit.stats.files:
                    if file in rel_files:
                        files_found = True
                        break
                #
                if files_found:
                    payload += '--   {}\n'.format(commit.summary)

            # split files by the change type
            if len(new_files) > 0:
                payload += '--\n-- NEW FILES:\n'
                for file in sorted(new_files):
                    payload += '--   {}\n'.format(file)  # diffs[file].change_type
            #
            if len(deleted_files) > 0:
                payload += '--\n-- DELETED FILES:\n'
                for file in sorted(deleted_files):
                    payload += '--   {}\n'.format(file)  # diffs[file].change_type
            #
            if len(modifed_files) > 0:
                payload += '--\n-- MODIFIED FILES:\n'
                for file in sorted(modifed_files):
                    payload += '--   {}\n'.format(file)  # diffs[file].change_type
            #
            payload += '--\n\n'

            # for APEX patches add some queries
            if self.apex_app_id != '':
                payload += self.fix_apex_start()

            # add properly sorted files (objects by dependencies) to the patch
            apex_pages = []
            for file in self.dependencies_sorted(diffs.keys()):
                if self.apex_app_id != '':
                    # move APEX pages to the end + create script to delete them in patch
                    if '/application/pages/page' in file:
                        apex_pages.append(file)
                        continue

                    # ignore full APEX exports
                    if len(re.findall('/f\d+/f\d+\.sql$', file)) > 0:
                        continue

                    # skip file if it should be ignored in the patch (but keep it in snapshot folder)
                    if file in skip_apex_files:
                        continue
                #
                payload += self.file_template.replace('#FILE#', file)

            # for APEX patches add some queries
            if self.apex_app_id != '':
                # attach APEX pages to the end
                if len(apex_pages) > 0:
                    payload += self.fix_apex_pages(apex_pages)
                #
                payload += self.fix_apex_end()
            #
            payload += '\n'

            # add grants for non APEX schemas
            if self.apex_app_id == '':
                payload += self.get_grants_made(diffs)

            # store payload in file
            self.create_patch_file(payload, target_schema)



    def dependencies_sorted(self, files):
        #
        # @TODO:
        #
        # follow the patch template + sort relevant files by dependencies
        return files



    def create_snapshots(self, diffs, target_schema):
        if len(diffs.keys()) > 0:
            process_files = diffs.keys()

            # create snapshot folder
            self.patch_folder = '{}/patch/{$PATCH_CODE}'  # /snapshot/ ??
            self.patch_folder = self.patch_folder.replace('{$PATCH_CODE}', self.patch_code)
            self.patch_folder = self.patch_folder.format(self.info_repo)
            #
            if not os.path.exists(self.patch_folder):
                os.makedirs(self.patch_folder)

            # copy some files even if they did not changed
            if self.apex_app_id != '':
                for file in self.apex_files_copy:
                    file = '{}f{}/{}'.format(self.path_apex, self.apex_app_id, file)
                    if file not in process_files:
                        self.create_file_snapshot(file)

            # copy changed files
            for file in process_files:
                self.create_file_snapshot(file)



    def create_patch_file(self, payload, target_schema):
        # save in schema patch file
        with open(self.patch_file_curr, 'wt', encoding = 'utf-8', newline = '\n') as w:
            w.write(payload)
        #
        if self.apex_app_id != '':
            self.patch_files_apex.append(self.patch_file_curr)
        else:
            self.patch_files.append(self.patch_file_curr)



    def create_file_snapshot(self, file):
        # create folders and copy files
        source_file     = '{}/{}'.format(self.info_repo, file).replace('//', '/')
        target_file     = '{}/{}'.format(self.patch_folder, file).replace('//', '/')
        target_folder   = os.path.dirname(target_file)
        #
        if not os.path.exists(target_folder):
            os.makedirs(target_folder)
        shutil.copy2(source_file, target_file)

        # change page audit columns
        if self.apex_app_id != '' and '/application/pages/page' in file:
            file_content = ''
            with open(target_file, 'rt', encoding = 'utf-8') as f:
                file_content = f.read()
            #
            file_content = re.sub(r",p_last_updated_by=>'([^']+)'", ",p_last_updated_by=>'{}'".format(self.patch_code), file_content)
            file_content = re.sub(r",p_last_upd_yyyymmddhh24miss=>'(\d+)'", ",p_last_upd_yyyymmddhh24miss=>'{}'".format(self.today_full_raw), file_content)
            #
            with open(target_file, 'wt', encoding = 'utf-8') as f:
                f.write(file_content)



    def create_summary(self):
        # create overall patch file
        payload = '--\n-- EXECUTE PATCH FILES\n--\n\n'

        # non APEX schemas first
        proceed = False
        for file in sorted(self.patch_files):
            payload += '@"./{}"\n'.format(file.replace(self.info_repo, '').lstrip('/'))
            proceed = True
        #
        for file in sorted(self.patch_files_apex):
            payload += '@"./{}"\n'.format(file.replace(self.info_repo, '').lstrip('/'))
            proceed = True
        payload += '\n'
        #
        if proceed:
            with open(self.patch_file, 'w', encoding = 'utf-8', newline = '\n') as w:
                w.write(payload)
            #
            print(payload)



    def fix_apex_start(self):
        assert self.apex_app_id != ''
        assert self.apex_workspace is not None

        # set proper workspace
        payload = self.replace_tags(queries.query_apex_version, self).strip() + '\n'

        # start APEX import
        payload += 'SET DEFINE OFF\n'
        payload += 'SET TIMING OFF\n'
        payload += 'WHENEVER SQLERROR EXIT ROLLBACK\n'
        payload += '--\n'

        # attach starting file
        payload += '@"./{}f{}/{}"\n'.format(self.path_apex, self.apex_app_id, 'application/set_environment.sql')

        # attach the whole application for full imports
        payload += '--@"./{}f{}.sql"\n'.format(self.path_apex, self.apex_app_id)
        payload += '--\n'
        #
        return payload



    def fix_apex_end(self):
        payload = '--\n'

        # attach ending file
        file = '{}f{}/{}'.format(self.path_apex, self.apex_app_id, 'application/end_environment.sql')
        payload += '@"./{}"\n'.format(file.replace(self.info_repo, '').lstrip('/'))
        #
        return payload



    def fix_apex_pages(self, apex_pages):
        payload = '--\nBEGIN\n'
        for file in apex_pages:
            page_id = int(re.search('/pages/page_(\d+)\.sql', file).group(1))
            #
            payload += '    wwv_flow_imp_page.remove_page(p_flow_id => wwv_flow.g_flow_id, p_page_id => {});\n'.format(page_id)
        payload += 'END;\n'
        payload += '/\n'

        # recreate requested pages
        payload += '--\n'
        for file in apex_pages:
            payload += self.file_template.replace('#FILE#', file)
        #
        return payload



    def get_grants_made(self, diffs):
        payload         = ''
        grants_found    = False

        # grab the file with grants made
        with open(self.grants_made, 'rt', encoding = 'utf-8') as f:
            file_content = f.readlines()
            for line in file_content:
                if line.startswith('--'):
                    continue

                # find match on object name
                find_name = re.search('\sON\s+(.*)\s+TO\s', line)
                if find_name:
                    find_name = find_name.group(1).lower()
                #
                for file in diffs:
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
            'schema'            : self.info_schema if not app_id else self.apex_schema,
            'apex_app_id'       : app_id,
            'apex_page_id'      : page_id,
            'apex_workspace'    : self.apex_workspace,
            #'patch_file'  : '',
            #'group'       : '',  subfolders
            #'shortcut'    : '',
            #'hash_old'    : '',
            #'hash_new'    : ''
        }



if __name__ == "__main__":
    # parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-p',   '-patch',       '--patch',      help = 'Patch code (name for the patch files)')
    parser.add_argument('-s',   '-search',      '--search',     help = 'Search string for Git to search just for relevant commits',     default = None, nargs = '*')
    parser.add_argument('-c',   '-commit',      '--commit',     help = 'Process just specific commits',                                 default = None, nargs = '*')
    parser.add_argument('-b',   '-branch',      '--branch',     help = 'To override active branch',                                     default = None)
    #
    patch = Patch(parser)

