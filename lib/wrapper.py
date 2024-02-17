# coding: utf-8
import sys, os, subprocess
import oracledb         # pip3 install oracledb     --upgrade
#
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
        self.versions = {}

        # temp file for Windows
        self.sqlcl_root         = './'
        self.sqlcl_temp_file    = './sqlcl.{}.tmp'.format('')

        # auto connect
        self.connect()
        self.get_versions()

        # test SQLcl connectivity
        output  = self.sqlcl_request('DESC DUAL')
        lines   = output.splitlines()[:5]
        #
        for i, line in enumerate(lines):
            if line.startswith('Connected.'):
                self.versions['SQLCL'] = lines[0].split(' ')[2]
                break

        # show versions
        util.header('CONNECTED TO {}:'.format(self.tns['desc']))
        util.debug_table(self.versions)



    def __del__(self):
        if self.conn:
            self.conn.close()  # disconnect



    def connect(self):
        os.environ['NLS_LANG'] = self.tns['lang']

        # might need to adjust client for classic connections
        if 'thick' in self.tns and len(self.tns['thick']) > 0:
            if isinstance(self.tns['thick'], str):
                client = os.path.abspath(os.path.dirname(self.tns['thick']))
                if os.path.exists(client):
                    try:
                        oracledb.init_oracle_client(lib_dir = client)
                        print('USING THICK CLIENT...\n{}'.format(client))
                    except:
                        try:
                            oracledb.init_oracle_client()  # for password issues
                            print('USING THICK CLIENT...')
                        except:
                            pass

        # use wallet to connect
        if 'wallet' in self.tns and len(self.tns['wallet']) > 0:
            wallet = os.path.abspath(self.tns['wallet']).rstrip('.zip')
            #
            # @TODO: CHECK IF WALLET EXISTS
            #
            self.conn = oracledb.connect(
                user            = self.tns['user'],
                password        = self.tns['pwd'] if self.tns['plain'] else util.decrypt(self.tns['pwd'], self.tns['key']),
                dsn             = self.tns['service'],
                config_dir      = wallet,
                wallet_location = wallet,
                wallet_password = self.tns['wallet_pwd'] if self.tns['plain'] else util.decrypt(self.tns['wallet_pwd'], self.tns['key']),
                encoding        = 'utf8'
            )
            return

        # classic connect
        if not 'dsn' in self.tns:
            if 'sid' in self.tns:
                self.tns['dsn'] = oracledb.makedsn(self.tns['host'], self.tns['port'], sid = self.tns['sid'])
            else:
                self.tns['dsn'] = oracledb.makedsn(self.tns['host'], self.tns['port'], service_name = self.tns['service'])
        #
        self.conn = oracledb.connect(
            user        = self.tns['user'],
            password    = self.tns['pwd'] if self.tns['plain'] else util.decrypt(self.tns['pwd'], self.tns['key']),
            dsn         = self.tns['dsn'],
            encoding    = 'utf8'
        )



    def get_versions(self):
        # get database and apex versions
        version_apex, version_db = '', ''
        try:
            version_apex  = self.fetch_value(query.query_version_apex)
            version_db    = self.fetch_value(query.query_version_db)
        except Exception:
            version_db    = self.fetch_value(query.query_version_db_old)
        #
        self.versions['DATABASE']   = '.'.join(version_db.split('.')[0:2])
        self.versions['APEX']       = '.'.join(version_apex.split('.')[0:2])



    def sqlcl_request(self, request):
        if isinstance(request, list):
            request = '\n'.join(request)

        # prepare connection string
        if 'wallet' in self.tns:
            request_conn = 'connect -cloudconfig {}.zip {}/"{}"@{}\n'.format(*[
                self.tns['wallet'].rstrip('.zip'),
                self.tns['user'],
                self.tns['pwd'] if self.tns['plain'] else util.decrypt(self.tns['pwd'], self.tns['key']),
                self.tns['service']
            ])
        else:
            request_conn = 'connect {}/"{}"@{}:{}/{}\n'.format(*[
                self.tns['user'],
                self.tns['pwd'] if self.tns['plain'] else util.decrypt(self.tns['pwd'], self.tns['key']),
                self.tns['host'],
                self.tns['port'],
                self.tns['sid'] if 'sid' in self.tns else self.tns['service']
            ])

        # prepare process for normal platforms
        request = '{}\n{}\nexit;\n'.format(request_conn, request)
        process = 'sql /nolog <<EOF\n{}EOF'.format(request)

        # for Windows we have to use the temp file
        if os.name == 'nt':
            process = 'sql /nolog @' + self.sqlcl_temp_file
            with open(self.sqlcl_temp_file, 'wt', encoding = 'utf-8', newline = '\n') as f:
                f.write(request)

        # run SQLcl and capture the output
        command = 'cd "{}"{}{}'.format(
            os.path.abspath(self.sqlcl_root),
            ' && ' if os.name == 'nt' else '; ',
            process
        )
        #
        if self.debug:
            util.header('REQUEST:')
            print(command)
            if os.name == 'nt':
                print(request)
            print()
        #
        result  = subprocess.run(command, shell = True, capture_output = True, text = True)
        output  = (result.stdout or '').strip()
        #
        if self.debug:
            util.header('RESULT:')
            print(result.stdout)
            print()

        # for Windows remove temp file
        if os.name == 'nt' and os.path.exists(self.sqlcl_temp_file):
            os.remove(apex_tmp)
        #
        return output



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

