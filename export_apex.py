# coding: utf-8
import sys, os, argparse, datetime, timeit
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
        self.target_env         = self.args.target or self.config.default_env
        self.target_path        = self.repo_root + self.config.path_apex
        self.target_path_rest   = self.repo_root + self.config.apex_path_rest
        self.target_files       = self.repo_root + self.config.apex_path_files
        self.target_files_ws    = self.repo_root + self.config.apex_path_files_ws
        #
        util.assert_(self.target_env, 'MISSING ARGUMENT: TARGET ENV')
        #
        self.init_config()
        self.init_connection(env_name = self.target_env)
        #
        self.conn = self.db_connect(ping_sqlcl = False)

        # create folders
        for dir in [self.target_path, self.target_path_rest, self.target_files, self.target_files_ws]:
            dir = os.path.dirname(dir)
            if not os.path.exists(dir):
                os.makedirs(dir)

        self.apex_apps  = {}
        self.apex_ws    = {}

        # scope
        self.arg_workspace  = self.args.ws      or self.config.default_workspace
        self.arg_group      = self.args.group   or self.config.default_app_group
        self.arg_apps       = self.args.app     or self.config.default_apps
        self.arg_recent     = self.args.recent
        self.today          = str(datetime.datetime.today() - datetime.timedelta(days = self.arg_recent - 1))[0:10]
        #
        self.get_applications()

        # for each requested app
        for app_id in sorted(self.apex_apps.keys()):
            if self.config.apex_show_recent and self.arg_recent and self.arg_recent > 0:
                self.show_recent_changes(app_id)

            # full export
            if self.config.apex_export_full and not self.args.nofull:
                self.get_export_full(app_id)

            # split export
            if self.config.apex_export_split and not self.args.nosplit:
                self.get_export_split(app_id)

            # export REST services
            if (self.config.apex_export_rest or self.args.rest):
                self.get_export_rest(app_id)



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
        transl = {
            '{app_id}'          : app_id,
            '{since}'           : self.today,
            '{format_json}'     : ',READABLE_JSON',
            '{format_yaml}'     : ',READABLE_YAML',
            '{embedded}'        : ',EMBEDDED_CODE',
        }
        request = 'SET LINESIZE 200;\napex export -applicationid {app_id} -list -changesSince {since};\n'
        request = util.replace_dict(request, transl)
        output  = self.conn.sqlcl_request(request)
        #
        data = util.parse_table(output.splitlines()[5:])
        for i, row in enumerate(data):
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



    def get_export_full(self, app_id):
        start   = timeit.default_timer() if self.is_curr_class else None
        request = 'apex export -applicationid {app_id} -nochecksum -skipExportDate -expComments -expTranslations'
        request = util.replace_dict(request, util.replace_dict(self.transl, {'{$APP_ID}': app_id, '{$TODAY}': self.today}))
        output  = self.conn.sqlcl_request(request)
        timer   = int(round(timeit.default_timer() - start + 0.5, 0))



    def get_export_split(self, app_id):
        start   = timeit.default_timer() if self.is_curr_class else None
        request = 'apex export -applicationid {app_id} -nochecksum -skipExportDate -expComments -expTranslations -expType APPLICATION_SOURCE{format_json}{format_yaml}{embedded} -split'
        request = util.replace_dict(request, util.replace_dict(self.transl, {'{$APP_ID}': app_id, '{$TODAY}': self.today}))
        output  = self.conn.sqlcl_request(request)
        timer   = int(round(timeit.default_timer() - start + 0.5, 0))



    def get_export_rest(self, app_id):
        start   = timeit.default_timer() if self.is_curr_class else None
        request = 'rest export;\n'
        output  = self.conn.sqlcl_request(request)
        timer   = int(round(timeit.default_timer() - start + 0.5, 0))



if __name__ == "__main__":
    # parse arguments
    parser = argparse.ArgumentParser(add_help = False)

    # actions and flags
    group = parser.add_argument_group('MAIN ACTIONS')
    group.add_argument('-fetch',        help = 'Fetch Git changes before patching',                                 nargs = '?', const = True,  default = False)
    group.add_argument('-rest',         help = 'Export REST services',                              nargs = '?', const = True, default = False)
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
    group.add_argument('-recent',       help = 'Show components changed in # days',     type = int, nargs = '?', default = 1)
    group.add_argument('-nofull',       help = 'Skip full export',                                  nargs = '?', const = True, default = False)
    group.add_argument('-nosplit',      help = 'Skip splitted export',                              nargs = '?', const = True, default = False)
    #
    Export_APEX(parser)

