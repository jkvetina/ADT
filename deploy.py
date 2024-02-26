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
        self.patch_folder       = self.args.folder
        self.info.branch        = self.args.branch or self.info.branch or self.repo.active_branch
        #
        self.init_config()

        #
        self.deploy_plan        = []
        self.deploy_schemas     = {}
        self.deploy_conn        = {}
        self.splitter           = '__'
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
            log_file    = ''    # to extract log name from spool line
            payload     = []    # for cleaned lines
            #
            with open(full, 'rt') as f:
                for line in f.readlines():
                    line = line.strip()
                    if line.startswith('--') or line == '':
                        continue
                    if line.startswith('PROMPT'):
                        line = line.replace('PROMPT --;', 'PROMPT ---;')

                    # change log name
                    if line.startswith('SPOOL "'):
                        split = line.split('"')
                        log_file = split[1].replace('./', './{}{}{}{}'.format(self.patch_env, self.splitter, self.config.today_deploy, self.splitter))
                        line = '{}"{}"{}'.format(split[0], log_file, split[2])
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
            log_file = log_file.replace('./', self.patch_path)
            os.rename(log_file, log_file.replace('.log', '{}{}.log'.format(self.splitter, results['status'])))

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
        found_folders = []
        patches = sorted(glob.glob(self.repo_root + self.config.patch_root + '**'))
        for patch in patches:
            if self.patch_folder != None and patch == self.patch_path:
                found_folders.append(patch)
            elif self.patch_code != None and self.patch_code in patch:
                found_folders.append(patch)
        #
        folders_count = len(found_folders)
        if folders_count == 1:
            self.patch_folder = found_folders[0].replace(self.repo_root + self.config.patch_root, '')
        #
        else:
            data = []
            for patch in patches:
                deployed    = ''
                result      = ''
                schemas     = []

                # find more details from log names
                for file in glob.glob(patch + '/*.log'):
                    info = os.path.splitext(os.path.basename(file))[0].split(self.splitter)
                    if len(info) == 4:
                        env, date, schema, status = info
                        if env != self.patch_env:
                            continue
                        deployed    = date.replace('_', ' ')
                        result      = status if (result == '' or status == 'ERROR') else result
                        #
                        if not (schema in schemas):
                            schemas.append(schema)
                #
                data.append({
                    'patch_name'    : patch.replace(self.repo_root + self.config.patch_root, ''),
                    'schemas'       : len(schemas),
                    'deployed_at'   : deployed,
                    'result'        : result,
                })
            #
            util.print_header('AVAILABLE PATCHES:', self.patch_env)
            util.print_table(data)
            #
            if len(found_folders) > 1:
                util.raise_error('TOO MANY PATCHES FOUND!', '  - add specific folder name\n')
            else:
                util.raise_error('NO PATCH FOUND!')

        # set values
        self.patch_full     = found_folders[0]
        self.patch_short    = self.patch_full.replace(self.repo_root + self.config.patch_root, '')
        self.patch_path     = self.repo_root + self.config.patch_root + self.patch_folder + '/'



    def create_plan(self):
        self.template_hack = [
            ['output',  '{1}___'],
            ['status',  '{2}____'],
            ['timer',   '{3}__']
        ]

        # create deployment plan
        for order, file in enumerate(sorted(glob.glob(self.patch_full + '/*.sql'))):
            full    = file
            file    = os.path.basename(file.replace(self.patch_full, ''))
            schema  = util.replace(os.path.splitext(file)[0], '^[0-9]+[_-]*', '')       # remove leading numbers
            #
            if not (schema in self.deploy_schemas):
                self.deploy_schemas[schema] = []
            self.deploy_schemas[schema].append(order)
            #
            plan = {
                'order'     : order + 1,
                'schema'    : schema,
                'file'      : file,
                'files'     : self.get_file_references(full),
            }
            for column, content in self.template_hack:
                plan[column] = content
            self.deploy_plan.append(plan)
        #
        util.print_header('PATCH FOUND:', self.patch_short)
        util.print_table(self.deploy_plan, columns = ['order', 'schema', 'file', 'files'])



    def get_file_references(self, file):
        files = 0
        with open(file, 'rt') as f:
            for line in f.readlines():
                if line.startswith('@'):
                    files += 1
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

