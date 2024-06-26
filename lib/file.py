# coding: utf-8
import sys, os, re
#
from lib import util

class File(util.Attributed):

    def __init__(self, file, config = {}):
        self.file           = file.replace('\\', '/').replace('//', '/')
        self.is_object      = False
        self.is_apex        = False
        self.is_template    = False
        self.is_script      = False

        object_types = config.object_types.items()

        # change file name on alternative file names (/type.name.sql) to correctly detect object type
        base = os.path.basename(file).split('.')
        if len(base) > 2:
            for object_type, info in object_types:
                folder, ext = info
                if folder.rstrip('/') == base[0]:
                    file = file.replace('/{}.{}'.format(base[0], base[1]), '/{}/{}'.format(base[0], base[1]))
                    break

        # check for APEX stuff
        app_id      = util.extract_int(config.apex_path_app_id, file.replace(config.path_apex, ''))
        #apex_root   = self.get_root(app_id, remove_root = True)
        find_page   = re.search(r'/pages/page_(\d+)\.sql$', self.file)
        page_id     = int(find_page.group(1)) if app_id and find_page else None
        #
        if app_id:
            # APEX stuff
            self.is_apex        = True
            self.apex_app_id    = app_id
            self.apex_page_id   = page_id
        #
        else:
            # detect object type and fix type check for SPEC/BODY
            self.object_type = None
            folders = {}
            for object_type, info in object_types:
                folder, ext = info
                if '/' + folder in file:
                    folders[ext] = object_type
            #
            for ext in sorted(folders.keys(), key = len):
                if ext in file:
                    self.object_type = folders[ext]

            # database object
            if self.object_type:
                self.is_object      = True
                self.object_name    = os.path.basename(file).split('.')[0].upper()

                # assume that database objects are just on one folder
                # so the second folder represents object type, the third represents optional group
                folders = os.path.dirname(file.replace(config.path_objects, '')).split('/')
                #
                self.folder         = folders[0]
                self.group          = folders[1] if len(folders) > 1 else ''
                self.object_code    = '{}.{}'.format(self.object_type, self.object_name)

