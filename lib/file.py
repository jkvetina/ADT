# coding: utf-8
import sys, os, re
#
from lib import util

class File(util.Attributed):

    def __init__(self, file):
        self.file   = file.replace('\\', '/').replace('//', '/')
        #
        find_app    = re.search('/f(\d+)/', self.file)
        find_page   = re.search('/f\d+/application/pages/page_(\d+)\.sql$', self.file)
        app_id      = int(find_app.group(1))  if find_app  else None
        page_id     = int(find_page.group(1)) if find_page else None
        #
        self.object_type    = self.get_file_object_type(file)
        self.object_name    = self.get_file_object_name(file)
        self.apex_app_id    = app_id
        self.apex_page_id   = page_id



    def get_file_object_name(self, file):
        return os.path.basename(file).split('.')[0]



    def get_file_object_type(self, file):
        return ''

