# coding: utf-8
import datetime

class Config(dict):

    def __init__(self):
        self.repo_path          = ''
        self.branch             = ''
        self.schema             = ''
        self.apex_schema        = ''
        self.apex_workspace     = ''
        self.path_objects       = ''
        self.path_apex          = ''
        self.git_depth          = 500

        # prepare date formats
        self.today              = datetime.datetime.today().strftime('%Y-%m-%d')        # YYYY-MM-DD
        self.today_full         = datetime.datetime.today().strftime('%Y-%m-%d %H:%M')  # YYYY-MM-DD HH24:MI
        self.today_full_raw     = datetime.datetime.today().strftime('%Y%m%d%H%M') + '00'

    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

