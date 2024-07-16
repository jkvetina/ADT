# coding: utf-8
import sys, os, re, argparse, datetime
#
import config
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

class Search_Repo(config.Config):

    def __init__(self, args = None):
        self.parser = argparse.ArgumentParser(add_help = False)
        #
        group = self.parser.add_argument_group('MAIN ACTIONS')
        group.add_argument('-commit',       help = 'Search for specific commit number(s)',      type = int,             nargs = '*', default = [])
        group.add_argument('-hash',         help = 'Search for specific commit hash(es)',                               nargs = '*', default = [])
        group.add_argument('-summary',      help = 'Search summary for provided word(s)',                               nargs = '*', default = [])
        group.add_argument('-file',         help = 'Search for specific file name',                                     nargs = '*', default = [])
        #
        group = self.parser.add_argument_group('LIMIT SCOPE')
        group.add_argument('-recent',       help = 'Limit scope to # of recent days',           type = int,             nargs = '?')
        group.add_argument('-branch',       help = 'Limit scope to specific branch',                                    nargs = '?')
        group.add_argument('-type',         help = 'Object type (you can use LIKE syntax)',                             nargs = '?')
        group.add_argument('-name',         help = 'Object name/prefix (you can use LIKE syntax)',                      nargs = '?')
        group.add_argument('-my',           help = 'Show only my commits',                                              nargs = '?', const = True,  default = False)
        #
        group = self.parser.add_argument_group('EXTRA ACTIONS')
        group.add_argument('-restore',      help = 'Restore specific version(s) of file',       type = int,             nargs = '*')

        super().__init__(parser = self.parser, args = args)

        # setup env and paths
        self.init_config()

        self.info.branch        = self.args.branch or self.config.repo_branch or self.info.branch or str(self.repo.active_branch)
        self.commits_file       = self.config.repo_commits_file.replace('#BRANCH#', self.info.branch)
        self.all_commits        = {}
        self.all_files          = {}
        self.old_date           = None
        self.relevant_files     = {}

        # to limit dates
        if self.args.recent != None:
            self.old_date = datetime.datetime.now().date() - datetime.timedelta(days = self.args.recent)

        # get all commits
        if not os.path.exists(self.commits_file):
            util.raise_error('COMMIT FILE MISSING',
                self.commits_file,
                'run: adt patch -rebuild'
            )
        #
        with open(self.commits_file, 'rt', encoding = 'utf-8') as f:
            self.all_commits = dict(util.get_yaml(f, self.commits_file))

        # also store commits with files as keys
        for commit_id in sorted(self.all_commits.keys()):
            obj = self.all_commits[commit_id]
            for file in obj['files']:
                if not (file in self.all_files):
                    self.all_files[file] = []
                self.all_files[file].append(commit_id)

        # go from newest to oldest
        for commit_num in sorted(self.all_commits.keys(), reverse = True):
            commit_obj = self.all_commits[commit_num]
            if self.old_date and self.old_date >= commit_obj['date'].date():    # limit searching by date
                break

            # search for specific commits
            if self.args.commit and not (commit_num in self.args.commit):
                continue

            # limit just to my commits
            if self.args.my and self.repo_user_mail != commit_obj['author']:
                continue

            # search for all words
            found_all = True
            for word in self.args.summary:
                if not (word.upper() in commit_obj['summary'].upper()):
                    found_all = False
                    break
            #
            if not found_all:
                continue

            # show commit details
            found_files     = []
            deleted_files   = []
            #
            for file in commit_obj['files']:
                # check object type and object name
                short   = file.replace(self.repo_root, '')
                obj     = self.repo_files.get(short) or File(file, config = self.config)

                # process just database objects
                if (not obj.is_object or not (file.startswith(self.config.path_objects))):
                    continue

                # limit requested object type and name
                if self.args.type and not (self.args.type in obj['object_type']):
                    continue
                if self.args.name and not (self.args.name in obj['object_name']):
                    continue

                # filename checks
                found_all = True
                if self.args.file:
                    for word in self.args.file:
                        if not (word.lower() in file.lower()):
                            found_all = False
                            break
                if found_all:
                    found_files.append(file)
                    if file in commit_obj['deleted']:
                        deleted_files.append(file)
                    #
                    if not (file in self.relevant_files):
                        self.relevant_files[file] = []
                    self.relevant_files[file].append(commit_num)

            # show findings to user
            if found_files:
                print('\n{}) {}'.format(commit_num, commit_obj['summary']))
                util.print_dots(' ' * (len(str(commit_num)) + 2) + commit_obj['author'], right = str(commit_obj['date'])[0:16])
                print()
                #
                groups = {}
                for file in found_files:
                    obj         = File(file, config = self.config)
                    obj_type    = obj.get('object_type') or ''
                    obj_name    = obj.get('object_name') or ''
                    #
                    if obj_name:
                        if not (obj_type in groups):
                            groups[obj_type] = {}
                        groups[obj_type][obj_name] = file
                #
                for obj_type in self.config.object_types.keys():
                    if obj_type in groups:
                        for i, obj_name in enumerate(sorted(groups[obj_type].keys())):
                            flag = '  [DELETED]' if groups[obj_type][obj_name] in deleted_files else ''
                            print('  {:>16} | {}{}'.format(obj_type if i == 0 else '', obj_name, flag))
                print()

        # restore matching files to requested (or all) past versions
        if self.args.restore != None:
            util.print_header('RESTORED FILES:')
            #
            for file in sorted(self.relevant_files.keys()):
                versions = list(sorted(self.args.restore or self.all_files[file], reverse = True))
                #
                print('  - {}'.format(file.replace(self.repo_root, '')))

                # restore file close to the original file, restore just relevant commits
                for ver in versions:
                    if ver in self.relevant_files[file]:
                        base, ext   = os.path.splitext(file)
                        ver_file    = '{}.{}{}'.format(base, ver, ext)
                        payload     = self.get_file_from_commit(file, commit = ver)
                        #
                        util.write_file(ver_file, payload)
            #
            print()



    def get_file_from_commit(self, file, commit):
        # convert commit_id (number) to commit hash
        if isinstance(commit, int):
            commit = self.all_commits[commit]['id']

        # run command line and capture the output, text file is expected
        return util.run_command('git show {}:{}'.format(commit, file))



if __name__ == "__main__":
    Search_Repo()

