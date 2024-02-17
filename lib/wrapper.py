# coding: utf-8
import sys, os, subprocess
import oracledb
from lib import util
from lib import queries_wrapper as query



class Oracle:

    def __init__(self, tns, debug = False):
        self.conn   = None    # recent connection link
        self.curs   = None    # recent cursor
        self.cols   = []      # recent columns mapping (name to position) to avoid associative arrays
        self.desc   = {}      # recent columns description (name, type, display_size, internal_size, precision, scale, null_ok)
        self.tns    = {
          'lang'    : '.AL32UTF8',
        }
        self.tns.update(tns)
        self.tns['host'] = self.tns['hostname'] if 'hostname' in self.tns else None

        # debug mode from config file or from caller
        self.debug = self.tns['debug'] if 'debug' in self.tns else False
        if not self.debug:
            self.debug = debug
        #

        # auto connect
        self.connect()
        self.show_versions()



    def __del__(self):
        # disconnect
        pass



    def connect(self):
        os.environ['NLS_LANG'] = self.tns['lang']

        # use wallet to connect
        if 'wallet' in self.tns and len(self.tns['wallet']) > 0:
            wallet = os.path.abspath(self.tns['wallet']).rstrip('.zip')
            #
            # @TODO: CHECK IF WALLET EXISTS
            #
            self.conn = oracledb.connect(
                user            = self.tns['user'],
                password        = self.tns['pwd'],
                dsn             = self.tns['service'],
                config_dir      = wallet,
                wallet_location = wallet,
                wallet_password = self.tns['wallet_pwd'],
                encoding        = 'utf8'
            )
            return



    def show_versions(self):
        util.header('CONNECTED TO {}:'.format(self.tns['desc']))

        # get database and apex versions
        version_apex, version_db = '', ''
        try:
            version_apex  = self.fetch_value(query.query_version_apex)
            version_db    = self.fetch_value(query.query_version_db)
        except Exception:
            version_db    = self.fetch_value(query.query_version_db_old)
        #
        #print('        THIN | {}'.format('Y' if oracledb.is_thin_mode() else ''))
        print('    DATABASE | {}'.format('.'.join(version_db.split('.')[0:2])))
        print('        APEX | {}'.format('.'.join(version_apex.split('.')[0:2])))
        print()



    def fetch(self, query, limit = 0, **binds):
        self.curs = self.conn.cursor()
        if limit > 0:
            self.curs.arraysize = limit
            data = self.curs.execute(query.strip(), **binds).fetchmany(limit)
        else:
            self.curs.arraysize = 5000
            data = self.curs.execute(query.strip(), **binds).fetchall()
        #
        self.cols = [row[0].lower() for row in self.curs.description]
        self.desc = {}
        for row in self.curs.description:
            self.desc[row[0].lower()] = row
        #
        return data



    def fetch_value(self, query, **binds):
        self.curs = self.conn.cursor()
        self.curs.arraysize = 1
        data = self.curs.execute(query.strip(), **binds).fetchmany(1)
        #
        self.cols = [row[0].lower() for row in self.curs.description]
        self.desc = {}
        for row in self.curs.description:
            self.desc[row[0].lower()] = row
        #
        if len(data):
            return data[0][0]
        return None



    def commit(self):
        try:
            self.conn.commit()
        except:
            return



    def rollback(self):
        try:
            self.conn.rollback()
        except:
            return

