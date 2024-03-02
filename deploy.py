# coding: utf-8
import sys, os, re, argparse, glob, timeit
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

class Deploy(config.Config):

    def __init__(self, parser, ignore_timer = False):
        super().__init__(parser, ignore_timer)

        # process arguments and reinitiate config
        util.assert_(self.args.target, 'MISSING ARGUMENT: TARGET ENV')
        #
        self.patch_env          = self.args.target
        self.patch_code         = self.args.patch
        self.patch_folder       = ''
        self.patch_ref          = self.args.get('ref', None)
        self.info.branch        = self.args.branch or self.info.branch or self.repo.active_branch
        #
        self.init_config()
        self.init_connection(env_name = self.patch_env)

        # internal variables
        self.patches            = {}
        self.available_ref      = {}
        self.available_show     = []
        self.patch_found        = []
        self.patch_commits      = {}
        self.deploy_plan        = []
        self.deploy_schemas     = {}
        self.deploy_conn        = {}
        self.splitter           = '__'      # in deploy logs in between env, date, schema, status
        self.logs_prefix        = '{}/LOGS_{}'
        #
        self.find_folder()
        if __name__ == "__main__":
            self.deploy_patch()



    def deploy_patch(self):
        self.check_folder()
        self.create_plan()
        self.check_connections()

        # run the target script(s) and spool the logs
        util.print_header('PATCHING PROGRESS AND RESULTS:')

        # create folder for logs
        if not os.path.exists(self.log_folder):
            os.makedirs(self.log_folder)

        # generate table headers before we know size of the data
        max_file_len = 0
        for plan in self.deploy_plan:
            max_file_len = max(max_file_len, len(plan['file']))
        #
        map = {
            'order'     : 5,
            'file'      : max_file_len,
            'output'    : 6,
            'status'    : 7,
            'timer'     : 5,
        }
        util.print_table([], columns = map)
        #
        for order, plan in enumerate(self.deploy_plan):
            start       = timeit.default_timer()
            schema      = plan['schema']
            file        = plan['file']
            full        = self.patch_path + file
            conn        = self.deploy_conn[schema]

            # check if file exists
            if not os.path.exists(full):
                util.raise_error('FILE MISSING', full)

            # cleanup the script from comments, fix prompts
            payload = []
            with open(full, 'rt') as f:
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
            output = conn.sqlcl_request(payload)

            # search for the success prompt at last few lines
            lines = output.splitlines()
            success = ''
            for line in lines[-10:]:                # last 10 lines
                if line.startswith('-- SUCCESS'):   # this is in patch.py
                    success = True
                    break

            # prep results for the template
            results = {
                'order'     : order + 1,
                'file'      : file,
                'output'    : len(lines),
                'status'    : 'SUCCESS' if success else 'ERROR',
                'timer'     : int(round(timeit.default_timer() - start + 0.5, 0)),  # ceil
            }

            # rename log to reflect the result in the file name
            original    = full.replace('.sql', '.log')
            renamed     = '{}/{} {} [{}].log'.format(self.log_folder, file.replace('.sql', ''), self.config.today_deploy, results['status'])
            #
            if os.path.exists(original):
                os.rename(original, renamed)

            # show progress
            util.print_table([results], columns = map, right_align = ['order', 'output', 'timer'], no_header = True)
        print()



    def find_folder(self):
        # identify patch folder
        for ref, patch in enumerate(sorted(glob.glob(self.repo_root + self.config.patch_root + '**'), reverse = True), start = 1):
            self.patches[ref] = patch
            if self.patch_ref != None:
                if self.patch_ref == ref:
                    self.patch_found.append(patch)
            elif self.patch_code != None:
                if self.patch_code in patch:
                    self.patch_found.append(patch)

            # pass all folders for Patch script
            if __name__ != "__main__":
                if self.patch_ref == None:
                    self.patch_found.append(patch)

        # get patches for checks
        self.get_available_patches()

        # set values
        if len(self.patch_found) > 0:
            self.patch_folder   = self.patch_found[0].replace(self.repo_root + self.config.patch_root, '')
            self.patch_full     = self.patch_found[0]
            self.patch_short    = self.patch_full.replace(self.repo_root + self.config.patch_root, '')
            self.patch_path     = self.repo_root + self.config.patch_root + self.patch_folder + '/'
            self.log_folder     = self.logs_prefix.format(self.patch_path, self.patch_env)



    def check_folder(self):
        if len(self.patch_found) != 1:
            util.print_header('AVAILABLE PATCHES:', self.patch_env)
            util.print_table(self.available_show)
            #
            util.print_header('SELECT PATCH YOU WANT TO DEPLOY')
            util.print_help('use -patch UNIQUE_NAME     to select patch by name')
            util.print_help('use -ref #                 to select patch by ref number in table above')
            print()
            util.quit()

        # check status of requested patch, search for ref#
        ref = self.patch_ref or list(self.patches.keys())[list(self.patches.values()).index(self.patch_found[0])]
        #
        if self.available_ref[ref]['result'] == 'SUCCESS' and not self.args.force:
            util.raise_error('PATCH ALREADY DEPLOYED',
                'use -force flag if you want to redeploy patch anyway')

        # check if there is a newer patch deployed than requested one
        found_newer = False
        new_patches = []
        conflicted  = []
        #
        for i in reversed(range(1, ref + 1)):
            info = self.available_ref[i]
            new_patches.append({
                'ref'           : info['ref'],
                'patch_name'    : info['patch_name'],
                'files'         : len(info['files']),
                'deployed_at'   : info['deployed_at'],
                'result'        : info['result'],
            })

            # for patches below
            if i < ref:
                # also check existence of log files
                if info['deployed_at'] != None and info['deployed_at'] != '':
                    found_newer = True

                    # check if files from requested patch are in the following patches
                    for file in self.available_ref[i]['files']:
                        if file in self.available_ref[ref]['files'] and not (file in conflicted):
                            conflicted.append(file)

        # show requested patch but also newer patches
        util.print_header('REQUESTED PATCH:', '{} ({})'.format(self.patch_short, ref))
        util.print_table(new_patches)

        # show list of conflicted files
        if len(conflicted) > 0:
            util.print_header('CONFLICTED FILES:')
            for file in conflicted:
                print('  - {}'.format(file).replace(' ./', ' '))
            print()

        # show warning
        if found_newer and not self.args.force:
            util.raise_error('REQUESTED PATCH TOO OLD',
                'there is a newer patch deployed, you might lose things...',
                'use -force flag if you want to redeploy anyway')



    def get_available_patches(self):
        for ref in sorted(self.patches.keys(), reverse = True):
            patch           = self.patches[ref]
            count_files     = []
            count_commits   = []
            buckets         = {}    # use buckets to identify the most recent results

            # get some numbers from patch root files
            for file in glob.glob(patch + '/*.sql'):
                # get list of commits referenced by file
                count_commits.extend(self.get_file_commits(file))

                # get number of referenced files
                count_files.extend(self.get_file_references(file))

            # deduplicate
            count_files     = list(set(count_files))
            count_commits   = list(set(count_commits))

            # find more details from log names
            for file in glob.glob(self.logs_prefix.format(patch, self.patch_env) + '/*.log'):
                info        = os.path.splitext(os.path.basename(file))[0].split(' ')
                schema      = info.pop(0)
                result      = info.pop(-1).replace('[', '').replace(']', '')
                deployed    = util.replace(' '.join(info).replace('_', ' '), '( \d\d)[-](\d\d)$', '\\1:\\2')  # fix time
                #
                if not (deployed in buckets):
                    buckets[deployed] = result
                else:
                    buckets[deployed] = result if result == 'ERROR' else min(buckets[deployed], result)
            #
            last_deployed   = max(buckets.keys())     if buckets != {} else ''
            last_result     = buckets[last_deployed]  if buckets != {} else ''

            # create a row in table
            self.available_ref[ref] = {
                'ref'           : ref,
                'patch_name'    : patch.replace(self.repo_root + self.config.patch_root, ''),
                'files'         : count_files,
                'commits'       : count_commits,
                'deployed_at'   : last_deployed,
                'result'        : last_result,
            }

            # show only matches
            if (self.patch_code == None or self.patch_code in patch):
                self.available_show.append({**self.available_ref[ref], **{'files': len(count_files)}})



    def create_plan(self):
        # create deployment plan
        for order, file in enumerate(sorted(glob.glob(self.patch_full + '/*.sql'))):
            full    = file
            file    = os.path.basename(file.replace(self.patch_full, ''))
            #
            schema_with_app  = os.path.splitext(file)[0]
            schema_with_app  = util.replace(schema_with_app, '^[0-9]+[_-]*', '')    # remove leading numbers
            #
            target_schema, app_id, _ = (schema_with_app + '..').split('.', maxsplit = 2)
            #
            if not (target_schema in self.deploy_schemas):
                self.deploy_schemas[target_schema] = []
            self.deploy_schemas[target_schema].append(order)
            #
            self.deploy_plan.append({
                'order'     : order + 1,
                'file'      : file,
                'schema'    : target_schema,
                'app_id'    : app_id,
                'files'     : len(self.get_file_references(full)),
            })
        #
        util.print_header('PATCH DETAILS:')
        util.print_table(self.deploy_plan, columns = ['order', 'file', 'schema', 'app_id', 'files'], right_align = ['app_id'])



    def get_file_references(self, file):
        files = []
        with open(file, 'rt') as f:
            for line in f.readlines():
                if line.startswith('@'):
                    if '"' in line:
                        file = line.split('"', maxsplit = 2)[1]
                    else:
                        file = line.replace('@', '').split(' ')[0]
                    files.append(file)
        return files



    def get_file_commits(self, file):
        commits = []
        with open(file, 'rt') as f:
            extracting = False
            for line in f.readlines():
                if line.startswith('-- COMMITS:'):      # find start of commits
                    extracting = True
                #
                if extracting:
                    if line.strip() == '--':            # find end of commits
                        break

                    # find commit number
                    search = re.search('^[-][-]\s+(\d+)[)]?\s', line)
                    if search:
                        commits.append(int(search.group(1)))
        return commits



    def check_connections(self):
        # connect to all target schemas first so we know we can deploy all scripts
        util.print_header('CONNECTING TO {}:'.format(self.patch_env))
        for schema in self.deploy_schemas.keys():
            self.init_connection(env_name = self.patch_env, schema_name = schema)
            print('  {} '.format(schema).ljust(72, '.') + ' ', end = '', flush = True)
            self.deploy_conn[schema] = self.db_connect(ping_sqlcl = True, silent = True)
            self.deploy_conn[schema].sqlcl_root = self.patch_path
            print('OK')
        print()



if __name__ == "__main__":
    # parse arguments
    parser = argparse.ArgumentParser()

    # actions and flags
    parser.add_argument('-debug',       help = 'Turn on the debug/verbose mode',    default = False, nargs = '?', const = True)
    parser.add_argument('-key',         help = 'Key or key location to encypt passwords')
    parser.add_argument('-schema',      help = 'Schema/connection name')
    #
    parser.add_argument('-patch',       help = 'Patch code (name for the patch files)')
    parser.add_argument('-ref',         help = 'Reference number (see list of available patches)', type = int)
    parser.add_argument('-target',      help = 'Target environment')
    parser.add_argument('-force',       help = 'Force deployment',                          default = False, nargs = '?', const = True)
    #
    Deploy(parser)

