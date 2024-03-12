# coding: utf-8
import sys, os, argparse, shutil, datetime, timeit
#
import config
from lib import util
from lib import queries_export_apex as query
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

class Export_APEX(config.Config):

    def __init__(self, parser):
        super().__init__(parser)

        # setup env and paths
        self.app_folder         = '$APP_FOLDER/'
        self.target_root        = self.repo_root + self.config.path_apex
        self.target_path        = self.target_root + self.app_folder        # raplace later
        self.target_rest        = self.config.apex_path_rest
        self.target_files       = self.config.apex_path_files
        self.target_files_ws    = self.config.apex_path_files_ws
        #
        self.init_config()
        self.conn = self.db_connect(ping_sqlcl = False)

        # make sure we have the temp folder ready
        if os.path.exists(self.config.sqlcl_root):
            shutil.rmtree(self.config.sqlcl_root, ignore_errors = True, onerror = None)
            os.makedirs(self.config.sqlcl_root, exist_ok = True)

        # for workspace and apps lists
        self.apex_apps      = {}
        self.apex_ws        = {}
        self.comp_changed   = []  # components changes recently

        # scope
        self.arg_workspace  = self.args.ws      or self.config.default_workspace
        self.arg_group      = self.args.group   or self.config.default_app_group
        self.arg_apps       = self.args.app     or self.config.default_apps
        self.today          = str(datetime.datetime.today() - datetime.timedelta(days = self.args.recent - 1))[0:10]
        #
        self.actions = {
            'recent'    : False,
            'full'      : False,
            'split'     : False,
            'embedded'  : False,
            'rest'      : False,
            'files'     : False,
            'files_ws'  : False,
        }
        self.parse_actions()

        # show matching apps every time
        self.get_applications()

        # for each requested app
        for app_id in sorted(self.apex_apps.keys()):
            # show recent changes
            if self.config.apex_show_recent and self.args.recent > 0:
                self.show_recent_changes(app_id)

            util.print_header('APP {}/{}, EXPORTING:'.format(app_id, self.apex_apps[app_id]['app_alias']))
            self.conn.execute(query.apex_security_context, app_id = app_id)

            # create folders
            for dir in ['', self.target_rest, self.target_files]:
                dir = os.path.dirname(self.get_root(app_id, dir))
                os.makedirs(dir, exist_ok = True)

            # export changed objects only and exit
            if self.actions['recent']:
                start = timeit.default_timer()
                util.print_now('  CHANGED COMPONENTS ...')
                self.export_changed(app_id)
                self.move_files(app_id)
                timer = int(round(timeit.default_timer() - start + 0.5, 0))
                print(' {}'.format(timer))
                break

            # full export
            if self.actions['full']:
                start = timeit.default_timer()
                util.print_now('  FULL APP EXPORT ...')
                self.export_full(app_id)
                timer = int(round(timeit.default_timer() - start + 0.5, 0))
                print(' {}'.format(timer))

            # split export
            if self.actions['split']:
                start = timeit.default_timer()
                util.print_now('  SPLIT COMPONENTS ...')
                self.export_split(app_id)
                timer = int(round(timeit.default_timer() - start + 0.5, 0))
                print(' {}'.format(timer))

            # export embedded code report
            if self.actions['embedded']:
                start = timeit.default_timer()
                util.print_now('  EMBEDDED CODE REPORT ...')
                self.export_embedded(app_id)
                timer = int(round(timeit.default_timer() - start + 0.5, 0))
                print(' {}'.format(timer))

            # export REST services
            if self.actions['rest']:
                start = timeit.default_timer()
                util.print_now('  REST SERVICES ...')
                self.export_rest(app_id)
                timer = int(round(timeit.default_timer() - start + 0.5, 0))
                print(' {}'.format(timer))

            # export application files
            if self.actions['files']:
                start = timeit.default_timer()
                util.print_now('  APPLICATION FILES ...')
                self.export_files(app_id)
                timer = int(round(timeit.default_timer() - start + 0.5, 0))
                print(' {}'.format(timer))

            self.move_files(app_id)

        # export workspace files
        if self.actions['files_ws']:
            start = timeit.default_timer()
            util.print_now('  WORKSPACE FILES ...')
            self.export_files(app_id = 0)
            timer = int(round(timeit.default_timer() - start + 0.5, 0))
            print(' {}'.format(timer))

        print()



    def parse_actions(self):
        # check what exactly we will be exporting
        for arg_name in self.actions.keys():
            if self.args.get('no' + arg_name, ''):  # keep default False
                continue
            if self.args.get(arg_name, ''):         # proceed
                self.actions[arg_name] = True
                continue
            if self.config.get('apex_export_' + arg_name, '') and not self.args.only:
                self.actions[arg_name] = True
                continue
        #
        self.actions['recent'] = (self.actions['recent'] and self.args.recent > 0 and not self.actions['split'])



    def get_root(self, app_id, folders = ''):
        app_alias   = self.apex_apps[app_id]['app_alias']
        app_folder  = '/{}_{}/'.format(app_id, app_alias)
        path        = self.target_path.replace(self.app_folder, app_folder) + folders
        #
        return path.replace('//', '/')



    def get_applications(self):
        # get list of applications
        args = {
            'owner'     : self.info.schema,
            'workspace' : self.arg_workspace,
            'group_id'  : self.arg_group,
            'app_id'    : '|'.join(str(x) for x in self.arg_apps),
        }
        #
        groups = {}
        for row in self.conn.fetch_assoc(query.apex_applications, **args):
            # split to groups for screen output
            row.app_group = row.app_group or '-'
            if not (row.app_group in groups):
                groups[row.app_group] = []
            groups[row.app_group].append({
                'app_id'        : row.app_id,
                'alias'         : row.app_alias,
                'name'          : row.app_name,
                'pages'         : row.pages,
                'updated_at'    : row.updated_at,
            })
            #
            if not (row.workspace in self.apex_ws):
                self.apex_ws[row.workspace] = {}
            if not (row.app_group in self.apex_ws[row.workspace]):
                self.apex_ws[row.workspace][row.app_group] = {}
            #self.apex_ws[row.workspace][row.app_group][row.app_id] = row
            self.apex_ws[row.workspace][row.app_id] = row
            self.apex_apps[row.app_id] = row

        # show groups
        for group, rows in groups.items():
            util.print_header('APEX APPLICATIONS:', group)
            util.print_table(rows)



    def show_recent_changes(self, app_id):
        alias = self.apex_apps[app_id]['app_alias']
        util.print_header('APP {}/{}, CHANGES SINCE {}'.format(app_id, alias, self.today))
        #
        output  = self.execute_request('apex export -applicationid {$APP_ID} -list -changesSince {$TODAY}', app_id)
        data    = util.parse_table(output.splitlines()[5:])
        #
        for i, row in enumerate(data):
            self.comp_changed.append(row['id'])
            if row['id'].startswith('PAGE:'):
                page_id = row['id'].replace('PAGE:', '')
                data[i]['name'] = data[i]['name'].replace('{}. '.format(page_id), '')
            else:
                data[i]['id']   = data[i]['id'].split(':')[0]
            #
            data[i]['id']   = util.get_string(data[i]['id'],    16)
            data[i]['name'] = util.get_string(data[i]['name'],  36)
        #
        util.print_table(data)



    def export_changed(self, app_id):
        output = self.execute_request('apex export -applicationid {$APP_ID} -skipExportDate -expComments -expComponents "{$COMPONENTS}" -split', app_id)

        # remove some extra files
        source_dir = '{}f{}'.format(self.config.sqlcl_root, app_id)
        for pattern in self.config.apex_files_ignore:
            for file in util.get_files(source_dir + pattern):
                os.remove(file)
        #
        return output



    def export_full(self, app_id):
        return self.execute_request('apex export -applicationid {$APP_ID} -nochecksum -skipExportDate -expComments -expTranslations', app_id)



    def export_split(self, app_id):
        output = self.execute_request('apex export -applicationid {$APP_ID} -nochecksum -skipExportDate -expComments -expTranslations -expType APPLICATION_SOURCE{$FORMAT_JSON}{$FORMAT_YAML} -split', app_id)

        # cleanup target directory before moving new files there
        target_dir = self.get_root(app_id, 'application/')
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir, ignore_errors = True, onerror = None)
        #
        return output



    def export_embedded(self, app_id):
        output = self.execute_request('apex export -applicationid {$APP_ID} -nochecksum -expType EMBEDDED_CODE', app_id)

        # move to proper folder
        source_dir = '{}f{}/embedded_code/'.format(self.config.sqlcl_root, app_id)
        target_dir = self.get_root(app_id, 'embedded_code/')
        #
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir, ignore_errors = True, onerror = None)
        #
        if os.path.exists(source_dir):
            for file in util.get_files(source_dir + '/pages/p*.*'):
                os.rename(file, file.replace('/pages/p', '/pages/page_'))
            #
            shutil.copytree(source_dir, target_dir, dirs_exist_ok = True)
            shutil.rmtree(source_dir, ignore_errors = True, onerror = None)
        #
        return output



    def export_rest(self, app_id):
        return self.execute_request('apex rest', app_id)



    def export_files(self, app_id):
        # get target folder
        if app_id == 0:  # workspace files
            target_dir = self.target_root + self.target_files_ws
        else:
            target_dir = self.get_root(app_id, self.target_files)

        # delete targer folders first
        shutil.rmtree(target_dir, ignore_errors = True, onerror = None)

        # create files
        for row in self.conn.fetch_assoc(query.apex_files, app_id = app_id):
            file = target_dir + row.filename
            os.makedirs(os.path.dirname(file), exist_ok = True)
            #
            with open(file, 'wb') as w:
                w.write(row.f.read())   # blob_content



    def move_files(self, app_id):
        source_dir = '{}f{}/'.format(self.config.sqlcl_root, app_id)
        target_dir = self.get_root(app_id)

        # move readable files
        for file in util.get_files(source_dir + 'readable/**/*.*'):
            target = file

            # application file close to app full export
            if '/readable/application/f{}.'.format(app_id) in file:
                target = file.replace('/readable/application/', '/')

            # move page files close to pages
            if '/readable/application/page_groups.' in file:
                target = file.replace('/application/', '/application/pages/')
            #
            if '/readable/application/pages/p' in file:
                target = file.replace('/pages/p', '/pages/page_')

            # workspace files
            if '/readable/workspace/' in file:
                target = file.replace('/readable/', '/../')

            # move readable files close to original files
            if os.path.exists(file):
                target = target.replace(source_dir, target_dir).replace('/readable/', '/')
                os.makedirs(os.path.dirname(target), exist_ok = True)
                os.rename(file, target)

        # remove readable folder
        if os.path.exists(source_dir + 'readable/'):
            shutil.rmtree(source_dir + 'readable/', ignore_errors = True, onerror = None)

        # move workspace files to workspace folder
        for file in util.get_files(source_dir + 'workspace/**/*.*'):
            target = file.replace('/f{}/workspace/'.format(app_id), '/workspace/')
            os.makedirs(os.path.dirname(target), exist_ok = True)
            os.rename(file, target)
        shutil.rmtree(source_dir + 'workspace/', ignore_errors = True, onerror = None)

        # move full export file
        source_file = '{}f{}.sql'.format(self.config.sqlcl_root, app_id)
        target_file = '{}f{}.sql'.format(self.get_root(app_id), app_id)
        #
        if os.path.exists(source_file):
            self.cleanup_file(source_file)
            os.rename(source_file, target_file)

        # move leftovers
        for file in util.get_files(source_dir + '**/*.*'):
            target = file.replace(source_dir, target_dir)
            os.makedirs(os.path.dirname(target), exist_ok = True)
            self.cleanup_file(file)
            os.rename(file, target)
        #
        shutil.rmtree(source_dir, ignore_errors = True, onerror = None)



    def cleanup_file(self, file):
        if not file.endswith('.sql'):
            return

        # replace just pages or/and full export
        if not ('/pages/page_' in file) and util.extract('/f(\d+).sql$', file) != '':
            return

        # get current file content
        old_content = ''
        with open(file, 'rt') as f:
            old_content = f.read()
        new_content = old_content

        # store new content in the same file
        if new_content != old_content:
            with open(file, 'w', encoding = 'utf-8', newline = '\n') as w:
                w.write(new_content)



    def execute_request(self, request, app_id):
        request = util.replace(request, {
            '{$APP_ID}'         : app_id,
            '{$TODAY}'          : self.today,
            '{$FORMAT_JSON}'    : ',READABLE_JSON' if self.config.apex_format_json else '',
            '{$FORMAT_YAML}'    : ',READABLE_YAML' if self.config.apex_format_yaml else '',
            '{$COMPONENTS}'     : ' '.join(self.comp_changed),
        })
        request = 'SET LINESIZE 200;\n{};\n'.format(request)
        return self.conn.sqlcl_request(request)



