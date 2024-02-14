# coding: utf-8
import sys, os, re, shutil, datetime, argparse, collections
from git import Repo

def replace_dict(text, translation):
    regex = re.compile('|'.join(map(re.escape, translation)))
    return regex.sub(lambda match: translation[match.group(0)], text)



#
# [_] store the schema somewhere during export - in the path or in schema.log or config !!!
# [_] follow the patch template + sort relevant files by dependencies
# [_] zip this if we are doing deployment over REST
# [_] SPOOL on deployment into patch/.../YY-MM-DD.. .log
# [_] ADD KEEP SESSIONS ALIVE, APEX_APPLICATION_ADMIN
# [_] CHECK MORE ISSUES WITH ARGS + SHOW BETTER MESSAGE, def raise_error(''): + exit
#



#
# ARGS
#
parser = argparse.ArgumentParser()
parser.add_argument('-p', '-patch',     '--patch',      help = 'Patch code (name for the patch files)')
parser.add_argument('-s', '-search',    '--search',     help = 'Search string for Git to search just for relevant commits',     default = None, nargs = '*')
parser.add_argument('-c', '-commit',    '--commit',     help = 'Process just specific commits',                                 default = None, nargs = '*')
parser.add_argument('-b', '-branch',    '--branch',     help = 'To override active branch',                                     default = None)
#parser.add_argument('-u', '-update',    '--update',     help = '',                   default = False,  nargs = '?',  const = True)
#
args = vars(parser.parse_args())
args = collections.namedtuple('ARG', args.keys())(*args.values())  # convert to named tuple

#print('ARGS:')
#print('-----')
#for key, value in sorted(zip(args._fields, args)):
#    print('{:>10} = {}'.format(key, value))
#print()

assert args.patch is not None

query_apex_version = """
BEGIN
    APEX_UTIL.SET_WORKSPACE (
        p_workspace         => '{$APEX_WORKSPACE}'
    );
    APEX_APPLICATION_ADMIN.SET_APPLICATION_VERSION (
        p_application_id    => {$APEX_APP_ID},
        p_version           => '{$APEX_VERSION}'
    );
    COMMIT;
END;
/
"""



