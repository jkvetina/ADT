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

        # check for APEX stuff
        find_app    = re.search('/f(\d+)/', self.file)
        find_page   = re.search('/f\d+/application/pages/page_(\d+)\.sql$', self.file)
        app_id      = int(find_app.group(1))  if find_app  else None
        page_id     = int(find_page.group(1)) if find_page else None
        #
        if app_id:
            # APEX stuff
            self.is_apex        = True
            self.apex_app_id    = app_id
            self.apex_page_id   = page_id
        else:
            # database object
            self.is_object      = True
            self.object_name    = os.path.basename(file).split('.')[0].upper()

            # assume that database objects are just on one folder
            # so the second folder represents object type, the third represents optional group
            folders = os.path.dirname(file.replace(config.path_objects, '')).split('/')
            #
            self.folder         = folders[0]
            self.group          = folders[1] if len(folders) > 1 else ''
            self.object_type    = ''

            # fix type check for SPEC/BODY
            folders = {}
            for object_type, info in config.object_types.items():
                folder, ext = info
                if config.path_objects + folder in file:
                    folders[ext] = object_type
            #
            for ext in sorted(folders.keys(), key = len):
                if ext in file:
                    self.object_type = folders[ext]

        #'hash_old'    : '',
        #'hash_new'    : ''

