# coding: utf-8
import sys, os, re, argparse, shutil, datetime, timeit
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
        self.target_path        = self.target_root + self.app_folder        # replace later
        self.target_rest        = self.config.apex_path_rest
        self.target_files       = self.config.apex_path_files
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
        #
        self.arg_recent     = 1     # default walue = changes done today
        if isinstance(self.args.recent, bool):
            self.arg_recent = self.arg_recent if self.args.recent else 0
        elif self.args.recent:
            self.arg_recent = int(self.args.recent)
        #
        self.today          = str(datetime.datetime.today() - datetime.timedelta(days = self.arg_recent - 1))[0:10]
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
            if (self.config.apex_show_recent > 0 or self.arg_recent > 0):
                self.show_recent_changes(app_id)

            util.print_header('APP {}/{}, EXPORTING:'.format(app_id, self.apex_apps[app_id]['app_alias']))
            self.conn.execute(query.apex_security_context, app_id = app_id)

            # create folders
            os.makedirs(os.path.dirname(self.get_root(app_id)), exist_ok = True)

            # create a queue
            todo = [
                {'action' : 'recent',       'header' : 'CHANGED COMPONENTS' },
                {'action' : 'full',         'header' : 'FULL APP EXPORT' },
                {'action' : 'split',        'header' : 'SPLIT COMPONENTS' },
                {'action' : 'embedded',     'header' : 'EMBEDDED CODE REPORT' },
                {'action' : 'rest',         'header' : 'REST SERVICES' },
                {'action' : 'files',        'header' : 'APPLICATION FILES' },
                {'action' : 'files_ws',     'header' : 'WORKSPACE FILES' },
            ]
            for row in todo:
                if self.actions[row['action']]:
                    h = self.print_start(row['header'])
                    getattr(self, 'export_' + row['action'])(app_id)
                    self.print_end(**h)
                    util.beep(sound = 1)

            # move files from temp folders to target folders
            self.move_files(app_id)
            self.move_ws_files()
            print()



    def print_start(self, header):
        header = '  {} ...'.format(header)
        util.print_now(header)
        #
        return {'header' : header, 'start' : timeit.default_timer()}



    def print_end(self, header, start):
        timer   = int(round(timeit.default_timer() - start + 0.5, 0))
        header  = '{}{}'.format(header.ljust(30, '.'), (' ' + str(timer)).rjust(6, '.'))
        util.print_now(header, close = True)



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
        if self.arg_recent and self.actions['split']:
            self.actions['recent'] = False



    def get_root(self, app_id, folders = ''):
        transl = {
            '{$APP_ID}'     : app_id,
            '{$APP_ALIAS}'  : self.apex_apps[app_id]['app_alias'],
            '{$APP_NAME}'   : self.apex_apps[app_id]['app_name'],
            '{$APP_GROUP}'  : self.apex_apps[app_id]['app_group'],
        }
        app_folder  = '/{}/'.format(util.replace(self.config.apex_path_app, transl))
        path        = self.target_path.replace(self.app_folder, app_folder) + folders
        #
        return path.replace('//', '/')



    def get_root_ws(self, folders = ''):
        return (self.target_root + self.config.apex_workspace_dir + folders).replace('//', '/')



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
            util.print_header('APEX APPLICATIONS:', group if group != '-' else '')
            util.print_table(rows)

        # for cleanup files get some extra info
        self.enrich_ids = {}
        for row in self.conn.fetch_assoc(query.apex_id_names, **args):
            self.enrich_ids[row.component_id] = '{}: {}'.format(row.component_type, row.component_name)



    def show_recent_changes(self, app_id):
        alias = self.apex_apps[app_id]['app_alias']
        util.print_header('APP {}/{}, CHANGES SINCE {}:'.format(app_id, alias, self.today))
        #
        output  = self.execute_request('apex export -applicationid {$APP_ID} -list -changesSince {$TODAY}', app_id, lines = True)
        data    = util.parse_table(output)
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



    def export_recent(self, app_id):
        if len(self.comp_changed) == 0:
            return
        #
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

        # get rid of install files
        for file in util.get_files(self.get_root(app_id, 'application/install*.sql')):
            os.remove(file)

        # delete original (encoded) files, we can export/keep binaries instead
        if self.config.apex_delete_orig_files:
            source_dir = '{}f{}/application/shared_components/files/'.format(self.config.sqlcl_root, app_id)
            shutil.rmtree(source_dir, ignore_errors = True, onerror = None)
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
            for file in util.get_files(source_dir + '**/*.*'):
                # remove first 10 lines
                with open(file, 'rt', encoding = 'utf-8') as f:
                    old_content = f.readlines()
                with open(file, 'wt', encoding = 'utf-8', newline = '\n') as w:
                    w.writelines(old_content[10:])

                # move files
                if '/pages/p' in file:
                    os.rename(file, file.replace('/pages/p', '/pages/page_'))
            #
            shutil.copytree(source_dir, target_dir, dirs_exist_ok = True)
            shutil.rmtree(source_dir, ignore_errors = True, onerror = None)
        #
        return output



    def export_rest(self, app_id):
        # prepare target folders
        if os.path.exists(self.target_rest):
            shutil.rmtree(self.target_rest, ignore_errors = True, onerror = None)
        for dir in [self.target_rest]:
            os.makedirs(os.path.dirname(self.get_root(app_id, dir)), exist_ok = True)

        # export REST services
        lines = self.execute_request('apex rest', app_id, lines = True)
        for (i, line) in enumerate(lines):
            print(i, line)

        # split into dedicated files for each module
        lines       = lines.append('ORDS.DEFINE_MODULE')    # to process inside of the loop
        content     = []
        modules     = []
        append      = False
        #
        for (i, line) in enumerate(lines):
            if 'ORDS.DEFINE_MODULE' in line:
                if len(content):
                    modules.append(content)
                content = []
                append    = True
            if line.strip().startswith('COMMIT;') and lines[i + 1].startswith('END;') and lines[i + 2].startswith('Disconnected'):
                append = False
            if append:
                content.append(line)

        # create folders from service names
        groups = {}
        for content in modules:
            name = re.findall('[\'][^\']+[\']', content[1])[0].replace('\'', '')
            path = re.findall('[\'][^\']+[\']', content[2])[0].replace('\'', '').replace('/', '')
            file = self.target_rest + '/' + path + '/' + name + '.sql'
            #
            if not path in groups:
                groups[path] = []
            groups[path].append(name)
            #
            os.makedirs(os.path.dirname(file), exist_ok = True)
            with open(file, 'wt', encoding = 'utf-8', newline = '\n') as w:
                w.write('BEGIN\n' + ('\n'.join(content)).rstrip() + '\nEND;\n/\n')



    def export_files(self, app_id):
        # get target folder
        if app_id == 0:  # workspace files
            target_dir = self.get_root_ws(self.config.apex_path_files)
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



    def export_files_ws(self, app_id = 0):
        self.export_files(app_id = 0)



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
            target = file.replace('/f{}/workspace/'.format(app_id), '/' + self.config.apex_workspace_dir)
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



    def move_ws_files(self):
        source_dir = '{}workspace/'.format(self.config.sqlcl_root)
        target_dir = self.get_root_ws()
        #
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

        # get current file content
        old_content = ''
        with open(file, 'rt', encoding = 'utf-8') as f:
            old_content = f.read()
        new_content = old_content

        if self.config.apex_workspace_id and self.config.apex_workspace_id > 0:
            new_content = util.replace(new_content,
                ",p_default_workspace_id=>(\d+)",
                ",p_default_workspace_id=>{}".format(self.config.apex_workspace_id))

        # change page attributes to make changes in Git minimal
        if self.config.apex_authors and ('/pages/page_' in file or util.extract('/f(\d+).sql$', file)):
            new_content = util.replace(new_content,
                ",p_last_updated_by=>'([^']+)'",
                ",p_last_updated_by=>'{}'".format(self.config.apex_authors))
        #
        if self.config.apex_timestamps and ('/pages/page_' in file or util.extract('/f(\d+).sql$', file)):
            new_content = util.replace(new_content,
                ",p_last_upd_yyyymmddhh24miss=>'(\d+)'",
                ",p_last_upd_yyyymmddhh24miss=>'{}'".format(self.config.apex_timestamps))

        # translate id to more meaningful names
        for component_id, component_name in self.enrich_ids.items():
            new_content = new_content.replace (
                '.id({})\n'.format(component_id),
                '.id({})  -- {}\n'.format(component_id, component_name))

        # store new content in the same file
        if new_content != old_content:
            with open(file, 'wt', encoding = 'utf-8', newline = '\n') as w:
                w.write(new_content)



    def execute_request(self, request, app_id, lines = False):
        request = util.replace(request, {
            '{$APP_ID}'         : app_id,
            '{$TODAY}'          : self.today,
            '{$FORMAT_JSON}'    : ',READABLE_JSON' if self.config.apex_format_json else '',
            '{$FORMAT_YAML}'    : ',READABLE_YAML' if self.config.apex_format_yaml else '',
            '{$COMPONENTS}'     : ' '.join(self.comp_changed),
        })
        request = 'SET LINESIZE 200;\n{};\n'.format(request)
        #
        return util.cleanup_sqlcl(self.conn.sqlcl_request(request), lines = lines)



