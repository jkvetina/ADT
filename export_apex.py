# coding: utf-8
import sys, os, re, argparse, datetime, codecs
from multiprocessing.pool import ThreadPool
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

class Export_APEX(config.Config):

    def __init__(self, args = None, conn = None, silent = False):
        self.parser = argparse.ArgumentParser(add_help = False)

        # actions and flags
        group = self.parser.add_argument_group('MAIN ACTIONS')
        group.add_argument('-recent',       help = 'Show components changed in # days',     type = util.is_boolstr, nargs = '?')
        group.add_argument('-by',           help = 'Export components changed by developer',                        nargs = '?')
        group.add_argument('-full',         help = 'Export full application export',                                nargs = '?', const = True, default = False)
        group.add_argument('-split',        help = 'Export splitted export (components)',                           nargs = '?', const = True, default = False)
        group.add_argument('-embedded',     help = 'Export Embedded Code report',                                   nargs = '?', const = True, default = False)
        group.add_argument('-rest',         help = 'Export REST services',                                          nargs = '?', const = True, default = False)
        group.add_argument('-files',        help = 'Export application files in binary form',                       nargs = '?', const = True, default = False)
        group.add_argument('-files_ws',     help = 'Export workspace files in binary form',                         nargs = '?', const = True, default = False)
        group.add_argument('-only',         help = 'Proceed with passed actions only',                              nargs = '?', const = True, default = False)
        group.add_argument('-all',          help = 'Export everything',                                             nargs = '?', const = True, default = False)
        group.add_argument('-fetch',        help = 'Fetch Git changes before patching',                             nargs = '?', const = True, default = False)
        #
        group = self.parser.add_argument_group('NEGATING ACTIONS')
        group.add_argument('-nofull',       help = 'Skip full export',                                              nargs = '?', const = True, default = False)
        group.add_argument('-nosplit',      help = 'Skip splitted export',                                          nargs = '?', const = True, default = False)
        group.add_argument('-noembedded',   help = 'Skip Embedded Code report',                                     nargs = '?', const = True, default = False)
        group.add_argument('-norest',       help = 'Skip REST services',                                            nargs = '?', const = True, default = False)
        group.add_argument('-nofiles',      help = 'Skip application files',                                        nargs = '?', const = True, default = False)
        group.add_argument('-nofiles_ws',   help = 'Skip workspace files',                                          nargs = '?', const = True, default = False)

        # env details
        group = self.parser.add_argument_group('SPECIFY ENVIRONMENT DETAILS')
        group.add_argument('-schema',       help = '',                                                              nargs = '?')
        group.add_argument('-env',          help = 'Source environment (for overrides)',                            nargs = '?')
        group.add_argument('-key',          help = 'Key or key location for passwords',                             nargs = '?')
        #
        group = self.parser.add_argument_group('LIMIT SCOPE')
        group.add_argument('-ws',           help = 'Limit APEX workspace',                                          nargs = '?')
        group.add_argument('-group',        help = 'Limit application group',                                       nargs = '?')
        group.add_argument('-app',          help = 'Limit list of application(s)',          type = int,             nargs = '*', default = [])

        super().__init__(self.parser, args)

        # setup env and paths
        self.target_root        = self.repo_root + self.config.path_apex
        self.target_rest        = self.target_root + self.config.apex_path_rest
        self.target_files       = self.config.apex_path_files
        #
        self.init_config()
        self.conn = conn or self.db_connect(ping_sqlcl = False, silent = silent)

        # make sure we have the temp folder ready
        if not os.path.exists(self.config.sqlcl_root):
            os.makedirs(self.config.sqlcl_root, exist_ok = True)

        # for workspace and apps lists
        self.comp_changed       = []  # components changes recently
        self.workspace_offset   = None
        self.timers             = {}  # to track export times so we can predict progress on next run

        # scope
        self.arg_workspace  = self.args.ws      or self.conn.tns.get('workspace', '')
        self.arg_group      = self.args.group
        self.arg_apps       = self.args.app     or [self.conn.tns.get('app', '')]
        #
        self.arg_recent     = 1     # default walue = changes done today
        if isinstance(self.args.recent, bool):
            self.arg_recent = self.arg_recent if self.args.recent else 0
        elif self.args.recent:
            self.arg_recent = int(self.args.recent)
        elif self.config.apex_show_recent > 0:
            self.arg_recent = self.config.apex_show_recent
        #
        self.today          = str(datetime.datetime.today() - datetime.timedelta(days = self.arg_recent - 1))[0:10]

        # sanitize requested actions
        self.actions = {
            'recent'    : False,
            'full'      : False,
            'split'     : False,
            'embedded'  : False,
            'rest'      : False,
            'files'     : False,
            'files_ws'  : False,
        }
        if __name__ != "__main__":  # dont continue if this class is called from other module
            return
        self.parse_actions()

        # show matching apps every time
        self.get_applications()
        self.get_enrichments()
        self.get_workspace_developers()
        self.load_timers()
        #
        if len(self.apex_apps) == 0:
            util.raise_error('NO APEX APPS FOUND')

        # for each requested app
        for app_id in sorted(self.apex_apps.keys()):
            if not (app_id in self.arg_apps):
                continue
            #
            util.delete_folder('{}f{}/'.format(self.config.sqlcl_root, app_id))
            self.get_comments(app_id)

            # show recent changes
            if self.arg_recent > 0 and self.actions['recent']:
                self.show_recent_changes(app_id)

            util.print_header('APP {}/{}, EXPORTING:'.format(app_id, self.apex_apps[app_id]['app_alias']))
            self.conn.execute(query.apex_security_context, app_id = app_id)

            # get default authentication scheme
            self.auth_scheme_id     = 0
            self.auth_scheme_name   = ''
            #
            if len(self.config.apex_authentication) > 0:
                for row in self.conn.fetch_assoc(query.apex_authentication_schemes, app_id = app_id):
                    if self.config.apex_authentication in row.authentication_name:
                        self.auth_scheme_id     = row.authentication_id
                        self.auth_scheme_name   = row.authentication_name

            # create folders
            os.makedirs(os.path.dirname(self.get_root(app_id)), exist_ok = True)

            # create a queue
            todo = [
                {'action' : 'recent',       'header' : '  CHANGED COMPONENTS' },
                {'action' : 'full',         'header' : '  FULL APP EXPORT' },
                {'action' : 'split',        'header' : '  SPLIT COMPONENTS' },
                {'action' : 'embedded',     'header' : '  EMBEDDED CODE REPORT' },
                {'action' : 'rest',         'header' : '  REST SERVICES' },
                {'action' : 'files',        'header' : '  APPLICATION FILES' },
                {'action' : 'files_ws',     'header' : '  WORKSPACE FILES' },
            ]
            for row in todo:
                action = row['action']
                if self.actions[action]:
                    if not (app_id in self.timers):
                        self.timers[app_id] = {}
                    if not (action in self.timers[app_id]):
                        self.timers[app_id][action] = 0
                    #
                    progress_target = self.timers[app_id][action] or 999
                    progress_done   = 0
                    start           = util.get_start()

                    # execute in a thread so we can show progress in main process
                    with ThreadPool(processes = 1) as pool:
                        result = pool.apply_async(getattr(self, 'export_' + action), [app_id])
                        while True:
                            try:
                                if result.ready():
                                    break
                                #
                                progress_done = util.print_progress(progress_done, progress_target, extra = row['header'], start = start, sleep = 1)
                                #
                            except KeyboardInterrupt:
                                print('\n')
                                return
                        if progress_done != -1:
                            util.print_progress_done(extra = row['header'], start = start)

                    # update timers
                    timer = util.get_start() - start
                    if self.timers[app_id][action] > 0:
                        timer = (timer + self.timers[app_id][action]) / 2
                    self.timers[app_id][action] = round(timer, 2)

                # move files from temp folders right away after each block
                self.move_files(app_id)

            # move files from temp folders to target folders
            self.move_files(app_id)
            self.move_ws_files()
            self.store_timers()
            print()

        # cleanup temp folder
        #if not self.debug and os.path.exists(self.config.sqlcl_root):
        #    util.delete_folder(self.config.sqlcl_root)



    def parse_actions(self):
        # check what exactly we will be exporting
        for arg_name in self.actions.keys():
            if self.args.get('no' + arg_name, ''):              # keep default False
                continue
            if self.args.get(arg_name, '') or self.args.all:    # proceed
                self.actions[arg_name] = True
                continue
            if self.config.get('apex_export_' + arg_name, '') and not self.args.only:
                self.actions[arg_name] = True
                continue
        #
        if (self.args.recent == 0 or self.args.split or self.args.all):
            self.actions['recent'] = False



    def get_applications(self):
        # get list of applications
        args = {
            'owner'         : self.info.schema,
            'workspace'     : self.arg_workspace,
            'group_id'      : self.arg_group,
            'app_id'        : '',  # '|'.join(str(x) for x in self.arg_apps),
        }
        self.apex_apps = {}
        #
        groups = {}
        for row in self.conn.fetch_assoc(query.apex_applications, **args):
            # split to groups for screen output
            row.app_group = row.app_group or '-'
            if row.app_id in self.arg_apps:
                if not (row.app_group in groups):
                    groups[row.app_group] = []
                groups[row.app_group].append({
                    'app_id'        : row.app_id,
                    'alias'         : row.app_alias,
                    #'name'          : row.app_name,
                    'pages'         : row.pages,
                    'updated_at'    : row.updated_at,
                })
            #
            self.apex_apps[row.app_id] = row

        # show groups
        for group, rows in groups.items():
            util.print_header('APEX APPLICATIONS:', group if group != '-' else '')
            util.print_table(rows)

        # store in file for later use
        payload = {}
        for app_id, row in self.apex_apps.items():
            payload[app_id] = dict(row)
        #
        util.write_file(self.apex_apps_file, payload = payload, yaml = True, fix = True)



    def get_enrichments(self):
        # enrich meaningless ids with component names
        args = {
            'owner'     : self.info.schema,
            'workspace' : self.arg_workspace,
            'group_id'  : self.arg_group,
            'app_id'    : '|'.join(str(x) for x in self.arg_apps),
        }
        self.enrich_ids = {}
        for row in self.conn.fetch_assoc(query.apex_id_names, **args):
            self.enrich_ids[row.component_id] = '{}: {}'.format(row.component_type, row.component_name)



    def load_timers(self):
        # store application list in the yaml file
        if os.path.exists(self.timers_file):
            with open(self.timers_file, 'rt', encoding = 'utf-8') as f:
                self.timers = dict(util.get_yaml(f, self.timers_file))



    def store_timers(self):
        util.write_file(self.timers_file, payload = self.timers, yaml = True, fix = True)



    def get_workspace_developers(self):
        self.developers = {}
        for row in self.conn.fetch_assoc(query.workspace_developers):
            if not (row.workspace in self.developers):
                self.developers[row.workspace] = {}
            self.developers[row.workspace][row.user_name] = row.user_mail
        #
        util.write_file(self.developers_file, payload = self.developers, yaml = True, fix = True)



    def get_comments(self, app_id):
        comments = {}
        for row in self.conn.fetch_assoc(query.page_comments, app_id = app_id):
            comments[row.page_id] = {
                'page' : {
                    'page_name'     : row.page_name,
                    'page_comment'  : row.page_comment,
                    'updated_by'    : row.last_updated_by,
                    'updated_at'    : row.last_updated_on,
                },
                'regions' : {},
            }
        #
        for row in self.conn.fetch_assoc(query.page_region_comments, app_id = app_id):
            if not (row.page_id in comments):
                comments[row.page_id] = {
                    'page' : {
                        'page_name' : row.page_name,
                    },
                    'regions' : {},
                }
            comments[row.page_id]['regions'][row.region_id] = {
                'region_name'       : row.region_name,
                'region_comment'    : row.component_comment,
                'updated_by'        : row.last_updated_by,
                'updated_at'        : row.last_updated_on,
            }

        # store connection parameters in the yaml file
        target_dir = '{}/comments/'.format(self.get_root(app_id))
        os.makedirs(target_dir, exist_ok = True)
        for page_id, content in comments.items():
            file = '{}p{}.yaml'.format(target_dir, str(page_id).rjust(5, '0'))
            util.write_file(file, content, yaml = True, fix = True)



    def show_recent_changes(self, app_id):
        alias       = self.apex_apps[app_id]['app_alias']
        workspace   = self.apex_apps[app_id]['workspace']
        author      = self.args.by if self.args.by in self.developers[workspace] else ''
        #
        util.print_header('APP {}/{}, CHANGES SINCE {}{}:'.format(app_id, alias, self.today, ' BY ' + author if author else ''))
        #
        changesby   = ' -changesby {}'.format(author) if author else ''
        output      = self.execute_request('apex export -applicationid {$APP_ID} -list -changessince {$TODAY}' + changesby, app_id, lines = True)
        data        = util.parse_table(output)
        if data == [{}]:
            data = []
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



    def export_recent(self, app_id, schema = None, components = None):
        if len(self.comp_changed) == 0 and not components:
            return
        #
        if components:
            # we need to pull info about the app
            self.get_application(app_id, schema = schema)
        #
        output = self.execute_request('apex export -applicationid {$APP_ID} -expcomments -expcomponents "{$COMPONENTS}" -split', app_id, components = components)

        # remove some extra files
        source_dir = '{}f{}'.format(self.config.sqlcl_root, app_id)
        for pattern in self.config.apex_files_ignore:
            for file in util.get_files(source_dir + pattern):
                os.remove(file)
        #
        return output



    def export_full(self, app_id):
        return self.execute_request('apex export -applicationid {$APP_ID} -nochecksum -expcomments -exptranslations -expaclassignments', app_id)



    def export_split(self, app_id):
        output = self.execute_request('apex export -applicationid {$APP_ID} -nochecksum -expcomments -exptranslations -expaclassignments -exptype APPLICATION_SOURCE{$FORMAT_JSON}{$FORMAT_YAML} -split', app_id)

        # cleanup target directory before moving new files there
        target_dir = self.get_root(app_id, 'application/')
        if os.path.exists(target_dir):
            util.delete_folder(target_dir)

        # delete original (encoded) files, we can export/keep binaries instead
        if self.config.apex_delete_orig_files:
            duplicates = [
                '{}f{}/application/shared_components/files/'.format(self.config.sqlcl_root, app_id),
                '{}f{}/application/shared_components/app_static_files/'.format(self.config.sqlcl_root, app_id),
            ]
            for source_dir in duplicates:
                util.delete_folder(source_dir)
        #
        return output



    def export_embedded(self, app_id):
        output = self.execute_request('apex export -applicationid {$APP_ID} -nochecksum -exptype EMBEDDED_CODE', app_id)

        # move to proper folder
        source_dir = '{}f{}/embedded_code/'.format(self.config.sqlcl_root, app_id)
        target_dir = self.get_root(app_id, 'embedded_code/')
        #
        if os.path.exists(target_dir):
            util.delete_folder(target_dir)
        #
        if os.path.exists(source_dir):
            for source_file in util.get_files(source_dir + '**/*.*'):
                # remove first 10 lines
                try:
                    with codecs.open(source_file, 'r', encoding = 'utf-8', errors = 'ignore') as f:
                        old_content = f.readlines()
                    util.write_file(source_file, ''.join(old_content[10:]))
                except:
                    print('\nERROR:', source_file.replace(self.config.sqlcl_root, ''))

                # move files
                if '/pages/p' in source_file:
                    target_file = source_file.replace('/pages/p', '/pages/page_')
                    util.move_file(source_file, target_file)
            #
            util.copy_folder(source_dir, target_dir)
            util.delete_folder(source_dir)
        #
        return output



    def export_rest(self, app_id):
        # prepare target folders
        if os.path.exists(self.target_rest):
            util.delete_folder(self.target_rest)
        os.makedirs(self.target_rest, exist_ok = True)

        # export REST services
        lines       = self.execute_request('rest export', app_id, lines = True)
        content     = []
        modules     = []
        first       = []
        append      = False

        # split one file into dedicated files for each module
        for (i, line) in enumerate(lines):
            module_started = ('ORDS.DEFINE_MODULE' in line)
            if not append and not module_started:
                first.append(line)
            #
            if module_started:
                if len(content):
                    modules.append(content)
                content = []
                append  = True
            if line.strip().startswith('COMMIT;') and lines[i + 1].startswith('END;'):
                append  = False
            if append:
                content.append(line.rstrip())
        if len(content):
            modules.append(content)

        # create folders from service names
        for content in modules:
            name = re.findall('[\'][^\']+[\']', content[1])[0].replace('\'', '')
            file = self.target_rest + '/' + name + '.sql'
            #
            found = len(self.config.apex_rest_prefixes) == 0
            for prefix in self.config.apex_rest_prefixes:
                if name.startswith(prefix):
                    found = True
                    break
            #
            if found:
                payload = 'BEGIN\n{}\nEND;\n/\n'.format('\n'.join(list(filter(None, content))))
                util.write_file(file, payload)

        # schema definition
        if len(modules) > 0:
            file    = self.target_rest + '/__enable_schema.sql'
            content = []
            #
            for line in first:
                if line.startswith('BEGIN'):
                    continue
                if line.startswith('-- Schema:'):
                    line = line.split(' Date:')[0]  # strip date
                if line.startswith('END;'):
                    break
                content.append(line.rstrip())
            #
            payload = 'BEGIN\n{}\nEND;\n/\n'.format('\n'.join(list(filter(None, content))))
            util.write_file(file, payload)



    def export_files(self, app_id):
        # get target folder
        if app_id == 0:  # workspace files
            target_dir = self.get_root_ws(self.config.apex_path_files)
        else:
            target_dir = self.get_root(app_id, self.target_files)

        # delete targer folders first
        util.delete_folder(target_dir)

        # create files
        for row in self.conn.fetch_assoc(query.apex_files, app_id = app_id):
            file = target_dir + row.filename
            os.makedirs(os.path.dirname(file), exist_ok = True)
            #
            with open(file, 'wb') as w:
                w.write(row.f.read())   # blob_content



    def export_files_ws(self, app_id = 0):
        self.export_files(app_id = 0)



    def move_files(self, app_id):
        source_dir = '{}f{}/'.format(self.config.sqlcl_root, app_id)
        target_dir = self.get_root(app_id)

        # move readable files
        for source_file in util.get_files(source_dir + 'readable/**/*.*'):
            target_file = source_file

            # application file close to app full export
            if '/readable/application/f{}.'.format(app_id) in source_file:
                target_file = source_file.replace('/readable/application/', '/')

            # move page files close to pages
            if '/readable/application/page_groups.' in source_file:
                target_file = source_file.replace('/application/', '/application/pages/')
            #
            if '/readable/application/pages/p' in source_file:
                target_file = source_file.replace('/pages/p', '/pages/page_')

            # workspace files
            if '/readable/workspace/' in source_file:
                target_file = source_file.replace('/readable/', '/../')

            # move readable files close to original files
            if os.path.exists(source_file):
                target_file = target_file.replace(source_dir, target_dir).replace('/readable/', '/')
                util.move_file(source_file, target_file)

        # remove readable folder
        if os.path.exists(source_dir + 'readable/'):
            util.delete_folder(source_dir + 'readable/')

        # move workspace files to workspace folder
        for source_file in util.get_files(source_dir + 'workspace/**/*.*'):
            target_file = source_file.replace('/f{}/workspace/'.format(app_id), '/' + self.config.apex_workspace_dir)
            util.move_file(source_file, target_file)
        util.delete_folder(source_dir + 'workspace/')

        # move full export file
        source_file = '{}f{}.sql'.format(self.config.sqlcl_root, app_id)
        target_file = '{}f{}.sql'.format(self.get_root(app_id), app_id)
        #
        if os.path.exists(source_file):
            self.cleanup_file(source_file)
            util.move_file(source_file, target_file)

        # move leftovers
        for source_file in util.get_files(source_dir + '**/*.*'):
            self.cleanup_file(source_file)
            target_file = source_file.replace(source_dir, target_dir)
            util.move_file(source_file, target_file)
        #
        util.delete_folder(source_dir)

        # get rid of install files
        for source_file in util.get_files(self.get_root(app_id, 'install*.sql')):
            os.remove(source_file)
        for source_file in util.get_files(self.get_root(app_id, 'application/create_application.sql')):
            os.remove(source_file)



    def move_ws_files(self):
        source_dir = '{}workspace/'.format(self.config.sqlcl_root)
        target_dir = self.get_root_ws()
        #
        for source_file in util.get_files(source_dir + '**/*.*'):
            target_file = source_file.replace(source_dir, target_dir)
            self.cleanup_file(source_file)
            util.move_file(source_file, target_file)
        #
        #util.delete_folder(source_dir)



    def cleanup_file(self, file):
        if not file.endswith('.sql'):
            return

        # get application id, workspace and type of file
        app_id      = util.extract_int(r'/f(\d+)/', file) or util.extract_int(r'/f(\d+)\.sql$', file)
        workspace   = self.apex_apps[app_id]['workspace'] if app_id else ''
        is_full     = app_id and '/f{}.sql'.format(app_id) in file
        is_page     = app_id and '/pages/page_' in file

        # get current file content
        old_content = ''
        with open(file, 'rt', encoding = 'utf-8') as f:
            old_content = f.read()
        new_content = old_content

        # replace workspace id if exported from different instance
        if self.config.apex_workspace_id and self.config.apex_workspace_id > 0:
            new_content = util.replace(new_content,
                r",p_default_workspace_id=>(\d+)",
                ",p_default_workspace_id=>{}".format(self.config.apex_workspace_id))

        # keep only developers as page authors
        if is_page and self.config.apex_keep_developers and self.config.apex_authors and 'developers' in self:
            developer = util.extract(",p_last_updated_by=>'([^']+)'", new_content)
            if (not (developer in self.developers[workspace]) or not self.config.apex_keep_developers):
                new_content = util.replace(new_content,
                    r",p_last_updated_by=>'([^']+)'",
                    ",p_last_updated_by=>'{}'".format(self.config.apex_authors))
                #
                if self.config.apex_timestamps:
                    new_content = util.replace(new_content,
                        r",p_last_upd_yyyymmddhh24miss=>'(\d+)'",
                        ",p_last_upd_yyyymmddhh24miss=>'{}'".format(self.config.apex_timestamps))

        # replace default authentication
        if is_full and self.auth_scheme_id > 0:
            new_content = util.replace(new_content,
                r",p_authentication_id=>wwv_flow_imp.id[(]([\d]+)[)]",
                ",p_authentication_id=>wwv_flow_imp.id({})  -- {}".format(self.auth_scheme_id, self.auth_scheme_name))

        # dont track offset on individual pages
        if self.workspace_offset == None:
            self.workspace_offset = util.extract_int(r",p_default_id_offset=>([\d]+)", new_content)
            if self.workspace_offset > 0 and self.debug:
                print('    WORKSPACE OFFSET:', self.workspace_offset)
        #
        if not is_full:
            new_content = util.replace(new_content,
                r",p_default_id_offset=>([\d]+)",
                ",p_default_id_offset=>0")

        # translate id to more meaningful names
        if 'enrich_ids' in self:
            for component_id, component_name in self.enrich_ids.items():
                component_id -= self.workspace_offset
                new_content = new_content.replace (
                    '.id({})\n'.format(component_id),
                    '.id({})  -- {}\n'.format(component_id, component_name))

        # store new content in the same file
        if new_content != old_content:
            util.write_file(file, new_content)



    def execute_request(self, request, app_id, lines = False, components = None):
        app_id  = int(app_id)
        request = util.replace(request, {
            '{$WORKSPACE}'      : self.apex_apps[app_id].workspace,
            '{$WORKSPACE_ID}'   : self.apex_apps[app_id].workspace_id,
            '{$APP_ID}'         : app_id,
            '{$TODAY}'          : self.today,
            '{$FORMAT_JSON}'    : ',READABLE_JSON' if self.config.apex_format_json else '',
            '{$FORMAT_YAML}'    : ',READABLE_YAML' if self.config.apex_format_yaml else '',
            '{$COMPONENTS}'     : ' '.join(components or self.comp_changed),
        })
        request = 'SET LINESIZE 200;\n{};\n'.format(request)
        #
        return util.cleanup_sqlcl(self.conn.sqlcl_request(request), lines = lines)



if __name__ == "__main__":
    Export_APEX()

