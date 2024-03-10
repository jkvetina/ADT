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
        self.target_env         = self.args.target or self.config.default_env
        self.target_root        = self.repo_root + self.config.path_apex
        self.target_path        = self.target_root + self.app_folder        # raplace later
        self.target_rest        = self.config.apex_path_rest
        self.target_files       = self.config.apex_path_files
        self.target_files_ws    = self.config.apex_path_files_ws
        #
        util.assert_(self.target_env, 'MISSING ARGUMENT: TARGET ENV')
        #
        self.init_config()
        self.init_connection(env_name = self.target_env)
        #
        self.conn = self.db_connect(ping_sqlcl = False)

        # make sure we have the temp folder ready
        if os.path.exists(self.config.sqlcl_root):
            shutil.rmtree(self.config.sqlcl_root, ignore_errors = True, onerror = None)
            os.makedirs(self.config.sqlcl_root)

        # for request replacements
        self.transl = {
            '{app_id}'          : '{$APP_ID}',
            '{since}'           : '{$TODAY}',
            '{format_json}'     : ',READABLE_JSON' if self.config.apex_format_json else '',
            '{format_yaml}'     : ',READABLE_YAML' if self.config.apex_format_yaml else '',
        }

        # for workspace and apps lists
        self.apex_apps      = {}
        self.apex_ws        = {}
        self.comp_changed   = []  # components changes recently

        # scope
        self.arg_workspace  = self.args.ws      or self.config.default_workspace
        self.arg_group      = self.args.group   or self.config.default_app_group
        self.arg_apps       = self.args.app     or self.config.default_apps
        self.arg_recent     = self.args.recent
        self.today          = str(datetime.datetime.today() - datetime.timedelta(days = self.arg_recent - 1))[0:10]
        #
        if self.args.changed:
            self.args.nofull    = True
            self.args.nosplit   = True

        # show matching apps every time
        self.get_applications()

        # for each requested app
        for app_id in sorted(self.apex_apps.keys()):
            # create folders
            for dir in ['', self.target_rest, self.target_files, self.target_files_ws]:
                dir = os.path.dirname(self.get_root(app_id, dir))
                if not os.path.exists(dir):
                    os.makedirs(dir)

            # show recent changes
            if self.config.apex_show_recent and self.arg_recent > 0:
                self.show_recent_changes(app_id)
                print()

            # export changed objects only
            if (self.config.apex_export_changed or self.args.changed) and self.arg_recent > 0:
                self.get_export_changed(app_id)

            # full export
            if self.config.apex_export_full and not self.args.nofull:
                self.get_export_full(app_id)

            # split export
            if self.config.apex_export_split and not self.args.nosplit:
                self.get_export_split(app_id)

            # export embedded code report
            if (self.config.apex_embedded or self.args.embedded):
                self.get_export_embedded(app_id)

            # export REST services
            if (self.config.apex_export_rest or self.args.rest):
                self.get_export_rest(app_id)



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
        request = 'SET LINESIZE 200;\napex export -applicationid {app_id} -list -changesSince {since};\n'
        request = util.replace_dict(request, util.replace_dict(self.transl, {'{$APP_ID}': app_id, '{$TODAY}': self.today}))
        output  = self.conn.sqlcl_request(request)
        #
        data = util.parse_table(output.splitlines()[5:])
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



    def get_export_changed(self, app_id):
        print('EXPORTING CHANGED... ', end = '')
        start   = timeit.default_timer() if self.is_curr_class else None
        request = 'apex export -applicationid {app_id} -expComponents "{comp}" -split'.replace('{comp}', ' '.join(self.comp_changed))
        request = util.replace_dict(request, util.replace_dict(self.transl, {'{$APP_ID}': app_id, '{$TODAY}': self.today}))
        output  = self.conn.sqlcl_request(request)
        timer   = int(round(timeit.default_timer() - start + 0.5, 0))
        print(timer)

        # remove some extra files
        source_dir = '{}f{}'.format(self.config.sqlcl_root, app_id)
        for pattern in self.config.apex_files_ignore:
            for file in util.get_files(source_dir + pattern):
                os.remove(file)
        #
        self.move_files(app_id)



    def get_export_full(self, app_id):
        start   = timeit.default_timer() if self.is_curr_class else None
        request = 'apex export -applicationid {app_id} -nochecksum -skipExportDate -expComments -expTranslations'
        request = util.replace_dict(request, util.replace_dict(self.transl, {'{$APP_ID}': app_id, '{$TODAY}': self.today}))
        output  = self.conn.sqlcl_request(request)
        timer   = int(round(timeit.default_timer() - start + 0.5, 0))
        #
        self.move_files(app_id)



    def get_export_split(self, app_id):
        start   = timeit.default_timer() if self.is_curr_class else None
        request = 'apex export -applicationid {app_id} -nochecksum -skipExportDate -expComments -expTranslations -expType APPLICATION_SOURCE{format_json}{format_yaml} -split'
        request = util.replace_dict(request, util.replace_dict(self.transl, {'{$APP_ID}': app_id, '{$TODAY}': self.today}))
        output  = self.conn.sqlcl_request(request)
        timer   = int(round(timeit.default_timer() - start + 0.5, 0))
        #
        target_dir = self.get_root(app_id, 'application/')
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir, ignore_errors = True, onerror = None)
        #
        self.move_files(app_id)



    def get_export_embedded(self, app_id):
        print('EXPORTING EMBEDDED... ', end = '')
        start   = timeit.default_timer() if self.is_curr_class else None
        request = 'apex export -applicationid {app_id} -nochecksum -expType EMBEDDED_CODE'
        request = util.replace_dict(request, util.replace_dict(self.transl, {'{$APP_ID}': app_id, '{$TODAY}': self.today}))
        output  = self.conn.sqlcl_request(request)
        timer   = int(round(timeit.default_timer() - start + 0.5, 0))
        print(timer)

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



    def get_export_rest(self, app_id):
        start   = timeit.default_timer() if self.is_curr_class else None
        request = 'rest export;\n'
        output  = self.conn.sqlcl_request(request)
        timer   = int(round(timeit.default_timer() - start + 0.5, 0))



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

            # move readable files close to original files
            if os.path.exists(file):
                target = target.replace(source_dir, target_dir).replace('/readable/', '/')
                if not os.path.exists(os.path.dirname(target)):
                    os.makedirs(os.path.dirname(target))
                os.rename(file, target)

        # remove readable folder
        if os.path.exists(source_dir + 'readable/'):
            shutil.rmtree(source_dir + 'readable/', ignore_errors = True, onerror = None)

        # move file
        source_file = '{}f{}.sql'.format(self.config.sqlcl_root, app_id)
        target_file = '{}f{}.sql'.format(self.get_root(app_id), app_id)
        #
        if os.path.exists(source_file):
            self.cleanup_file(source_file)
            os.rename(source_file, target_file)

        # move leftovers
        for file in util.get_files(source_dir + '**/*.*'):
            target = file.replace(source_dir, target_dir)
            if not os.path.exists(os.path.dirname(target)):
                os.makedirs(os.path.dirname(target))
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