class Patch:

    def __init__(self, config):
        self.config     = config
        self.repo_path  = config['repo_path']

        # make sure we have a valid repo
        self.open_repo()



    def open_repo(self):
        self.repo       = Repo(self.repo_path)
        self.repo_url   = self.repo.remotes[0].url

        # check that the repository loaded correctly
        assert not self.repo.bare

        # get current account
        with self.repo.config_reader() as git_config:
            self.user_name  = git_config.get_value('user', 'name')
            self.user_mail  = git_config.get_value('user', 'email')

        # show to the user
        print('ACCOUNT  : {}, {}'.format(self.user_name, self.user_mail))
        print('REPO     : {}'.format(self.repo_path))
        print('URL      : {}'.format(self.repo_url))
        #print('BRANCH   : {}'.format(self.branch))
        print()

        #print(self.repo.git.status)
        #print()

        # check changes
        if self.repo.is_dirty(untracked_files = True):
            print('CHANGES DETECTED!')
            print()

            index = self.repo.index

            #print('Untracked files', self.repo.untracked_files)

            #print('Staged files:')
            #for item in self.repo.index.diff('HEAD'):
            #    print(item.a_path)

            #for obj in index.diff(None):
            #    print('  {} | {}'.format(obj.change_type, obj.b_path))  # obj.deleted_file
            #print()
            #print()



    def fetch_changes(self):
        self.repo.git.checkout()
        self.repo.git.pull()



    def create_patch(self, patch_code, search_message = None, commits = None, branch = None):
        self.patch_files        = []
        self.patch_files_apex   = []
        self.patch_code         = patch_code
        self.search_message     = search_message or [patch_code]
        self.commits            = commits
        self.branch             = branch or self.repo.active_branch                     # get current branch
        self.today              = datetime.datetime.today().strftime('%Y-%m-%d')        # YYYY-MM-DD
        self.today_full         = datetime.datetime.today().strftime('%Y-%m-%d %H:%M')  # YYYY-MM-DD HH24:MI
        self.file_template      = '@@"../patch/{}/#FILE#"\n'.format(self.patch_code)

        # pull some variables from config
        self.path_objects       = self.config['path_objects']
        self.path_apex          = self.config['path_apex']

        # track changes
        self.all_commits        = {}
        self.relevant_commits   = {}
        self.relevant_files     = {}
        self.relevant_objects   = {}

        # APEX related
        self.apex_root          = '../' + self.path_apex.rstrip('/')
        self.apex_app_id        = ''
        self.apex_workspace     = ''
        self.apex_version       = '{} {}'.format(self.today, self.patch_code)

        # set current commit to the head and search through recent commits
        self.current_commit_obj = self.repo.commit('HEAD')
        self.current_commit     = self.current_commit_obj.count()

        # workflow
        self.find_commits()
        self.create_patches()
        self.create_summary()



    def find_commits(self):
        for commit in list(self.repo.iter_commits(self.branch, max_count = self.config['git_depth'], skip = 0)):
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
        # process files per schema
        for target_schema, rel_files in self.relevant_files.items():
            self.apex_app_id = ''

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
            # create snapshot folder
            self.patch_folder = '{}/patch/{$PATCH_CODE}'  # /snapshot/ ??
            self.patch_folder = self.patch_folder.replace('{$PATCH_CODE}', self.patch_code)
            self.patch_folder = self.patch_folder.format(self.repo_path)
            #
            if not os.path.exists(self.patch_folder):
                os.makedirs(self.patch_folder)

            # copy files
            for file in diffs.keys():
                source_file     = '{}/{}'.format(self.repo_path, file).replace('//', '/')
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
                    file_content = re.sub(r",p_last_upd_yyyymmddhh24miss=>'(\d+)'", ",p_last_upd_yyyymmddhh24miss=>'{}00'".format(self.today_full.replace('-', '').replace(' ', '').replace(':', '')), file_content)
                    #
                    with open(target_file, 'wt', encoding = 'utf-8') as f:
                        f.write(file_content)



    def create_patch_file(self, payload, target_schema):
        # prepare list of commits and attach it to patch filename for quick/additional patches
        commits_list = ''
        if self.commits != None:
            commits_list = '_{}'.format(max(self.commits))

        # save in schema patch file
        patch_file = replace_dict('{}/patch/{$PATCH_CODE}/{$INFO_SCHEMA}{}.sql', {
            '{$PATCH_CODE}'     : self.patch_code,
            '{$INFO_SCHEMA}'    : target_schema,
        }
        ).format(self.repo_path, commits_list)
        #
        with open(patch_file, 'w', encoding = 'utf-8', newline = '\n') as w:
            w.write(payload)
        #
        if self.apex_app_id != '':
            self.patch_files_apex.append(patch_file)
        else:
            self.patch_files.append(patch_file)



    def create_summary(self):
        # create overall patch file
        patch_file = '{}/patch/{$PATCH_CODE}.sql'
        patch_file = patch_file.replace('{$PATCH_CODE}', self.patch_code)
        patch_file = patch_file.format(self.repo_path)
        #
        payload = ''
        payload += '--\n-- EXECUTE PATCH FILES\n--\n'

        # non APEX schemas first
        for file in sorted(self.patch_files):
            payload += '@@"./{}"\n'.format(file.replace(self.repo_path, '').lstrip('/'))
        for file in sorted(self.patch_files_apex):
            payload += '@@"./{}"\n'.format(file.replace(self.repo_path, '').lstrip('/'))
        payload += '\n'
        #
        with open(patch_file, 'w', encoding = 'utf-8', newline = '\n') as w:
            w.write(payload)
        #
        print(payload)



    def fix_apex_start(self):
        assert self.apex_app_id != ''
        assert self.apex_workspace is not None

        # set proper workspace
        payload = ''
        payload += replace_dict(query_apex_version, {
            '{$APEX_WORKSPACE}' : self.apex_workspace,
            '{$APEX_APP_ID}'    : str(self.apex_app_id),
            '{$APEX_VERSION}'   : self.apex_version,
        }
        ).lstrip() + '\n'

        # start APEX import
        payload += 'SET DEFINE OFF\n'
        payload += 'SET TIMING OFF\n'
        payload += '--\n'
        payload += '@@"{}/f{}/application/set_environment.sql"\n'.format(self.apex_root, self.apex_app_id)
        payload += '--@@"{}/f{}/f{}.sql"\n'.format(self.apex_root, self.apex_app_id, self.apex_app_id)
        payload += '--\n'
        #
        return payload



    def fix_apex_end(self):
        payload = ''
        payload += '--\n@@"{}/f{}/application/end_environment.sql"\n'.format(self.apex_root, self.apex_app_id)
        #
        return payload



    def fix_apex_pages(self, apex_pages):
        payload = ''
        payload += '--\nBEGIN\n'
        for file in apex_pages:
            page_id = int(re.search('/pages/page_(\d+)\.sql', file).group(1))
            #
            payload += '    wwv_flow_imp_page.remove_page(p_flow_id => wwv_flow.g_flow_id, p_page_id => {});\n'.format(page_id)
        payload += 'END;\n'
        payload += '/\n'

        # recreate pages
        payload += '--\n'
        for file in apex_pages:
            payload += self.file_template.replace('#FILE#', file)
        #
        return payload



    def get_grants_made(self, diffs):
        payload = ''

        # grab the file with grants made
        grants_made     = '{}{}grants/{}.sql'.format(config['repo_path'], config['path_objects'], self.config['schema'])
        grants_found    = False
        #
        with open(grants_made, 'rt', encoding = 'utf-8') as f:
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
            'schema'            : self.config['schema'] if not app_id else self.config['apex_schema'],
            'apex_app_id'       : app_id,
            'apex_page_id'      : page_id,
            'apex_workspace'    : self.config['apex_workspace'],
            #'patch_file'  : '',
            #'group'       : '',  subfolders
            #'shortcut'    : '',
            #'hash_old'    : '',
            #'hash_new'    : ''
        }





if __name__ == "__main__":
    config = {
        'repo_path'         : '',
        'branch'            : args.branch,
        'schema'            : '',
        'apex_schema'       : '',
        'apex_workspace'    : '',
        'path_objects'      : '',
        'path_apex'         : '',
        'git_depth'         : 500,
    }

    # search just for specific commits
    patch = Patch(config = config)
    patch.create_patch(patch_code = args.patch, search_message = args.search, commits = args.commit, branch = args.branch)

