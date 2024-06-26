# coding: utf-8
import sys, os, argparse, time, mimetypes
import rcssmin, rjsmin
#
import config
from lib import util
from lib import queries_export_apex as query

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

class Live_Upload(config.Config):

    def __init__(self, args = None):
        self.parser = argparse.ArgumentParser(add_help = False)

        # actions and flags
        group = self.parser.add_argument_group('MAIN ACTIONS')
        group.add_argument('-app',          help = 'To override APEX application',          type = int,             nargs = '?')
        group.add_argument('-folder',       help = 'To override static files location',                             nargs = '?')
        group.add_argument('-workspace',    help = 'Upload to workspace (not app) files',                           nargs = '?', const = True, default = False)
        group.add_argument('-interval',     help = 'Interval in between loops',             type = int,             nargs = '?')
        group.add_argument('-show',         help = 'Show files in folder at start',                                 nargs = '?', const = True, default = False)

        # env details
        group = self.parser.add_argument_group('SPECIFY ENVIRONMENT DETAILS')
        group.add_argument('-schema',       help = '',                                                              nargs = '?')
        group.add_argument('-env',          help = 'Source environment (for overrides)',                            nargs = '?')
        group.add_argument('-key',          help = 'Key or key location for passwords',                             nargs = '?')

        super().__init__(self.parser, args)

        # setup env and paths
        self.app_folder         = '$APP_FOLDER/'
        self.target_root        = self.repo_root + self.config.path_apex
        self.target_path        = self.target_root + self.app_folder        # replace later
        self.target_files       = self.config.apex_path_files
        self.apex_apps          = {}
        self.arg_sleep          = self.args.interval or 1

        # connect to the database, APEX schema
        self.init_config()
        self.info['schema']     = self.args.schema  or self.connection.get('schema_apex') or self.connection.get('schema')
        self.curr_app_id        = self.args.app     or int(self.connection.get('app'))
        #
        self.conn = self.db_connect(ping_sqlcl = False)
        self.conn.execute(query.apex_security_context, app_id = self.curr_app_id)

        # get info about application to setup proper folder
        self.get_application(app_id = self.curr_app_id)
        #
        self.monitored_files    = {}
        self.monitored_dir      = self.args.folder or self.get_root(app_id = self.curr_app_id) + self.target_files
        if self.args.workspace:
            self.monitored_dir  = self.args.folder or (self.target_root + self.config.apex_workspace_dir + self.target_files).replace('//', '/')
        #
        if not os.path.exists(self.monitored_dir):
            util.raise_error('FOLDER MISSING', self.monitored_dir)
        #
        util.print_header('MONITORING FOLDER:', self.monitored_dir)
        util.print_help('press Control+C to quit')
        print()

        # initial load
        pattern     = self.monitored_dir + '**/*'
        check_files = util.get_files(pattern)
        #
        for file in check_files:
            if self.args.show:
                print('  - {}'.format(file.replace(self.monitored_dir, '')))
            current_stamp = os.path.getmtime(file)
            self.monitored_files[file] = current_stamp
        if self.args.show:
            print()

        # check for changes at an interval
        while True:
            try:
                check_files     = util.get_files(pattern)
                changed_files   = []
                #
                for file in check_files:
                    current_stamp = os.path.getmtime(file)
                    if (not (file in self.monitored_files) or current_stamp > self.monitored_files.get(file)):
                        self.monitored_files[file] = current_stamp
                        changed_files.append(file)
                #
                if len(changed_files) > 0:
                    print()
                    for file in changed_files:
                        util.print_now('  - {} '.format(file.replace(self.monitored_dir, '')))
                        self.upload_file(file)
                        minified = self.minify_file(file)
                        util.print_now('[OK]', append = True, close = True)
                #
                util.print_now('.', append = True)
                time.sleep(self.arg_sleep)
                #
            except KeyboardInterrupt:
                break
        print()



    def upload_file(self, file):
        with open(file, 'rb') as b:
            name    = file.replace(self.monitored_dir, '')
            mime    = mimetypes.guess_type(file)[0] or 'text/plain'
            payload = b.read()
            #
            if self.args.workspace:
                self.conn.execute(query.apex_upload_ws_file, name = name, mime = mime, payload = payload)
            else:
                self.conn.execute(query.apex_upload_app_file, app_id = self.curr_app_id, name = name, mime = mime, payload = payload)



    def minify_file(self, file):
        if (file.endswith('.css') or file.endswith('.js')) and not ('.min.' in file):
            payload = util.get_file_lines(file)
            #
            if file.endswith('.js'):
                payload = rcssmin.cssmin(payload, keep_bang_comments = True)
                #
            elif file.endswith('.js'):
                payload = rjsmin.jsmin(payload, keep_bang_comments = True)
            #
            target_file = file.replace('.css', '.min.css').replace('.js', '.min.js')
            util.write_file(target_file, payload)
            return target_file



if __name__ == "__main__":
    Live_Upload()

