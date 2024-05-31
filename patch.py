# coding: utf-8
import sys, os, re, argparse, datetime
#
import config
from lib            import queries_patch as query
from lib            import util
from lib.file       import File
from export_apex    import Export_APEX
from recompile      import Recompile

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

    def __init__(self, args = None):
        self.parser = argparse.ArgumentParser(add_help = False)

        # actions and flags
        group = self.parser.add_argument_group('MAIN ACTIONS')
        group.add_argument('-patch',        help = 'Patch code (name for the patch files)',                             nargs = '?')
        group.add_argument('-ref',          help = 'Patch reference (the number from screen)',  type = int,             nargs = '?')
        group.add_argument('-create',       help = 'To create patch with or without sequence',  type = util.is_boolstr, nargs = '?', const = True,  default = False)
        group.add_argument('-deploy',       help = 'Deploy created patch right away',           type = util.is_boolstr, nargs = '?', const = True,  default = False)
        group.add_argument('-force',        help = 'Force (re)deployment',                                              nargs = '?', const = True,  default = False)
        group.add_argument('-continue',     help = 'Rollback or continue on DB error',                                  nargs = '?', const = True,  default = False)
        #
        group = self.parser.add_argument_group('SUPPORTING ACTIONS')
        group.add_argument('-archive',      help = 'To archive patches with specific ref #',    type = int,             nargs = '*',                default = [])
        group.add_argument('-install',      help = 'Create install file',                                               nargs = '?', const = True,  default = False)
        group.add_argument('-moveup',       help = 'Move driving patch files higher',                                   nargs = '?', const = True,  default = False)
        group.add_argument('-refresh',      help = 'Refresh used objects and APEX components',                          nargs = '?', const = True,  default = False)
        #
        group = self.parser.add_argument_group('SPECIFY ENVIRONMENT DETAILS')
        group.add_argument('-target',       help = 'Target environment',                                                nargs = '?')
        group.add_argument('-branch',       help = 'To override active branch',                                         nargs = '?',                default = None)
        group.add_argument('-key',          help = 'Key or key location for passwords',                                 nargs = '?')
        #
        group = self.parser.add_argument_group('LIMIT SCOPE')
        group.add_argument('-my',           help = 'Show only my commits',                                              nargs = '?', const = True,  default = False)
        group.add_argument('-commits',      help = 'To show number of recent commits',          type = int,             nargs = '?',                default = 0)
        group.add_argument('-patches',      help = 'To show number of recent patches',          type = int,             nargs = '?',                default = 0)
        group.add_argument('-search',       help = 'Search commits summary for provided words',                         nargs = '*',                default = None)
        group.add_argument('-commit',       help = 'Process just specific commits',                                     nargs = '*',                default = [])
        group.add_argument('-ignore',       help = 'Ignore specific commits',                                           nargs = '*',                default = [])
        group.add_argument('-full',         help = 'Specify APEX app(s) where to use full export',                      nargs = '*',                default = [])
        group.add_argument('-local',        help = 'Use local files and not files from Git',                            nargs = '?', const = True,  default = False)
        group.add_argument('-head',         help = 'Use file version from head commit',                                 nargs = '?', const = True,  default = False)
        #
        group = self.parser.add_argument_group('ADDITIONAL ACTIONS')
        group.add_argument('-hash',         help = 'Store file hashes on patch -create',        type = util.is_boolint, nargs = '?', const = True,  default = False)
        group.add_argument('-fetch',        help = 'Fetch Git changes before patching',                                 nargs = '?', const = True,  default = False)
        group.add_argument('-rebuild',      help = 'Rebuild temp files',                                                nargs = '?', const = True,  default = False)
        group.add_argument('-implode',      help = 'Merge files in a folder',                                           nargs = '?')
        group.add_argument('-deldiff',      help = 'Delete diff tables',                                                nargs = '?', const = True,  default = False)

        super().__init__(self.parser, args)

        # process arguments and reinitiate config
        if not (self.args.install or self.args.rebuild or self.args.implode):
            util.assert_(self.args.target, 'MISSING ARGUMENT: TARGET ENV')
        #
        self.patch_code         = self.args.patch
        self.patch_seq          = self.args.create
        self.search_message     = self.args.search or [self.patch_code]
        self.info.branch        = self.args.branch or self.config.repo_branch or self.info.branch or str(self.repo.active_branch)
        self.add_commits        = util.ranged_str(self.args.commit)
        self.ignore_commits     = util.ranged_str(self.args.ignore)
        self.full_exports       = self.args.full
        self.target_env         = self.args.deploy if isinstance(self.args.deploy, str) and len(self.args.deploy) > 0 else self.args.target
        self.patch_ref          = self.args.get('ref')
        self.patch_rollback     = 'CONTINUE' if self.args.get('continue') else 'EXIT ROLLBACK'
        self.patch_dry          = False
        self.patch_file_moveup  = self.args.moveup
        #
        self.init_config()

        # adjust sequence
        if isinstance(self.args.create, bool) and self.args.create:
            self.patch_seq      = '0' if '#PATCH_SEQ#' in self.config.patch_folder else ''

        # prepare internal variables
        self.patch_files        = []
        self.patch_files_apex   = []
        self.patch_file         = ''
        self.patch_folder__     = self.repo_root + self.config.patch_root + self.config.patch_folder
        self.patch_folder       = ''
        self.patch_folders      = {}
        self.patch_sequences    = {}
        self.patch_current      = {}
        self.patch_status       = ''
        self.all_commits        = {}
        self.all_files          = {}
        self.relevant_commits   = []
        self.relevant_count     = {}
        self.relevant_files     = {}
        self.diffs              = {}
        self.hash_commits       = []
        self.head_commit        = None
        self.head_commit_id     = None
        self.first_commit_id    = None
        self.first_commit       = None
        self.last_commit_id     = None
        self.last_commit        = None
        self.postfix_before     = self.config.patch_postfix_before
        self.postfix_after      = self.config.patch_postfix_after
        self.commits_file       = self.config.repo_commits_file.replace('#BRANCH#', self.info.branch)
        self.show_commits       = (self.args.commits or 10) if self.patch_code == None else self.args.commits
        self.show_patches       = (self.args.patches or 10)
        self.patches            = {}
        self.patch_found        = []
        self.deploy_plan        = []
        self.deploy_schemas     = {}
        self.deploy_conn        = {}
        self.logs_prefix        = self.config.patch_deploy_logs.replace('{$TARGET_ENV}', self.target_env or '')
        self.script_stats       = {}
        self.obj_not_found      = []

        # fetch changes in Git
        if self.args.fetch:
            self.fetch_changes()

        # make sure we have all commits ready
        self.get_all_commits()
        self.get_matching_commits()

        # go through patch folders
        self.get_patch_folders()

        # archive old patches and quit
        if self.args.archive != []:
            self.archive_patches(self.args.archive)
            util.quit()

        # create install script
        if self.args.install:
            self.create_install()
            util.quit()

        # merge folder if requested
        if self.args.implode:
            self.implode_folder(self.args.implode)
            util.quit()

        # delete lost/forgotten diff tables
        if self.args.deldiff:
            self.delete_diff_tables()
            util.quit()

        # show recent commits and patches
        if not self.args.hash:
            if self.patch_code:
                # show recent commits for selected patch
                # show more details if we have them
                self.show_matching_commits()
                self.show_matching_patches()

                # check number of commits
                if len(self.relevant_commits) == 0:
                    util.raise_error('NO COMMITS FOUND',
                        'please adjust your input parameters')
            #
            else:
                if self.show_commits > 0:
                    self.show_recent_commits()
                if self.show_patches > 0:
                    self.show_matching_patches()

            if self.patch_code == None:
                util.assert_(self.patch_code, 'MISSING ARGUMENT: PATCH CODE')

            # show help for processing specific commits
            if self.patch_code and not self.args.create:
                if self.patch_current['day']:
                    if self.patch_current['day'] and self.patch_current['day'] in self.patch_folders:
                        data = []
                        for folder, info in self.patch_folders[self.patch_current['day']].items():
                            if info['seq']:
                                data.append({
                                    #'folder'    : folder
                                    'day'           : info['day'],
                                    'seq'           : info['seq'],
                                    'patch_code'    : info['patch_code'],
                                })
                        #
                        if len(data):
                            util.print_header('TODAY\'S FOLDERS:')
                            util.print_table(data)

                # check clash on patch sequence
                elif len(self.patch_sequences.get(self.patch_seq, [])) > 0:
                    util.raise_error('CLASH ON PATCH SEQUENCE',
                        'you should select a different sequence')

        # create hash file based on previous commit
        if self.args.hash:
            self.generate_hash_file()
            self.show_matching_commits()
            #
            if self.args.create:
                self.create_patch()
            #
        elif self.patch_code:
            # create patch for requested name and seq
            if (self.args.create or self.args.deploy):
                if not self.args.create:
                    self.patch_dry = True

                    # find most recent patch
                    recent_patch = ''
                    for ref in sorted(self.patches.keys(), reverse = True):
                        info = self.patches[ref]
                        if self.patch_code == info['patch_code']:
                            if info['folder'] > recent_patch:
                                self.patch_seq = info['seq']
                #
                self.create_patch()

        # also deploy, we can do create, deploy or create+deploy
        if self.patch_code:
            if self.args.deploy:
                self.deploy_patch()

            # offer/hint next available sequence
            if not self.args.deploy and not self.args.create and self.patch_status != 'SUCCESS':
                try:
                    next = max(self.patch_sequences)
                    next = str(int(next) + 1) if next.isnumeric() else '#'
                except:
                    next = '1'
                #
                util.print_header('TO CREATE PATCH SPECIFY SEQUENCE:', next)
                util.print_help('add -create #  to create patch with specified sequence')
                util.print_help('add -create    to create patch without sequence')
                print()



    def show_matching_patches(self):
        found_patches = []
        for ref in sorted(self.patches.keys(), reverse = True):
            info = self.patches[ref]
            if (self.patch_code == None or self.patch_code in info['patch_code']):
                if self.args.my and info['my'] != 'Y':
                    continue
                #
                found_patches.append({
                    'ref'           : info['ref'],
                    'my'            : info['my'],
                    'patch_code'    : info['patch_code'] or info['folder'],
                    'files'         : len(info['files']),
                    'commits'       : len(info['commits']),
                    'deployed_at'   : info['deployed_at'],
                    'result'        : info['result'],
                })
                self.patch_status = info['result']

        # show recent patches
        if ((self.patch_code == None and self.show_patches > 0) or len(found_patches) > 0):
            util.print_header('RECENT PATCHES:', self.target_env)
            util.print_table(found_patches, limit_bottom = self.show_patches)



    def generate_hash_file(self):
        # get either requested commit or the most recent one
        if type(self.args.hash) == int:
            target_commit_num = self.args.hash
        else:
            target_commit_num = max(self.relevant_commits or [self.head_commit_id])

        # get last known rollout log before target commit
        hashes = [1]
        for file in util.get_files(self.config.patch_hashes + 'rollout.*.log'):
            commit_num = util.extract_int(r'rollout.(\d+).log', file)
            if commit_num < target_commit_num:
                hashes.append(commit_num)
        #
        prev_commit = max(hashes)

        # generate hash file for files changed in between these two commits
        self.rollout_file = self.config.patch_hashes + 'rollout.{}.log'.format(target_commit_num)
        #
        util.print_header('GENERATING HASH FILE:', '{} -> {}'.format(prev_commit, target_commit_num))
        self.create_patch_hashfile(prev_commit = prev_commit, curr_commit = target_commit_num)
        print('  - {}'.format(self.rollout_file))
        print()



    def create_patch_hashfile(self, prev_commit, curr_commit):
        # get last file modification
        files = self.get_hash_files(prev_commit, curr_commit)

        # create rollout log
        rollout = []
        for file in sorted(files.keys()):
            commit_num  = files[file]
            obj         = File(file, config = self.config)
            #
            if obj.is_object:
                file_hash = self.all_commits[commit_num].get('files', {}).get(file)
                if not file_hash:
                    continue
                #
                rollout.append('{} | {} | {}'.format(file, commit_num, file_hash))
        #
        util.write_file(self.rollout_file, payload = rollout)



    def get_hash_files(self, prev_commit, curr_commit):
        self.hash_commits = []
        files = {}
        for commit_num in sorted(self.all_commits.keys()):
            if commit_num <= prev_commit and prev_commit != 1:
                continue
            if commit_num > curr_commit and curr_commit != 1:
                continue

            # skip non requested commits
            if len(self.add_commits) > 0:
                commits     = '|{}|'.format('|'.join(self.add_commits))
                search_for  = '|{}|'.format(commit_num)
                #
                if not (search_for in commits):
                    continue

            # skip ignored commits
            if len(self.ignore_commits) > 0:
                commits     = '|{}|'.format('|'.join(self.ignore_commits))
                search_for  = '|{}|'.format(commit_num)
                #
                if search_for in commits:
                    continue

            # store commits for overview
            if not (commit_num in self.hash_commits):
                self.hash_commits.append(commit_num)

            # build list of changed files
            for file in self.all_commits[commit_num].get('files', {}).keys():
                if self.is_usable_file(file):
                    files[file] = commit_num
        #
        return files



    def create_patch(self):
        self.create_patch_files()
        self.create_deployment_plan()

        # show summary
        folder = self.patch_folder.replace(self.repo_root + self.config.patch_root, '')
        util.print_header('PATCH OVERVIEW:', folder if self.args.create else '')
        util.print_table(self.deploy_plan, right_align = ['app_id'])



    def create_deployment_plan(self):
        for order, schema_with_app in enumerate(sorted(self.relevant_files.keys())):
            schema, app_id = self.get_schema_split(schema_with_app)
            self.deploy_plan.append({
                'order'     : order + 1,
                'file'      : schema_with_app + '.sql',
                'schema'    : schema,
                'app_id'    : app_id,
                'files'     : len(self.relevant_files[schema_with_app]),
                'commits'   : len(self.relevant_count[schema_with_app]),
            })

            # create deployment plan
            if not (schema in self.deploy_schemas):
                self.deploy_schemas[schema] = []
            self.deploy_schemas[schema].append(order)



    def deploy_patch(self):
        self.check_connections()

        # create folder for logs
        log_folder = '{}/{}/'.format(self.patch_folder, self.logs_prefix)
        if not os.path.exists(log_folder):
            os.makedirs(log_folder)

        # generate table headers before we know size of the data
        max_file_len = 0
        for plan in self.deploy_plan:
            max_file_len = max(max_file_len, len(plan['file']))
        #
        map = {         # widths (in charaters)
            'order'     : 5,
            'file'      : max_file_len,
            'output'    : 6,
            'status'    : 7,
            'timer'     : 5,
        }
        util.print_header('PATCHING PROGRESS AND RESULTS:')
        util.print_table([], columns = map)

        self.patch_status   = ''
        self.patch_results  = []
        build_logs          = {}

        # run the target script(s) and spool the logs
        for order, plan in enumerate(self.deploy_plan):
            start = util.get_start()

            # check if file exists
            full = '{}/{}'.format(self.patch_folder, plan['file'])
            if not os.path.exists(full):
                util.raise_error('FILE MISSING', full)

            # cleanup the script from comments, fix prompts
            payload = []
            with open(full, 'rt', encoding = 'utf-8') as f:
                for line in f.readlines():
                    line = line.strip()
                    if line.startswith('--') or line == '':
                        continue
                    if line.startswith('PROMPT'):
                        line = line.replace('PROMPT --;', 'PROMPT ---;')
                    #
                    payload.append(line)
            payload = '\n'.join(payload)

            # execute the script
            output  = self.deploy_conn[plan['schema']].sqlcl_request(payload, root = self.patch_folder, silent = True)
            lines   = output.splitlines()

            # search for error message
            success = None
            for line in lines:
                if line.startswith('Error starting at line'):
                    success = False
                    break

            # search for the success prompt at last few lines
            if success == None:
                for line in lines[-10:]:                # last 10 lines
                    if line.startswith('-- SUCCESS'):   # this is in patch.py
                        success = True
                        break

            # prep results for the template
            results = {
                'order'     : order + 1,
                'file'      : plan['file'],
                'output'    : len(lines),
                'status'    : 'SUCCESS' if success else 'ERROR',
                'timer'     : int(round(util.get_start() - start + 0.5, 0)),  # ceil
            }
            self.patch_results.append({**self.deploy_plan[order], **results})
            self.patch_status = 'SUCCESS' if (success and (self.patch_status == 'SUCCESS' or self.patch_status == '')) else 'ERROR'

            # rename log to reflect the result in the file name
            log_file    = full.replace('.sql', '.log')
            log_status  = '{}/{} {} [{}].log'.format(log_folder, plan['file'].replace('.sql', ''), self.config.today_deploy, results['status'])
            payload     = util.cleanup_sqlcl(output, lines = False).replace('---\n', '--\n')
            payload     = util.replace(payload, r'(\nComment created.\n)', '\n', flags = re.M)
            #
            build_logs[os.path.basename(full)] = payload
            #
            if os.path.exists(log_file):
                os.rename(log_file, log_status)
            else:
                # if no spooling, create file manually
                util.write_file(log_status, payload)

            # show progress
            util.print_table([results], columns = map, right_align = ['order', 'output', 'timer'], no_header = True)
            util.beep_success()
        print()

        # send notification on success
        if self.patch_status == 'SUCCESS' or 1 == 1:
            title       = '{} - Patch {} deployed'.format(self.target_env, self.patch_code)
            author      = '<at>{}</at>'.format(self.repo_user_mail)
            stamp       = datetime.datetime.today().strftime('%Y-%m-%d %H:%M')
            message     = '{}\n{}'.format(author, stamp)
            blocks      = []

            # add patch status table
            blocks.extend(self.build_table(
                data        = self.patch_results,
                columns     = ['order', 'file', 'schema', 'app_id', 'files', 'commits', 'status', 'timer'],
                widths      = [2, 5, 2, 2, 2, 2, 3, 2],  # as a ratio in between columns,
                right_align = ['order', 'app_id', 'files', 'commits', 'timer']
            ))

            # add commits
            data = []
            for commit_id in sorted(self.relevant_commits, reverse = True):
                commit = self.all_commits[commit_id]
                data.append({
                    'commit'    : commit_id,
                    'summary'   : util.get_string(commit['summary'], 50),
                })
            blocks.append('')
            blocks.extend(self.build_table(
                data        = data,
                columns     = ['commit', 'summary'],
                widths      = [1, 7],  # as a ratio in between columns,
                right_align = ['commit']
            ))

            # find most recent patch commit
            last_commit = self.relevant_commits[0]
            last_commit = self.all_commits[last_commit]

            # add links to GitHub
            actions = [
                {'View on GitHub' : self.repo_url.replace('.git', '/commit/' + last_commit['id'])},
            ]
            self.notify_team(title, message, blocks = blocks, actions = actions)

            # also post build logs
            for file in sorted(build_logs.keys()):
                message = self.build_header('Build log: ' + file)
                blocks  = self.build_mono(build_logs[file])
                self.notify_team('', message, blocks = blocks)

        # recompile invalid objects
        for order, plan in enumerate(self.deploy_plan):
            schema  = plan['schema']
            args    = ['-target', self.target_env, '-schema', schema, '-silent', 'Y']
            reco    = Recompile(args = args, conn = self.deploy_conn[schema], silent = True)



    def check_connections(self):
        # maybe we are already connected
        for schema in self.deploy_schemas.keys():
            if schema in self.deploy_conn and self.deploy_conn[schema]:
                return

        # connect to all target schemas first so we know we can deploy all scripts
        util.print_header('CONNECTING TO {}:'.format(self.target_env))
        for schema in self.deploy_schemas.keys():
            self.init_connection(env_name = self.target_env, schema_name = schema)
            util.print_now('  {} '.format(schema).ljust(72, '.') + ' ')
            self.deploy_conn[schema] = self.db_connect(ping_sqlcl = False, silent = True)
            self.deploy_conn[schema].sqlcl_root = self.patch_folder
            print('OK')
        print()



    def get_schema_split(self, schema_with_app):
        schema, app_id, _ = (schema_with_app + '..').split('.', maxsplit = 2)
        return (schema, int(app_id) if app_id else None)



    def get_folder_split(self, folder):
        if os.path.isdir(folder):
            folder      = folder.replace(self.repo_root + self.config.patch_root, '')
            patch_code  = folder
        else:
            patch_code  = os.path.splitext(folder.replace(self.repo_root + self.config.patch_root, ''))[0]
            folder      = ''

        # split folder name
        splitter = self.config.patch_folder_splitter.replace('~', '-')
        if splitter == '':
            return {
                'day'           : '',
                'seq'           : '',
                'patch_code'    : patch_code,
                'folder'        : folder,
            }
        #
        result = folder.split(splitter, maxsplit = 2)
        return {
            'day'           : result[0],
            'seq'           : result[1] if len(result) > 1 else '',
            'patch_code'    : result[2] if len(result) > 2 and result[2] != 'None' else '',
            'folder'        : folder,
        }



    def get_patch_folder(self):
        return util.replace(self.patch_folder__, {
            '#PATCH_SEQ#'       : self.patch_seq,
            '#PATCH_CODE#'      : self.patch_code,
        }).rstrip()



    def get_patch_folders(self):
        # extract values from folder name to find/compare today's patch
        self.patch_folder   = self.get_patch_folder()
        self.patch_current  = self.get_folder_split(self.patch_folder)

        # identify patch folder
        for ref, folder in enumerate(util.get_files(self.repo_root + self.config.patch_root + '*', reverse = True, recursive = False), start = 1):
            # get more info from folder name
            root    = folder
            info    = self.get_folder_split(folder)

            # for current day sequence clash check
            if info['day'] == self.patch_current['day']:
                if not (info['seq'] in self.patch_sequences):
                    self.patch_sequences[info['seq']] = []
                if info['patch_code'] != self.patch_code:   # collect just other patches
                    self.patch_sequences[info['seq']].append(info['patch_code'])

            # get some numbers & deduplicate
            info['my'] = ''
            found_commits, found_files = [], []
            for commit_id, commit in self.all_commits.items():
                if info['patch_code'] in commit['summary']:
                    info['my'] = 'Y' if (self.repo_user_mail == commit['author'] or info['my']) else ''
                    #
                    found_commits.append(commit_id)
                    found_files.extend(commit['files'].keys())
            #
            info['files']   = list(set(found_files))
            info['commits'] = list(set(found_commits))

            # extract deployment result and date from log names
            buckets = {}    # use buckets to get overall status over multiple files
            for file in util.get_files(root + '/' + self.logs_prefix + '/*.log'):
                base        = os.path.splitext(os.path.basename(file))[0].split(' ')
                schema      = base.pop(0)
                result      = base.pop(-1).replace('[', '').replace(']', '')
                deployed    = util.replace(' '.join(base).replace('_', ' '), r'( \d\d)[-](\d\d)$', '\\1:\\2')  # fix time
                #
                if not (deployed in buckets):
                    buckets[deployed] = result
                else:
                    buckets[deployed] = result if result == 'ERROR' else min(buckets[deployed], result)
            #
            info['ref']         = ref
            info['deployed_at'] = max(buckets.keys())                   if buckets != {} else ''
            info['result']      = buckets.get(info['deployed_at'], '')  if buckets != {} else ''
            self.patches[ref]   = info



    def get_all_commits(self):
        # read stored values
        all_hashes = []
        if os.path.exists(self.commits_file):
            with open(self.commits_file, 'rt', encoding = 'utf-8') as f:
                self.all_commits = dict(util.get_yaml(f, self.commits_file))
                for _, commit in self.all_commits.items():
                    all_hashes.append(commit['id'])

        # check for new format, dict with file hashes is expected, not the bare list
        for commit, data in self.all_commits.items():
            if type(data.get('files', {})) == list:
                self.args.rebuild = True
        #
        if len(self.all_commits.keys()) == 0:       # no keys = rebuild
            self.args.rebuild = True

        # detect correct branch
        branches = {}
        for row in self.repo.branches:
            branches[row.name] = row
        #
        if not (self.info.branch in branches):
            self.info.branch = self.repo.active_branch

        # estimate number of commits to show progress
        commits = 0
        for commit in self.repo.iter_commits(self.info.branch, max_count = 1, skip = 0, reverse = False):
            commits = commit.count()
        #
        if self.args.rebuild:
            self.all_commits, all_hashes = {}, []
            #
            print()
            print('    BRANCH |', self.info.branch)
            print('   COMMITS |', commits)
            print()
            print('REBUILDING:   // time to get a coffee')

        # loop throught all commits from newest to oldest, add missing commits
        progress_target = commits
        progress_done   = 0
        start           = util.get_start()
        new_commits     = []
        #
        for commit in self.repo.iter_commits(self.info.branch, skip = 0, reverse = False):
            commit_hash = str(commit)
            if commit_hash in all_hashes:       # last known commit reached
                break

            # calculate file hash right away
            committed_files = {}
            for file in sorted(commit.stats.files.keys()):
                if self.is_usable_file(file):
                    file_payload            = self.get_file_from_commit(file, commit = commit_hash)
                    committed_files[file]   = util.get_hash(file_payload)
            #
            new_commits.append({                        # number
                'id'        : commit_hash,              # hash
                'summary'   : commit.summary,
                'author'    : commit.author.email,
                'date'      : commit.authored_datetime,
                'files'     : committed_files,          # database + APEX files and their hashes
            })

            # show progress
            if self.args.rebuild:
                progress_done = util.print_progress(progress_done, progress_target, start = start)
        if self.args.rebuild:
            util.print_progress_done(start = start)
            print()

        if self.args.rebuild:
            print('DELETED FILES:')

        # load last commit number
        if len(self.all_commits) > 0:
            self.head_commit_id = max(self.all_commits.keys())

        # attach new commits with proper id
        progress_target = len(new_commits)
        progress_done   = 0
        start           = util.get_start()
        commit_id       = self.head_commit_id or 0
        #
        for obj in reversed(new_commits):
            obj['deleted'] = []
            #
            commit_id += 1
            if commit_id > 1:
                # store list of deleted files
                prev_commit_id  = self.all_commits[commit_id - 1]['id']
                curr_commit_id  = obj['id']
                #
                try:
                    diffs = self.repo.commit(prev_commit_id).diff(curr_commit_id)
                except:
                    util.raise_error('REBUILD NEEDED')
                #
                for diff in diffs:
                    rows = str(diff).splitlines()
                    if 'file deleted in rhs' in rows[-1]:
                        obj['deleted'].append(rows[0])
            #
            self.all_commits[commit_id] = obj
            #
            if self.args.rebuild:
                progress_done = util.print_progress(progress_done, progress_target, start = start)
        if self.args.rebuild:
            util.print_progress_done(start = start)

        # remove 90 days old commits
        old_date = datetime.datetime.now().date() - datetime.timedelta(days = self.config.repo_commit_days)
        for commit_id, obj in dict(self.all_commits).items():
            if obj['date'].date() < old_date:
                self.all_commits.pop(commit_id)

        # prepare head commit, self.repo.commit('HEAD')
        self.head_commit    = self.all_commits[commit_id]
        self.head_commit_id = commit_id

        # store commits in file for better performance
        if len(new_commits) > 0:
            if os.path.exists(self.commits_file):
                os.remove(self.commits_file)
            util.write_file(self.commits_file, self.all_commits, yaml = True)

        # also store commits with files as keys
        for commit_id in sorted(self.all_commits.keys()):
            obj = self.all_commits[commit_id]
            for file in obj['files'].keys():
                if not (file in self.all_files):
                    self.all_files[file] = []
                self.all_files[file].append(commit_id)

        # clean screen on rebuild
        if self.args.rebuild:
            print()
            sys.exit()



    def is_usable_file(self, file):
        if not (file.endswith('.sql')):
            return False
        #
        if file.startswith(self.config.path_objects):
            return True
        if file.startswith(self.config.path_apex):
            return True
        if file.startswith(self.config.patch_scripts_snap):
            return True
        #
        return False


    def get_matching_commits(self):
        # add or remove specific commits from the queue
        for commit_id in sorted(self.all_commits.keys(), reverse = True):
            commit = self.all_commits[commit_id]

            # skip non requested commits
            if len(self.add_commits) > 0:
                commits     = '|{}|'.format('|'.join(self.add_commits))
                search_for  = '|{}|'.format(commit_id)
                #
                if not (search_for in commits):
                    continue

            # skip ignored commits
            if len(self.ignore_commits) > 0:
                commits     = '|{}|'.format('|'.join(self.ignore_commits))
                search_for  = '|{}|'.format(commit_id)
                #
                if search_for in commits:
                    continue

            # skip non relevant commits
            if (self.search_message != [] and self.search_message != ['%']):
                found_match = False
                for word in [word for word in self.search_message if word is not None]:
                    if word in commit['summary']:
                        found_match = True
                        break
                if not found_match:
                    continue

            # store relevant commit
            self.relevant_commits.append(commit_id)

            # process files in commit
            for file, file_hash in commit['files'].items():
                # process just the listed extensions (in the config)
                if os.path.splitext(file)[1] != '.sql':
                    continue

                # skip embedded code report files
                if '/embedded_code/' in file:
                    continue

                # process just database and APEX exports
                if not (self.is_usable_file(file)):
                    continue

                # get APEX app info from filename
                schema = self.info.schema
                if self.config.path_apex in file:
                    app_id = util.extract_int(self.config.apex_path_app_id, file.replace(self.config.path_apex, ''))
                    if app_id:
                        if not file.startswith(self.get_root(app_id).replace(self.repo_root, '')):
                            continue

                        # append app_id to separate APEX files
                        schema = '{}.{}'.format(self.connection.get('schema_apex') or schema, app_id)
                #
                if not (schema in self.relevant_files):
                    self.relevant_files[schema] = []
                    self.relevant_count[schema] = []
                if not (file in self.relevant_files[schema]):
                    self.relevant_files[schema].append(file)
                if not (commit_id in self.relevant_count[schema]):
                    self.relevant_count[schema].append(commit_id)

        # check number of commits
        if len(self.relevant_commits) == 0:
            return

        # get last version (max) and version before first change (min)
        self.first_commit_id    = max(min(self.relevant_commits) - 1, 1)  # minimum = 1
        self.last_commit_id     = max(self.relevant_commits)
        #
        if not (self.first_commit in self.all_commits):
            for id in sorted(self.all_commits.keys(), reverse = True):
                if id <= self.first_commit_id:
                    self.first_commit_id = id
                    break
        #
        if not (self.first_commit_id in self.all_commits):
            util.print_warning(
                'COMMIT {} OUT OF RANGE'.format(self.first_commit_id), [
                    'INCREASE repo_commit_days IN CONFIG',
                ])
            self.first_commit_id = min(self.all_commits.keys())
        #
        try:
            self.first_commit   = self.repo.commit(self.all_commits[self.first_commit_id]['id'])
            self.last_commit    = self.repo.commit(self.all_commits[self.last_commit_id]['id'])
        except:
            util.raise_error('REBUILD NEEDED')



    def show_matching_commits(self):
        # pivot commits
        commits_map = {}
        for ref in sorted(self.patches.keys()):
            for commit in self.patches[ref]['commits']:
                commits_map[commit] = ref

        # show relevant recent commits
        header  = 'REQUESTED' if (self.args.hash or self.add_commits != [] or self.ignore_commits != []) else 'RELEVANT'
        data    = []
        picked  = self.hash_commits if self.args.hash else self.relevant_commits
        #
        for commit_id in sorted(picked, reverse = True):
            commit = self.all_commits[commit_id]
            data.append({
                'commit'    : commit_id,
                #'ref'       : commits_map.get(commit_id, ''),
                'summary'   : util.get_string(commit['summary'], 50),
                'files'     : len(commit['files']),
            })
        #
        util.print_header('{} COMMITS FOR "{}":'.format(header, ' '.join(self.search_message or [])))
        util.print_table(data)



    def show_recent_commits(self):
        # loop through all recent commits
        data = []
        for commit_id in sorted(self.all_commits.keys(), reverse = True):
            if len(data) == self.show_commits:
                break
            #
            commit = self.all_commits[commit_id]
            if self.args.my and self.repo_user_mail != commit['author']:
                continue
            #
            data.append({
                'commit'        : commit_id,
                'my'            : 'Y' if self.repo_user_mail == commit['author'] else '',
                'summary'       : util.get_string(commit['summary'], 50),
            })
        #
        util.print_header('RECENT COMMITS:')
        util.print_table(data, limit_top = self.show_commits)



    def create_patch_files(self):
        # generate patch file name for specific schema
        self.patch_folder = self.get_patch_folder()

        # create snapshot folder
        if not os.path.exists(self.patch_folder):
            os.makedirs(self.patch_folder)
        elif not self.patch_dry:
            # delete everything in patch folder
            util.delete_folder(self.patch_folder)

        # simplify searching for ignored files
        skip_apex_files = '|{}|'.format('|'.join(self.config.apex_files_ignore))

        # move driving file a bit higher
        self.patch_file = '{}/../{}.sql'.format(self.patch_folder, self.patch_code)
        if self.patch_file_moveup:
            util.write_file(self.patch_file, '')
        elif os.path.exists(self.patch_file):
            os.remove(self.patch_file)

        # process files per schema
        for schema_with_app in sorted(self.relevant_files.keys()):
            schema, app_id = self.get_schema_split(schema_with_app)
            #
            if not self.patch_file_moveup:
                self.patch_file     = '{}/{}.sql'.format(self.patch_folder, schema_with_app)
            self.patch_spool_log    = './{}.log'.format(schema_with_app)  # must start with ./ and ends with .log for proper function
            #
            if self.patch_file_moveup:
                self.patch_file     = '{}/../{}.sql'.format(self.patch_folder, self.patch_code)

            # generate patch header
            payload = [
                '--',
                '-- {:>16} | {}'.format('PATCH CODE', self.patch_code),
                '-- {:>16} | {}'.format('SCHEMA', schema),
                '-- {:>16} | {}'.format('APP ID', app_id) if app_id else None,
                '--',
            ]

            # get differences in between first and last commits
            # also fill the self.diffs() with files changed in commits
            # in self.relevant_files we can have files which were deleted
            payload.extend(self.get_differences(self.relevant_files[schema_with_app]))

            # need to map files to object types & sort them by dependencies
            # (1) self.diffs.keys() with committed files
            # (2) self.patch_templates with template files (only if some files were changed), before and after (1)
            # (3) self.patch_script with adhoc files (add every time), before and after (1)
            #
            files_to_process = {}
            for file in self.diffs.keys():
                # skip file if it should be ignored in the patch (but keep it in snapshot folder)
                try:
                    short_file = '/' + file.split('/', maxsplit = 2)[2]
                except:
                    short_file = ''
                #
                if short_file in skip_apex_files:
                    continue

                # skip all grant files, since we pull just related grants later
                if file.startswith(os.path.dirname(self.patch_grants.replace(self.repo_root, ''))):
                    continue

                # skip full exports, need to add support for alias...
                if app_id:
                    if file == self.get_root(app_id, 'f{}.sql'.format(app_id)):
                        continue
                #
                short = file.replace(self.repo_root, '')
                files_to_process[file] = self.repo_files.get(short) or File(file, config = self.config)

            # find files in groups so we can skip templates or not
            files_grouped = {}
            for group in self.config.patch_map.keys():
                files_grouped[group] = []

                # process committed files
                for object_type in self.config.patch_map[group]:
                    # scenario (1)
                    for file in list(files_to_process.keys()):  # copy
                        obj = files_to_process[file]
                        if obj.is_object and obj.object_type == object_type:
                            if not (file in files_grouped[group]):
                                files_grouped[group].append(file)
                                files_to_process.pop(file, '')

                        # put scripts on the side
                        if file.startswith(self.config.patch_scripts_snap):
                            files_to_process.pop(file, '')

            # create a file in scripts to drop object
            for file in self.relevant_files[schema_with_app]:
                if not (file in self.diffs):
                    object_name     = self.get_object_name(file)
                    object_type     = self.get_object_type(file)
                    #
                    if object_name and object_type and object_type not in ('GRANT',):
                        script_drop = util.replace(query.templates['DROP'], {
                            '{$HEADER}'         : 'DROP {} {}'.format(object_type, object_name),
                            '{$OBJECT_TYPE}'    : object_type,
                            '{$OBJECT_NAME}'    : object_name,
                            '{$STATEMENT}'      : 'DROP {} {}'.format(object_type, object_name),
                        })
                        script_file = '{}objects_after/drop.{}.{}.sql'.format(self.config.patch_scripts_dir, object_type.replace(' ', '_').lower(), object_name.lower())
                        #
                        util.write_file(script_file, script_drop)

            # detect changed tables
            self.alter_files = {}
            for file in self.relevant_files[schema_with_app]:
                if file in self.diffs:
                    object_name     = self.get_object_name(file)
                    object_type     = self.get_object_type(file)
                    #
                    if object_name and object_type == 'TABLE':
                        last_commit     = max(self.relevant_commits)
                        first_commit    = min(self.relevant_commits)
                        #
                        for commit_num in self.relevant_commits:
                            if commit_num >= first_commit and commit_num <= last_commit and commit_num in self.all_files[file]:
                                if not self.conn:
                                    self.conn = self.db_connect(ping_sqlcl = False, silent = True)
                                #
                                alter_payload = ''
                                for alter in self.get_table_diff(file, object_name, commit_num - 1, commit_num):
                                    if alter:
                                        alter_payload += '{};\n'.format(alter)
                                #
                                if alter_payload:
                                    alter_file = self.config.patch_scripts_dir + 'tables_after.' + os.path.basename(file).replace('.sql', '.{}.sql'.format(commit_num))
                                    util.write_file(alter_file, alter_payload)
                                    self.alter_files[alter_file] = alter_payload
            #
            if len(self.alter_files) > 0:
                util.print_header('TABLE CHANGES DETECTED:')
                for file in sorted(self.alter_files):
                    print('  - {}'.format(file))
                print()

            # processed groups one by one in order defined by patch_map
            files_processed     = []
            scripts_processed   = []
            uncommitted_files   = []
            #
            for group in self.config.patch_map.keys():
                # get adhoc scripts
                scripts_before, scripts_after = [], []
                if not app_id and self.config.patch_add_scripts:
                    scripts_before  = self.get_script_files(group, before = True)
                    scripts_after   = self.get_script_files(group, before = False, ignore_timing = True)

                # continue only if we have committed files or scripts
                files = files_grouped[group]
                if len(files) == 0 and len(scripts_before) == 0 and len(scripts_after) == 0:
                    continue

                # (2) before template
                if self.config.patch_add_templates:
                    for file in self.get_template_files(group + self.postfix_before):
                        if not (file in files_processed):
                            files_processed.append(file)

                # (3) before script
                for file in scripts_before:
                    if not (file in files_processed):
                        files_processed.append(file)
                        scripts_processed.append(file)

                # sort files by dependencies
                for file in self.sort_files_by_deps(files):
                    if not (file in files_processed):
                        files_processed.append(file)

                # (3) after script
                for file in scripts_after:
                    if not (file in files_processed):
                        files_processed.append(file)
                        scripts_processed.append(file)

                # (2) after template
                if self.config.patch_add_templates:
                    for file in self.get_template_files(group + self.postfix_after):
                        if not (file in files_processed):
                            files_processed.append(file)

            # check unknown files
            if not app_id and self.config.patch_add_scripts:
                unknown = self.get_script_unknow_files(scripts_processed)
                if len(unknown) > 0:
                    util.print_warning('UNKOWN SCRIPTS:', unknown)

            # attach APEX files
            if app_id:
                for file in list(files_to_process.keys()):  # copy
                    files_processed.append(file)
                    self.create_file_snapshot(file, app_id = app_id)
            #
            elif len(files_to_process.keys()) > 0:
                unprocessed = []
                for file in files_to_process:
                    unprocessed.append(file)
                #
                util.raise_error('NOT ALL FILES PROCESSED', *unprocessed)

            # create APEX specific snapshot files
            if app_id:
                self.create_apex_snapshots(app_id)

            # set defaults in case they are not specified in init file
            # spool output to the file
            payload.extend([
                'SET DEFINE OFF',
                'SET TIMING OFF',
                'SET SQLBLANKLINES ON',
                '--',
                'WHENEVER OSERROR  {};'.format(self.patch_rollback),
                'WHENEVER SQLERROR {};'.format(self.patch_rollback),
                '--',
            ])
            if self.config.patch_spooling:
                payload.append('SPOOL "{}" APPEND;\n'.format(self.patch_spool_log))

            # add properly sorted files (objects by dependencies) to the patch
            if app_id and app_id in self.full_exports:
                # attach the whole application for full imports
                file = '{}f{}.sql'.format(self.get_root(app_id), app_id)
                file, _ = self.create_file_snapshot(file, app_id = app_id)
                file = file.replace(self.patch_folder, '')       # replace first, full path
                file = util.replace(self.config.patch_file_link if not self.patch_file_moveup else self.config.patch_file_link_moveup, {
                    '#FILE#' : file.lstrip('/'),
                })
                payload.extend(self.attach_files(self.get_template_files('apex_init'), category = 'INIT', app_id = app_id))
                payload.extend([
                    '--',
                    '-- APPLICATION {}'.format(app_id),
                    '--',
                    file,
                    '',
                ])
            #
            else:
                # load init files, for database or APEX
                if self.config.patch_add_templates:
                    payload.extend(self.attach_files(self.get_template_files('apex_init' if app_id else 'db_init'), category = 'INIT', app_id = app_id))

                # attach APEX starting file for partial APEX exports
                if app_id:
                    # attach the whole application for full imports (as a fallback)
                    payload.extend([
                        'SET DEFINE OFF',
                        'SET TIMING OFF',
                        '--',
                    ])

                    # attach starting file
                    file = self.get_root(app_id, 'application/set_environment.sql')
                    payload.extend(self.attach_file(file, header = 'APEX COMPONENTS START', category = 'STATIC', app_id = app_id))
                    payload.append(
                        # replace existing components
                        'BEGIN wwv_flow_imp.g_mode := \'REPLACE\'; END;\n/\n'
                    )

                # go through files
                apex_pages = []
                for file in files_processed:
                    # modify list of APEX files
                    if app_id:
                        # move APEX pages to the end + create script to delete them in patch
                        search = re.search(r'/pages/page_(\d+)\.sql', file)
                        if search:
                            apex_pages.append(file)
                            continue

                        # skip full APEX exports
                        if len(re.findall(r'/f\d+/f\d+\.sql$', file)) > 0:
                            continue

                    # attach file reference
                    payload.extend(self.attach_file(file, category = 'COMMIT', app_id = app_id))

                # attach APEX pages to the end
                if len(apex_pages) > 0:
                    payload.extend(self.fix_apex_pages(apex_pages))
            #
            payload.append('')

            # attach APEX ending file for partial APEX exports
            if app_id and not (app_id in self.full_exports):
                if not (app_id in self.full_exports):
                    file = self.get_root(app_id, 'application/end_environment.sql')
                    payload.extend(self.attach_file(file, header = 'APEX END', category = 'STATIC', app_id = app_id))

            # add grants made on referenced objects
            grants = self.get_grants_made(schema = schema)
            if len(grants) > 0:
                payload.extend([
                    'PROMPT --;',
                    'PROMPT -- GRANTS',
                    'PROMPT --;',
                ])
                payload.extend(grants)

            # load final files, for database or APEX
            if self.config.patch_add_templates:
                payload.extend(self.attach_files(self.get_template_files('apex_end' if app_id else 'db_end'), category = 'END', app_id = app_id))

            # add flag so deploy script can evaluate it as successful
            payload.extend([
                'PROMPT "";',
                'PROMPT --;',
                'PROMPT -- SUCCESS',
                'PROMPT --;',
                '',
            ])
            if self.config.patch_spooling:
                payload.append('SPOOL OFF;\n')

            # store payload in file
            self.create_patch_file(payload, app_id = app_id)
            util.print_header('PROCESSED FILES:', schema_with_app)
            for file in files_processed:
                # shorten file name
                orig_file = file
                if file.startswith(self.config.path_objects):
                    file = file.replace(self.config.path_objects, '')
                elif file.startswith(self.config.path_apex):
                    if len(file.split('/application/')) == 1:       # full export...
                        continue
                    file = file.split('/application/')[1]

                # get commit info
                curr_commit_id  = self.get_file_commit(orig_file)[1]
                obj_code        = self.repo_files.get(orig_file, {}).get('object_code') or ''

                # show processed file with some flags
                flag    = '-'
                extra   = ''
                #
                if file in scripts_processed:
                    flag = '!' if not curr_commit_id else '>'
                    statements = 0
                    for row in self.script_stats.get(file, {}):
                        if row['template']:
                            statements += 1
                    extra = '[ALT:{}]'.format(statements).replace('[ALT:0]', '')
                else:
                    extra = '[NEW]' if obj_code in self.obj_not_found else ''
                #
                pad = (72 - len(file) - len(extra)) * '.' if extra else ''
                print('  {} {} {} {}'.format(flag, file, pad, extra))

                # check if the file was part of newer commit
                if not curr_commit_id:
                    uncommitted_files.append(file)
                    continue
                #
                found_newer = []
                if not self.args.head:
                    for commit_id in sorted(self.all_files[orig_file]):
                        if commit_id > curr_commit_id:
                            commit = self.all_commits[commit_id]
                            found_newer.append('{}) {}'.format(commit_id, commit['summary'][0:50]))
                #
                if len(found_newer) > 0:
                    curr_commit = self.all_commits[curr_commit_id]
                    print('    ^')
                    for row in reversed(found_newer):
                        print('      NEW .......', row)
                    print('      CURRENT ... {}) {}'.format(curr_commit_id, curr_commit['summary'][0:50]))
                    print('      --')
            print()

            # show warnings for files which are not committed
            if len(uncommitted_files) > 0:
                util.print_warning('UNCOMMITTED FILES', uncommitted_files)

            # refresh objects and APEX components
            if self.args.refresh:
                components = []
                if app_id:
                    app_id = int(app_id)
                    for file in files_processed:
                        page_id = util.extract_int(r'/pages/page_(\d+)\.sql$', file)
                        if page_id:
                            components.append('PAGE:{}'.format(page_id))
                    #
                    args = ['-schema', schema]
                    util.print_header('REFRESHING OBJECTS:')
                    for comp in components:
                        print('  - {}'.format(comp))
                    print()
                    #
                    apex = Export_APEX(args = args, silent = True)
                    apex.args.app, apex.arg_apps = [app_id], [app_id]
                    #
                    apex.get_enrichments()
                    apex.export_recent(app_id = app_id, schema = schema, components = components)
                    apex.move_files(app_id)



    def delete_diff_tables(self):
        # drop them at DEV, not on target env!
        if not self.conn:
            self.conn = self.db_connect(ping_sqlcl = False, silent = True)

        util.print_header('DROPPING DIFF TABLES')

        # delete leftovers
        args = {
            'objects_prefix'    : self.objects_prefix   or '',
            'objects_ignore'    : self.objects_ignore   or '',
        }
        diff_tables = self.conn.fetch_assoc(query.diff_tables, **args)
        for row in diff_tables:
            print('  - {}'.format(row['table_name']))
            self.conn.drop_object('TABLE', row['table_name'])
        print()



    def get_differences(self, rel_files):
        self.diffs      = {}    # cleanup
        payload         = []
        new_files       = []
        deleted_files   = []
        modifed_files   = []
        #
        for diff in self.first_commit.diff(self.last_commit):
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
        for commit_id in sorted(self.relevant_commits, reverse = True):
            commit = self.all_commits[commit_id]
            files_found = False
            for file in commit['files'].keys():
                if file in rel_files:
                    files_found = True
                    break
            #
            if files_found:
                payload.append('--   {}) {}'.format(commit_id, commit['summary']))

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



    def get_script_files(self, group, before, ignore_timing = False):
        timing_before   = util.replace(self.postfix_before, r'[^a-z]+', '').strip()
        timing_after    = util.replace(self.postfix_after,  r'[^a-z]+', '').strip()
        timing          = timing_before if before else timing_after
        #
        found = []
        for file in util.get_files(self.config.patch_scripts_dir + '**/*.sql'):
            short = file.replace(self.config.patch_scripts_dir, '').replace('.sql', '')
            words = util.replace(short.lower(), r'[^a-z]+', ' ').split()
            #
            if group in words and (timing in words or ignore_timing) and (before or not (timing_before) in words):
                env_name = util.extract(r'\.\[([^\]]+)\]\.', file) or ''
                if env_name and env_name != self.target_env:
                    continue
                found.append(file)
        #
        return list(sorted(set(found)))  # unique files



    def get_script_unknow_files(self, scripts_processed):
        unknown = []
        for file in util.get_files(self.config.patch_scripts_dir + '**/*.sql'):
            if file in self.alter_files:
                continue
            if file in scripts_processed:
                continue
            #
            unknown.append(file)
        return unknown



    def get_template_files(self, folder):
        found = []
        for file in util.get_files('{}{}/*.sql'.format(self.config.patch_template_dir, folder)):
            env_name = util.extract(r'\.\[([^\]]+)\]\.', file) or ''
            if env_name and env_name != self.target_env:
                continue
            found.append(file)
        #
        return found



    def attach_file(self, file, header = '', category = '', app_id = None):
        attach_type = ''
        if category != '':
            attach_type = category
        if self.config.patch_template_dir in file:
            attach_type = 'TEMPLATE'
        elif self.config.patch_scripts_dir in file:
            attach_type = 'SCRIPT'
        #
        file, commit = self.create_file_snapshot(file, app_id = app_id, replace_tags = (attach_type in ('TEMPLATE', 'SCRIPT',)))
        #
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
            'PROMPT -- {}{}: {}'.format(attach_type or 'FILE', ' #{}'.format(commit) if commit else '', file),
            util.replace(self.config.patch_file_link if not self.patch_file_moveup else self.config.patch_file_link_moveup, {
                '#FILE#'        : file.lstrip('/'),
                '#PATCH_CODE#'  : self.patch_code,
            }),
            '',
        ])
        return payload



    def attach_files(self, files, category = '', app_id = None):
        if isinstance(files, str):
            files = util.get_files(files)
        #
        payload = []
        for file in files:
            payload.extend(self.attach_file(file, category = category, app_id = app_id))
        return payload



    def create_apex_snapshots(self, app_id):
        # copy some files even if they did not changed
        if app_id:
            path = self.get_root(app_id)
            for file in self.config.apex_files_copy:
                file = path + file
                if os.path.exists(file):
                    self.create_file_snapshot(file, app_id = app_id, local = True)



    def create_patch_file(self, payload, app_id):
        payload = '\n'.join([line for line in payload if line != None])

        # save in schema patch file
        if not self.patch_dry:
            mode = 'at' if self.patch_file_moveup else 'wt'
            util.write_file(self.patch_file, payload, mode = mode)
        #
        if app_id:
            self.patch_files_apex.append(self.patch_file)
        else:
            self.patch_files.append(self.patch_file)



    def create_file_snapshot(self, file, file_content = None, app_id = None, local = False, replace_tags = False):
        file = file.replace(self.repo_root, '')

        # create folders and copy files
        target_file = '{}/{}'.format(self.patch_folder, file).replace('//', '/')
        commit_id   = ''

        # get real file content, not the git
        if (local or self.args.local or self.config.patch_template_dir in target_file or file.startswith(self.config.patch_scripts_snap)):
            if os.path.exists(file):
                with open(file, 'rt', encoding = 'utf-8') as f:
                    file_content = f.read()
            else:
                commit_hash, commit_id = self.head_commit['id'], self.head_commit_id
                file_content    = self.get_file_from_commit(file, commit = commit_hash)

        # shorten target folder for template files
        if self.config.patch_template_dir in target_file:
            target_file     = target_file.replace(self.config.patch_template_dir, self.config.patch_template_snap)

        # shorten target folder for script files
        if self.config.patch_scripts_dir in target_file:
            target_file     = target_file.replace(self.config.patch_scripts_dir, self.config.patch_scripts_snap)
            file_content    = self.fix_patch_script(file)

        # get file content from commit, not local file
        if file_content == None:
            commit_hash, commit_id = self.get_file_commit(file)
            file_content    = self.get_file_from_commit(file, commit = commit_hash)

        # check for empty file
        if (file_content == None or len(file_content) == 0):
            util.raise_error('FILE IS EMPTY', file)

        # check for merge issues when developer ovelook things
        if '<<<<<<< ' in file_content and '>>>>>>> ' in file_content:
            util.raise_error('UNRESOLVED MERGE ISSUES', file)

        # change page audit columns to current date and patch code, but not for full exports
        if app_id and not (app_id in self.full_exports):
            full_app = self.get_root(app_id, 'f{}.sql'.format(app_id))
            if ('/application/pages/page_' in file or file in full_app):
                file_content = util.replace(file_content,
                    r",p_last_updated_by=>'([^']+)'",
                    ",p_last_updated_by=>'{}'".format(self.patch_code))
                file_content = util.replace(file_content,
                    r",p_last_upd_yyyymmddhh24miss=>'(\d+)'",
                    ",p_last_upd_yyyymmddhh24miss=>'{}'".format(self.config.today_full_raw))

        # replace file content
        file_content = self.replace_tags(file_content)
        if app_id:
            transl = {
                '{$APEX_APP_ID}' : app_id,
            }
            for key, value in transl.items():
                file_content = file_content.replace(key, str(value))

        # make the folder structure more shallow
        if self.config.apex_snapshots:
            target_file = self.get_target_file(target_file)

        # save file
        if not self.patch_dry:
            util.write_file(target_file, file_content)
        #
        return (target_file, commit_id)



    def fix_apex_pages(self, apex_pages):
        payload = [
            'PROMPT --;',
            'PROMPT -- APEX PAGES',
            'PROMPT --;',
            ##'BEGIN',
        ]
        #
        for file in apex_pages:
            page_id = util.extract_int(r'/pages/page_(\d+)\.sql', file)
            ##payload.append('    wwv_flow_imp_page.remove_page(p_flow_id => wwv_flow.g_flow_id, p_page_id => {});'.format(page_id))
        #
        payload.extend([
            ##'END;',
            ##'/',
            ##'--',
        ])

        # recreate requested pages
        for target_file in apex_pages:
            # make the folder structure more shallow
            if self.config.apex_snapshots:
                target_file = self.get_target_file(target_file).replace(self.patch_folder + '/', '')
            #
            payload.append(util.replace(self.config.patch_file_link if not self.patch_file_moveup else self.config.patch_file_link_moveup, {
                '#FILE#'        : target_file,
                '#PATCH_CODE#'  : self.patch_code,
            }))
        #
        return payload



    def get_target_file(self, file):
        file    = file.replace(self.patch_folder, '').strip('/').split('/')
        first   = file.pop(0)
        file    = '{}/{}'.format(first, '.'.join(file))
        file    = '{}/{}/{}'.format(self.patch_folder, self.config.apex_snapshots, file).replace('//', '/')
        return file



    def get_file_commit(self, file):
        last_commit     = ''
        last_commit_id  = None
        #
        for commit_id in sorted(self.all_commits.keys(), reverse = True):
            if not self.args.head and commit_id > self.last_commit_id:
                continue
            #
            commit = self.all_commits[commit_id]
            if file in commit['files'].keys():
                last_commit     = commit['id']
                last_commit_id  = commit_id
                #
                if self.config.patch_skip_merge and commit['summary'].startswith('Merge'):
                    continue    # look for another commit
                break           # commit found
        #
        return last_commit, last_commit_id



    def get_file_from_commit(self, file, commit):
        # convert commit_id (number) to commit hash
        if isinstance(commit, int) and commit in self.all_commits:
            commit = self.all_commits[commit]['id']

        # run command line and capture the output, text file is expected
        return util.run_command('git show {}:{}'.format(commit, file), silent = True)



    def fetch_changes(self):
        self.repo.git.checkout()
        self.repo.git.pull()



    def archive_patches(self, requested = []):
        if requested == []:
            return

        # prepare archive folder if needed
        archive_folder = self.repo_root + self.config.patch_archive
        if not (os.path.exists(archive_folder)):
            os.makedirs(archive_folder)

        # find requested folders to archive
        data = []
        for ref in sorted(self.patches.keys(), reverse = True):
            if ref in requested:
                data.append({
                    'ref'           : ref,
                    'patch_code'    : self.patches[ref]['patch_code'],
                    'folder'        : self.patches[ref]['folder'],
                })
        #
        util.print_header('ARCHIVING PATCHES:')
        util.print_table(data)
        #
        for row in data:
            # zip custom source files first
            source_folder   = self.repo_root + self.config.patch_scripts_dir.replace('/None/', '/{}/'.format(row['patch_code']))
            patch_folder    = self.repo_root + self.config.patch_root + row['folder'] + '/'
            #
            if os.path.exists(source_folder):
                util.create_zip(patch_folder + row['patch_code'], source_folder)
                util.delete_folder(source_folder)

            # zip whole patch folder
            util.create_zip(archive_folder + row['patch_code'], patch_folder)
            util.delete_folder(patch_folder)



    def fix_patch_script(self, file):
        replacements = {}
        buffers, buffer_start, buffer_end = [], None, None
        #
        if not (file in self.script_stats):
            self.script_stats[file] = []

        # get lines from file
        lines = []
        with open(file, 'rt', encoding = 'utf-8') as f:
            lines = f.readlines()

        # find statements
        for i, line in enumerate(lines):
            # replace comments with prompts
            if line.startswith('--'):
                lines[i] = 'PROMPT "{}";\n'.format(line.strip().replace('"', ''))

            # search for the type of command
            if buffers == []:
                first_word = line.strip().split(' ', maxsplit = 1)
                if len(first_word) > 0:
                    first_word = first_word[0].upper()
                    if first_word in ('CREATE', 'DROP', 'ALTER'):
                        statement_type = first_word
                        buffers         = [line]
                        buffer_start    = i
                        buffer_end      = i

            # skip unknown statements
            if len(buffers) == 0:
                continue

            # search for the end of the statement
            if len(buffers) > 0 and i != buffer_start:
                buffers.append(line)
                buffer_end = i
            if not (';' in line):
                continue

            # strip inline comments after statements
            comment = util.extract(r'(;\s*--)', buffers[-1]) or ''   # on last line only and after ';'
            if len(comment) > 0:
                buffers[-1] = buffers[-1].split(comment)[0] + '\n'

            # statement end found, so join the buffers
            statement = ''.join(buffers)
            statement_type, object_type, object_name, operation, cc_name = self.get_object_from_statement(statement)

            # find proper template
            template        = ''
            template_name   = ''
            options         = [
                ' | '.join((statement_type, object_type, operation)),
                ' | '.join((statement_type, operation)),
                operation,
                ' | '.join((statement_type, object_type)),
                statement_type,
            ]
            if statement_type and cc_name != '?':   # skip multicolumn statements
                for name in options:
                    if name in query.templates and len(query.templates[name]) > 0:
                        template        = query.templates[name]
                        template_name   = name
                        break

            # create overview for new patch script file
            self.script_stats[file].append({
                'line'          : (buffer_start + 1),
                'template'      : template_name,
                'statement'     : statement_type,
                'object_type'   : object_type,
                'object_name'   : object_name,
                'col./constr.'  : cc_name,
            })

            # check template for specified statement type
            if template:
                statement = util.replace(template.lstrip(), {
                    '{$HEADER}'         : ' | '.join((statement_type, object_type, object_name, operation, cc_name)).strip(' | '),
                    '{$STATEMENT}'      : statement.replace("'", "''").strip().strip(';').strip(),
                    '{$OBJECT_TYPE}'    : object_type,
                    '{$OBJECT_NAME}'    : object_name,
                    '{$CC_NAME}'        : cc_name,
                })
                replacements[buffer_start] = [buffer_start, buffer_end, statement]

            # prep for next statement
            buffers = []

        # create header with overview
        header  = '--' + util.print_header('SOURCE FILE:', file, capture = True).replace('\n', '\n--  ').rstrip()
        outcome = '\n'
        if len(self.script_stats[file]) > 0:
            outcome = util.print_table(self.script_stats[file], capture = True).replace('\n', '\n--').rstrip().rstrip('--')

        # replace lines in file from the end
        for buffer in sorted(replacements.keys(), reverse = True):
            buffer_start, buffer_end, statement = replacements[buffer]
            for i in reversed(range(buffer_start, buffer_end + 1)):
                if i == buffer_start:
                    lines[i] = statement
                else:
                    lines.pop(i)
        #
        return header + outcome + ''.join(lines)



    def get_object_from_statement(self, statement):
        statement   = util.replace(statement, r'\s+', ' ', flags = re.M).strip().upper()
        statement   = statement.replace(' UNIQUE ', ' ').rstrip(';').strip()
        patterns    = [
            r'(CREATE|DROP|ALTER)\s({})\s["]?[A-Z0-9_-]+["]?\.["]?([A-Z0-9_-]+)["]?',
            r'(CREATE|DROP|ALTER)\s({})\s["]?([A-Z0-9_-]+)["]?',
        ]
        #
        for check_type in sorted(self.config.object_types.keys(), reverse = True):
            for pattern in patterns:
                pattern         = pattern.format(check_type)
                statement_type  = util.extract(pattern, statement, 1)
                #
                if statement_type:
                    object_type     = util.extract(pattern, statement, 2)
                    object_name     = util.extract(pattern, statement, 3)
                    operation       = ''
                    cc_name         = ''

                    # special attention to ALTER TABLE statements
                    if statement_type == 'ALTER' and object_type == 'TABLE':
                        what        = statement.split(object_name, maxsplit = 1)[1].strip().split()
                        operation   = '{} {}'.format(what[0], what[1] if what[1] in ('CONSTRAINT', 'PARTITION',) else 'COLUMN')

                        # get also column or constraint name
                        if what[0] == 'ADD' and not (what[1] in ('CONSTRAINT', 'PARTITION',)):
                            what.insert(1, 'COLUMN')
                            if what[2][0] == '(':
                                what[2] = what[2][1:]           # strip first bracket
                                if what[3][-1:] == ')':
                                    what[3] = what[3][0:-1]     # strip last bracket
                        #
                        if what[0] == 'DROP' and not (what[1] in ('CONSTRAINT', 'PARTITION',)):
                            what.insert(1, 'COLUMN')
                            if what[2][0] == '(' and what[2][-1:] == ')':
                                what[2] = what[2][1:-1]
                        #
                        if len(what) > 2:
                            cc_name = '?' if ('(' in what[2] or ')' in what[2]) else what[2]
                    #
                    return (statement_type, object_type, object_name, operation, cc_name)
        #
        return ('', '', '', '', '')



    def create_install(self):
        util.print_header('INSTALL SCRIPT:')
        #
        files           = self.sort_files_by_deps(util.get_files('{}{}**/*.sql'.format(self.repo_root, self.config.path_objects)))
        files_grouped   = {}
        overview        = {}
        payload         = []

        # sort files into groups
        for group in self.config.patch_map.keys():
            files_grouped[group] = []
            for object_type in self.config.patch_map[group]:
                for file in files:
                    if group.upper() == 'GRANTS' and not file.endswith('/{}.sql'.format(self.info['schema'])):
                        continue
                    #
                    short   = file.replace(self.repo_root, '')
                    obj     = self.repo_files.get(short) or File(file, config = self.config)
                    #
                    if obj.is_object and obj.object_type == object_type:
                        if not (file in files_grouped[group]):
                            files_grouped[group].append(file)
                    #
                    if not (obj['object_type'] in overview):
                        overview[obj['object_type']] = []
                    if not (short in overview[obj['object_type']]):
                        overview[obj['object_type']].append(short)

        # create overview
        payload.append('--')
        for object_type in sorted(overview.keys()):
            if object_type and object_type != 'GRANT':
                payload.append('-- {}{}'.format((object_type + ' ').ljust(20, '.'), ' {}'.format(len(overview[object_type])).rjust(6, '.')))

        # init files
        payload.extend([
            '--',
            '',
            '--',
            '-- INIT',
            '--',
        ])
        for file in self.get_template_files('db_init'):
            payload.append('@"../{}";'.format(file))

        # files per groups
        for group in self.config.patch_map.keys():
            files = files_grouped[group]
            if len(files) == 0:
                continue

            # (2) before template
            if self.config.patch_add_templates:
                for file in self.get_template_files(group + self.postfix_before):
                    payload.append('@"../{}";'.format(file))

            # (1) files
            payload.extend([
                '',
                '--',
                '-- {}'.format(group.upper()),
                '--',
            ])
            for file in files:
                payload.append('@"./{}";'.format(file.replace(self.repo_root + self.config.path_objects, '')))

            # (2) after template
            if self.config.patch_add_templates:
                for file in self.get_template_files(group + self.postfix_after):
                    payload.append('@"../{}";'.format(file))

        # exit files
        payload.extend([
            '',
            '--',
            '-- FINISH',
            '--',
        ])
        for file in self.get_template_files('db_end'):
            payload.append('@"../{}";'.format(file))

        # show install script on screen and save it to file
        file    = self.repo_root + self.config.path_objects + 'INSTALL.sql'
        payload = '\n'.join(payload) + '\n'
        util.write_file(file, payload)
        print(payload)



    def get_table_for_diff(self, payload):
        payload = payload.split(';')[0]
        payload = payload.split('\nPARTITION BY')[0]
        payload = payload.split('\n')
        #
        for i, line in enumerate(payload):
            line = util.replace(line, r'\s+', ' ')

            # remove auto sequence (identity)
            if ' GENERATED BY ' in line:
                line = line.split(' GENERATED BY')[0] + (' NOT NULL ' if ' NOT NULL' in line else '').rstrip() + ','

            # rename constraints
            constraint = util.extract(r'CONSTRAINT ([^\s]+)', line)
            if constraint:
                line = line.replace(constraint, constraint + '$#')

            # rename table
            table = util.extract(r'TABLE ([^\s]+)', line)
            if table:
                line = line.replace(table, table + '$#')

            # store udpated line
            payload[i] = line
        #
        return '\n'.join(payload)



    def get_table_diff(self, file, object_name, version_src, version_trg):
        # compare only tables
        table_folder, table_ext = self.config.object_types['TABLE']
        if not (self.config.path_objects in file and table_folder in file and file.endswith(table_ext)):
            return ''
        #
        if not (version_src in self.all_commits.keys()):
            return ''
        #
        source_file = self.get_file_from_commit(file, commit = version_src)
        if not source_file:
            return ''
        #
        source_obj = self.get_table_for_diff(source_file)
        target_obj = self.get_table_for_diff(self.get_file_from_commit(file, commit = version_trg))
        if source_obj == target_obj:
            return ''

        # create source table
        source_obj      = source_obj.replace('$#', '$1')
        source_table    = object_name.upper() + '$1'
        #
        try:
            self.conn.drop_object('TABLE', source_table)
            self.conn.execute(source_obj)
        except:
            util.print_warning(
                'DIFF SOURCE TABLE FAIL: {}'.format(object_name), [
                    'YOU HAVE ERRORS IN #{} COMMIT'.format(version_src),
                ])
            self.conn.drop_object('TABLE', source_table)
            return ''

        # create target table
        target_obj      = target_obj.replace('$#', '$2')
        target_table    = object_name.upper() + '$2'
        #
        try:
            self.conn.drop_object('TABLE', target_table)
            self.conn.execute(target_obj)
        except:
            util.print_warning(
                'DIFF TARGET TABLE FAIL: {}'.format(object_name), [
                    'YOU HAVE ERRORS IN #{} COMMIT'.format(version_trg),
                ])
            self.conn.drop_object('TABLE', target_table)
            return ''

        # compare tables
        result  = str(self.conn.fetch_clob_result(query.generate_table_diff, source_table = source_table, target_table = target_table))
        lines   = []
        for line in result.splitlines():
            line = line.strip()
            line = util.replace(line, r'("[^"]+"\.)', '')  # remove schema
            #
            for object_name in re.findall(r'"[^"]+"', line):
                line = line.replace(object_name, object_name.replace('"', '').lower())
            #
            lines.append(line)

        # remove tables
        self.conn.drop_object('TABLE', source_table)
        self.conn.drop_object('TABLE', target_table)
        #
        return lines



    def implode_folder(self, folder):
        if os.path.exists(folder):
            util.print_header('IMPLODE FOLDER')
            #
            payload = ''
            for file in util.get_files(folder + '/*.*'):
                print('  - {}'.format(file))
                payload += open(file, 'rt', encoding = 'utf-8').read() + '\n'
            print()
            #
            merged_file = folder.replace('\\', '/').rstrip('/') + '.sql'
            util.write_file(merged_file, payload)



if __name__ == "__main__":
    Patch()