if __name__ == "__main__":
    # parse arguments
    parser = argparse.ArgumentParser(add_help = False)

    # actions and flags
    group = parser.add_argument_group('MAIN ACTIONS')
    group.add_argument('-recent',       help = 'Show components changed in # days',     type = int, nargs = '?', default = 1)
    group.add_argument('-full',         help = 'Export full application export',                    nargs = '?', const = True, default = False)
    group.add_argument('-split',        help = 'Export splitted export (components)',               nargs = '?', const = True, default = False)
    group.add_argument('-embedded',     help = 'Export Embedded Code report',                       nargs = '?', const = True, default = False)
    group.add_argument('-rest',         help = 'Export REST services',                              nargs = '?', const = True, default = False)
    group.add_argument('-files',        help = 'Export application files in binary form',           nargs = '?', const = True, default = False)
    group.add_argument('-files_ws',     help = 'Export workspace files in binary form',             nargs = '?', const = True, default = False)
    group.add_argument('-only',         help = 'Proceed with passed actions only',                  nargs = '?', const = True, default = False)
    group.add_argument('-fetch',        help = 'Fetch Git changes before patching',                 nargs = '?', const = True, default = False)
    #
    group = parser.add_argument_group('NEGATING ACTIONS')
    group.add_argument('-nofull',       help = 'Skip full export',                                  nargs = '?', const = True, default = False)
    group.add_argument('-nosplit',      help = 'Skip splitted export',                              nargs = '?', const = True, default = False)
    group.add_argument('-noembedded',   help = 'Skip Embedded Code report',                         nargs = '?', const = True, default = False)
    group.add_argument('-norest',       help = 'Skip REST services',                                nargs = '?', const = True, default = False)
    group.add_argument('-nofiles',      help = 'Skip application files',                            nargs = '?', const = True, default = False)
    group.add_argument('-nofiles_ws',   help = 'Skip workspace files',                              nargs = '?', const = True, default = False)

    # env details
    group = parser.add_argument_group('SPECIFY ENVIRONMENT DETAILS')
    group.add_argument('-schema',       help = '',                                                  nargs = '?')
    group.add_argument('-env',          help = 'Source environment (for overrides)',                nargs = '?')
    group.add_argument('-key',          help = 'Key or key location for passwords',                 nargs = '?')
    #
    group = parser.add_argument_group('LIMIT SCOPE')
    group.add_argument('-ws',           help = 'Limit APEX workspace',                              nargs = '?')
    group.add_argument('-group',        help = 'Limit application group',                           nargs = '?')
    group.add_argument('-app',          help = 'Limit list of application(s)',          type = int, nargs = '*', default = [])
    #
    Export_APEX(parser)

