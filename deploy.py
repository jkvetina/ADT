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

    def __init__(self, parser):
        super().__init__(parser)

        # process arguments and reinitiate config
        util.assert_(self.args.target, 'MISSING ARGUMENT: TARGET ENV')
        #
        self.patch_env          = self.args.target
        self.patch_code         = self.args.patch
        self.patch_folder       = ''
        self.info.branch        = self.args.branch or self.info.branch or self.repo.active_branch
        #
        self.init_config()
        self.init_connection(env_name = self.patch_env)

        # internal variables
        self.patches            = {}
        self.available_ref      = {}
        self.available_show     = []
        self.deploy_plan        = []
        self.deploy_schemas     = {}
        self.deploy_conn        = {}
        self.splitter           = '__'      # in deploy logs in between env, date, schema, status
        #
        self.deploy_patch()



    def deploy_patch(self):
        self.find_folder()
        self.create_plan()
        self.check_connections()

        # run the target script(s) and spool the logs
        util.print_header('PATCHING PROGRESS AND RESULTS:')
        template = util.print_table(self.deploy_plan, capture = True).splitlines()
        print(template.pop(0))  # empty line
        print(template.pop(0))  # headers
        print(template.pop(0))  # splitter
        #
        for plan in self.deploy_plan:
            start   = timeit.default_timer()
            schema  = plan['schema']
            file    = plan['file']
            full    = self.patch_path + file
            conn    = self.deploy_conn[schema]

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
                'output'    : len(lines),
                'status'    : 'SUCCESS' if success else 'ERROR',
                'timer'     : int(round(timeit.default_timer() - start + 0.5, 0)),  # ceil
            }

            # rename log to reflect the result in the file name
            original    = full.replace('.sql', '.log')
            renamed     = full.replace('.sql', '|{}|{}|{}.log'.format(self.patch_env, self.config.today_deploy, results['status']))
            renamed     = renamed.replace('|', self.splitter)
            #
            if os.path.exists(original):
                os.rename(original, renamed)

            # show progress
            out = template.pop(0)
            for column, content in self.template_hack:
                width   = len(content)
                value   = results[column]
                out     = out.replace(content, value.ljust(width) if isinstance(value, str) else str(value).rjust(width))
            #
            print(out)
        print()



    def find_folder(self):
        # identify patch folder
        patch_found = []
        for ref, patch in enumerate(sorted(glob.glob(self.repo_root + self.config.patch_root + '**'), reverse = True), start = 1):
            if self.patch_code != '' and not (self.patch_code in patch):
                continue
            #
            self.patches[ref] = patch
            if self.args.ref != None:
                if self.args.ref == ref:
                    patch_found.append(patch)
            elif self.patch_code != '':
                if self.patch_code in patch:
                    patch_found.append(patch)

        # get patches for checks
        self.get_available_patches()
        #
        if len(patch_found) != 1:
            util.print_header('AVAILABLE PATCHES:', self.patch_env)
            util.print_table(self.available_show)
            #
            util.print_header('SELECT PATCH YOU WANT TO DEPLOY')
            print('  - use can either use       : -patch NAME')
            print('  - or pass reference number : -ref #')
            print()
            util.quit()

        # check status of requested patch, search for ref#
        ref = self.args.ref or list(self.patches.keys())[list(self.patches.values()).index(patch_found[0])]
        #
        if self.available_ref[ref]['result'] == 'SUCCESS' and not self.args.force:
            util.raise_error('PATCH ALREADY DEPLOYED', '  - use -force flag if you want to redeploy anyway')

        # check if there is a newer patch deployed than requested one
        found_newer = False
        conflicted  = []
        #
        for i in reversed(range(1, ref)):
            found_newer = True
            for file in self.available_ref[i]['files']:
                if file in self.available_ref[ref]['files'] and not (file in conflicted):
                    conflicted.append(file)

        # show list of conflicted files
        if len(conflicted) > 0:
            util.print_header('CONFLICTED FILES:')
            for file in conflicted:
                print('  - {}'.format(file))
            print()
        #
        if found_newer:
            util.raise_error('REQUESTED PATCH TOO OLD',
                '  - there is a newer patch deployed, you might lose things...\n' +
                '  - use -force flag if you want to redeploy anyway')

        # set values
        self.patch_folder   = patch_found[0].replace(self.repo_root + self.config.patch_root, '')
        self.patch_full     = patch_found[0]
        self.patch_short    = self.patch_full.replace(self.repo_root + self.config.patch_root, '')
        self.patch_path     = self.repo_root + self.config.patch_root + self.patch_folder + '/'



    def get_available_patches(self):
        for ref in sorted(self.patches.keys(), reverse = True):
            patch       = self.patches[ref]
            files       = []
            deployed    = ''
            result      = ''

            # get number of files referenced in the patch root files
            for file in glob.glob(patch + '/*.sql'):
                files.extend(self.get_file_references(file))
            files = list(set(files))    # deduplicate

            # find more details from log names
            for file in glob.glob(patch + '/*.log'):
                info = os.path.splitext(os.path.basename(file))[0].split(self.splitter)
                if len(info) == 4:
                    env, date, schema, status = info
                    if env != self.patch_env:
                        continue
                    #
                    deployed    = util.replace(date.replace('_', ' '), '( \d\d)[-](\d\d)$', '\\1:\\2')  # fix time
                    result      = status if (result == '' or status == 'ERROR') else result

            # create a row in table
            self.available_ref[ref] = {
                'ref'           : ref,
                'patch_name'    : patch.replace(self.repo_root + self.config.patch_root, ''),
                'files'         : files,
                'deployed_at'   : deployed,
                'result'        : result,
            }
            self.available_show.append({**self.available_ref[ref], **{'files': len(files)}})



    def create_plan(self):
        self.template_hack = [
            ['output',  '{1}___'],      # to block the minimum column width
            ['status',  '{2}____'],
            ['timer',   '{3}__']
        ]

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
            plan = {
                'order'     : order + 1,
                'file'      : file,
                'schema'    : target_schema,
                'app_id'    : app_id,
                'files'     : len(self.get_file_references(full)),
            }
            for column, content in self.template_hack:
                plan[column] = content
            self.deploy_plan.append(plan)
        #
        util.print_header('PATCH FOUND:', self.patch_short)
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

