# coding: utf-8
import sys, os, argparse, datetime
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
        #
        self.show_ws_apps()



    def show_ws_apps(self):
        self.get_applications()

        if self.arg_recent:
            today = str(datetime.datetime.today() - datetime.timedelta(days = self.arg_recent - 1))[0:10]
            #
            for app_id in sorted(self.apex_apps.keys()):
                alias = self.apex_apps[app_id]['app_alias']
                util.print_header('APP {}/{}, CHANGES SINCE {}'.format(app_id, alias, today))
                #
                transl = {
                    '{app_id}'          : app_id,
                    '{since}'           : today,
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
                util.print_table(data)



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



if __name__ == "__main__":
    # parse arguments
    parser = argparse.ArgumentParser(add_help = False)

    # actions and flags
    group = parser.add_argument_group('MAIN ACTIONS')
    group.add_argument('-fetch',        help = 'Fetch Git changes before patching',                                 nargs = '?', const = True,  default = False)
    #
    group = parser.add_argument_group('SPECIFY ENVIRONMENT DETAILS')
    group.add_argument('-schema',       help = '')
    group.add_argument('-target',       help = 'Target environment')
    group.add_argument('-key',          help = 'Key or key location for passwords',                                 nargs = '?')
    #
    group = parser.add_argument_group('LIMIT SCOPE')
    group.add_argument('-ws',           help = '',                         nargs = '?')
    group.add_argument('-group',        help = '',                         nargs = '?')
    group.add_argument('-app',          help = '',                         type = int, nargs = '*', default = [])
    group.add_argument('-recent',       help = '',                         type = int, nargs = '?', default = 1)
    #
    Export_APEX(parser)