if __name__ == "__main__":
    # parse arguments
    parser = argparse.ArgumentParser(add_help = False)

    # actions and flags
    group = parser.add_argument_group('MAIN ACTIONS')
    group.add_argument('-recent',       help = 'Show components changed in # days',     type = util.is_boolstr, nargs = '?')
    group.add_argument('-full',         help = 'Export full application export',                                nargs = '?', const = True, default = False)
    group.add_argument('-split',        help = 'Export splitted export (components)',                           nargs = '?', const = True, default = False)
    group.add_argument('-embedded',     help = 'Export Embedded Code report',                                   nargs = '?', const = True, default = False)
    group.add_argument('-rest',         help = 'Export REST services',                                          nargs = '?', const = True, default = False)
    group.add_argument('-files',        help = 'Export application files in binary form',                       nargs = '?', const = True, default = False)
    group.add_argument('-files_ws',     help = 'Export workspace files in binary form',                         nargs = '?', const = True, default = False)
    group.add_argument('-only',         help = 'Proceed with passed actions only',                              nargs = '?', const = True, default = False)
    group.add_argument('-fetch',        help = 'Fetch Git changes before patching',                             nargs = '?', const = True, default = False)
    #
    group = parser.add_argument_group('NEGATING ACTIONS')
    group.add_argument('-nofull',       help = 'Skip full export',                                              nargs = '?', const = True, default = False)
    group.add_argument('-nosplit',      help = 'Skip splitted export',                                          nargs = '?', const = True, default = False)
    group.add_argument('-noembedded',   help = 'Skip Embedded Code report',                                     nargs = '?', const = True, default = False)
    group.add_argument('-norest',       help = 'Skip REST services',                                            nargs = '?', const = True, default = False)
    group.add_argument('-nofiles',      help = 'Skip application files',                                        nargs = '?', const = True, default = False)
    group.add_argument('-nofiles_ws',   help = 'Skip workspace files',                                          nargs = '?', const = True, default = False)

    # env details
    group = parser.add_argument_group('SPECIFY ENVIRONMENT DETAILS')
    group.add_argument('-schema',       help = '',                                                              nargs = '?')
    group.add_argument('-env',          help = 'Source environment (for overrides)',                            nargs = '?')
    group.add_argument('-key',          help = 'Key or key location for passwords',                             nargs = '?')
    #
    group = parser.add_argument_group('LIMIT SCOPE')
    group.add_argument('-ws',           help = 'Limit APEX workspace',                                          nargs = '?')
    group.add_argument('-group',        help = 'Limit application group',                                       nargs = '?')
    group.add_argument('-app',          help = 'Limit list of application(s)',          type = int,             nargs = '*', default = [])
    #
    Export_APEX(parser)