if __name__ == "__main__":
    # parse arguments
    parser = argparse.ArgumentParser(add_help = False)

    # actions and flags
    group = parser.add_argument_group('MAIN ACTIONS')
    group.add_argument('-recent',       help = 'Show components changed in # days',     type = int, nargs = '?', default = 1)
    group.add_argument('-changed',      help = 'Export components changed in # days',               nargs = '?', const = True, default = False)
    group.add_argument('-nofull',       help = 'Skip full export',                                  nargs = '?', const = True, default = False)
    group.add_argument('-nosplit',      help = 'Skip splitted export',                              nargs = '?', const = True, default = False)
    group.add_argument('-embedded',     help = 'Export Embedded Code Report',                       nargs = '?', const = True, default = False)
    group.add_argument('-rest',         help = 'Export REST services',                              nargs = '?', const = True, default = False)
    group.add_argument('-files',        help = 'Export app & ws files in binary form',              nargs = '?', const = True, default = False)
    group.add_argument('-fetch',        help = 'Fetch Git changes before patching',                 nargs = '?', const = True, default = False)
    #
    group = parser.add_argument_group('SPECIFY ENVIRONMENT DETAILS')
    group.add_argument('-schema',       help = '')
    group.add_argument('-target',       help = 'Target environment')
    group.add_argument('-key',          help = 'Key or key location for passwords',                                 nargs = '?')
    #
    group = parser.add_argument_group('LIMIT SCOPE')
    group.add_argument('-ws',           help = 'Limit APEX workspace',                              nargs = '?')
    group.add_argument('-group',        help = 'Limit application group',                           nargs = '?')
    group.add_argument('-app',          help = 'Limit list of application(s)',          type = int, nargs = '*', default = [])
    #
    Export_APEX(parser)

