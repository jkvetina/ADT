# coding: utf-8
import sys, os, traceback
import oracledb         # pip3 install oracledb     --upgrade
import sshtunnel
#
from lib import util
from lib import queries_wrapper as query

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

class Oracle:

    def __init__(self, tns, config = {}, debug = False, ping_sqlcl = False, silent = False):
        self.conn       = None    # recent connection link
        self.curs       = None    # recent cursor
        self.cols       = []      # recent columns mapping (name to position) to avoid associative arrays
        self.desc       = {}      # recent columns description (name, type, display_size, internal_size, precision, scale, null_ok)
        self.config     = config
        self.silent     = silent
        self.tns        = {
            'lang'      : '.AL32UTF8',
        }
        if not isinstance(tns, dict):
            util.raise_error('DB_CONNECT EXPECTS DICTIONARY')
        #
        self.tns.update(tns)
        self.tns        = util.Attributed(self.tns)
        self.tns.host   = self.tns.hostname if 'hostname' in self.tns else None
        self.versions   = {}

        # debug mode from config file or from caller
        self.debug = self.tns.debug if 'debug' in self.tns else False
        if not self.debug:
            self.debug = debug

        # fix for proxy users
        import re
        if '[' in self.tns.get('schema', ''):
            self.tns['schema'] = re.sub(r'(.*)\[(.*)', r'"\1"[\2', self.tns['schema'])
        if '[' in self.tns.get('schema_db', ''):
            self.tns['schema_db'] = re.sub(r'(.*)\[(.*)', r'"\1"[\2', self.tns['schema_db'])
        if '[' in self.tns.get('schema_apex', ''):
            self.tns['schema_apex'] = re.sub(r'(.*)\[(.*)', r'"\1"[\2', self.tns['schema_apex'])
        if '[' in self.tns.get('user', ''):
            self.tns['user'] = re.sub(r'(.*)\[(.*)', r'"\1"[\2', self.tns['user'])

        # auto connect
        if not self.silent:
            schema  = self.tns.get('proxy', '') or self.tns.get('schema', '') or self.tns.get('user', '')
            env     = self.tns.get('env', '')
            util.print_header('CONNECTING TO {}, {}:'.format(schema, env))
        #
        self.connect()
        self.get_versions()

        # test SQLcl connectivity
        if ping_sqlcl:  # or self.tns.get('workspace', None) != None):
            output  = self.sqlcl_request('DESC DUAL')
            lines   = output.splitlines()[:5]
            #
            for i, line in enumerate(lines):
                if line.startswith('Connected.'):
                    self.versions['SQLCL'] = lines[0].split(' ')[2]
                    break

        # show versions
        if not self.silent:
            util.print_pipes(self.versions)



    def __del__(self):
        self.disconnect()



    def connect(self):
        self.disconnect()       # to use as reconnect
        os.environ['NLS_LANG'] = self.tns.lang

        # might need to adjust client for classic connections or for DPY-3015 password issues
        # https://python-oracledb.readthedocs.io/en/latest/user_guide/troubleshooting.html#dpy-3015
        self.thick = self.tns.get('thick', None)
        if self.thick in ('Y', 'CLIENT_HOME', 'ORACLE_HOME'):
            self.thick = os.environ.get('CLIENT_HOME') or os.environ.get('ORACLE_HOME') or 'Y'
        #
        if self.thick != None and self.thick != '':
            if os.path.exists(self.thick):
                oracledb.init_oracle_client(lib_dir = self.thick)
            else:
                oracledb.init_oracle_client()

        # use wallet to connect
        if 'wallet' in self.tns and len(self.tns.wallet) > 0:
            self.tns.wallet = self.tns.wallet.replace('~/', os.path.expanduser('~') + '/')
            self.tns.wallet = os.path.abspath(self.tns.wallet).rstrip('.zip')
            if not os.path.exists(self.tns.wallet):
                util.raise_error('INVALID WALLET', self.tns.wallet)
            #
            try:
                self.conn = oracledb.connect(
                    user            = self.tns.get('proxy', '') or self.tns.user,
                    password        = self.tns.pwd if self.tns.get('pwd!', '') != 'Y' else util.decrypt(self.tns.pwd, self.tns.key),
                    dsn             = self.tns.service,
                    config_dir      = self.tns.wallet,
                    wallet_location = self.tns.wallet,
                    wallet_password = self.tns.wallet_pwd if self.tns.get('wallet_pwd!', '') != 'Y' else util.decrypt(self.tns.wallet_pwd, self.tns.key)
                )
            except Exception:
                if self.debug:
                    print(traceback.format_exc())
                    print(sys.exc_info()[2])
                util.raise_error('CONNECTION FAILED', self.get_error_code())
            return

        # open SSH tunnel
        if len(self.tns.get('gateway') or '') > 0:
            #with sshtunnel.SSHTunnelForwarder (
            with sshtunnel.open_tunnel (
                (self.tns['gateway'], self.tns['gateway_port']),
                ssh_username        = self.tns['ssh_user'],
                ssh_password        = self.tns['ssh_pwd'],
                remote_bind_address = (self.tns['remote_bind'], self.tns['remote_port']),
                local_bind_address  = (self.tns['local_bind'],  self.tns['local_port'])
            ) as server:
                server.start()
                self.tns['host']    = self.tns.get('local_bind') or '127.0.0.1'
                self.tns['port']    = self.tns.get('local_port') or server.local_bind_port
                #
                print('  -> SSH TUNNEL ENABLED\n')
                self.connect__()
        else:
            self.connect__()



    def connect__(self):
        if not 'dsn' in self.tns:
            if self.tns.get('sid', '') != '':
                self.tns.dsn = oracledb.makedsn(self.tns.host, self.tns.port, sid = self.tns.sid)
            else:
                self.tns.dsn = oracledb.makedsn(self.tns.host, self.tns.port, service_name = self.tns.service)
        #
        try:
            self.conn = oracledb.connect(
                user        = self.tns.get('proxy', '') or self.tns.user,
                password    = self.tns.pwd if self.tns.get('pwd!', '') != 'Y' else util.decrypt(self.tns.pwd, self.tns.key),
                dsn         = self.tns.dsn
            )
            self.commit()
            #
        except Exception:
            if self.debug:
                print(traceback.format_exc())
                print(sys.exc_info()[2])
            util.raise_error('CONNECTION FAILED', self.get_error_code())

        # convert CLOB to string
        self.conn.outputtypehandler = self.output_type_handler



    def output_type_handler(self, cursor, name, defaultType, size, precision, scale):
        if defaultType == oracledb.CLOB:
            return cursor.var(oracledb.LONG_STRING, arraysize = cursor.arraysize)



    def disconnect(self):
        if self.conn:
            try:
                self.conn.close()
            except:
                pass



    def get_error_code(self):
        message = ''
        for line in traceback.format_exc().splitlines():
            for search in (': ORA-', ': DPY-',):
                chunks = line.split(search)
                if len(chunks) > 1:
                    message = '{}{}\n'.format(search.replace(': ', ''), chunks[1])
        return message



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
        #
        if self.thick:
            version = util.extract(r'(\d+_\d+)$', self.thick).replace('_', '.')
            self.versions['THICK'] = version or self.thick



    def sqlcl_request(self, request, root = None, silent = False):
        if isinstance(request, list):
            request = '\n'.join(request)

        # prepare connection string
        if 'wallet' in self.tns:
            request_conn = 'connect -cloudconfig "{}.zip" {}/"{}"@{}\n'.format(*[
                self.tns.wallet.rstrip('.zip'),
                self.tns.get('proxy') or self.tns.user,
                self.tns.pwd if self.tns.get('pwd!', '') != 'Y' else util.decrypt(self.tns.pwd, self.tns.key),
                self.tns.service
            ])
        else:
            request_conn = 'connect {}/"{}"@{}:{}/{}\n'.format(*[
                self.tns.get('proxy') or self.tns.user,
                self.tns.pwd if self.tns.get('pwd!', '') != 'Y' else util.decrypt(self.tns.pwd, self.tns.key),
                self.tns.host,
                self.tns.port,
                self.tns.sid if self.tns.get('sid', '') != '' else self.tns.service
            ])

        # prepare process for normal platforms
        root    = os.path.abspath(root or self.config.sqlcl_root)
        request = '{}\n{}\nexit;\n'.format(request_conn, request)
        process = 'sql /nolog <<EOF\n{}EOF'.format(request)

        # for Windows we have to use the temp file
        if os.name == 'nt':
            process     = 'sql /nolog @{}'.format(self.config.sqlcl_temp_file)
            full_tmp    = root + '/' + self.config.sqlcl_temp_file
            #
            with open(full_tmp, 'wt', encoding = 'utf-8', newline = '\n') as f:
                f.write(request)
            if not os.path.exists(full_tmp):
                util.raise_error('TEMP FILE FAILED')

        # run SQLcl and capture the output
        command = 'cd "{}"{}{}'.format(
            root,
            ' && ' if os.name == 'nt' else '; ',
            process
        )
        #
        result  = util.run_command(command, silent = silent).strip()
        failed  = 'Error starting at line' in result
        #
        if (self.debug or failed):
            print()
            util.print_header('REQUEST:')
            print(command.rstrip())
            if os.name == 'nt':
                print(request.rstrip())
            print()
            util.print_header('RESULT:')
            print(result)
            print()
            #
            if failed:
                error = ''
                lines = result.splitlines()
                for i, line in enumerate(lines):
                    if 'Error report' in line:
                        error = lines[i + 1]
                util.raise_error('COMMAND ERROR', error.upper())

        # for Windows remove temp file
        if os.name == 'nt' and os.path.exists(full_tmp):
            os.remove(full_tmp)
        #
        return result



    def fetch(self, query, limit = 0, **binds):
        self.curs = self.conn.cursor()
        if limit > 0:
            self.curs.arraysize = limit
            data = self.curs.execute(query.strip(), **self.get_binds(query, binds)).fetchmany(limit)
        else:
            self.curs.arraysize = 5000
            data = self.curs.execute(query.strip(), **self.get_binds(query, binds)).fetchall()
        #
        self.cols = [row[0].lower() for row in self.curs.description]
        self.desc = {}
        for row in self.curs.description:
            self.desc[row[0].lower()] = row
        #
        return data



    def fetch_clob_result(self, query, **binds):
        self.curs   = self.conn.cursor()
        result      = self.curs.var(oracledb.DB_TYPE_CLOB)
        #
        self.curs.execute(query.strip(), result = result, **self.get_binds(query, binds))
        #
        return result.getvalue()



    def cursor(self):
        self.curs = self.conn.cursor()
        return self.curs



    def row_as_dict(self, cursor):
        columns = [d[0].lower() for d in cursor.description]
        def row(*args):
            return util.Attributed(dict(zip(columns, args)))
        return row



    def get_binds(self, query, binds):
        # remove passed arguments which are not in the query
        pass_binds = {}
        for key, value in binds.items():
            if ':{}'.format(key) in query:
                pass_binds[key] = None if value == '' else value
        return pass_binds



    def debug_query(self, query, **binds):
        binds = self.get_binds(query, binds)
        for arg in sorted(binds.keys(), reverse = True):
            value = binds[arg]
            value = "'{}'".format(value) if isinstance(value, str) else value
            value = 'NULL' if value == "''" else value
            query = query.replace(':' + arg, str(value))
        return query.strip()



    def fetch_assoc(self, query, limit = 0, **binds):
        self.curs = self.conn.cursor()
        #
        try:
            binds   = self.get_binds(query, binds)
            h       = self.curs.execute(query.strip(), **binds)
            #
        except oracledb.DatabaseError as e:
            if self.debug:
                print('#' * 80)
                print(self.debug_query(query, **binds))
                print()
            #
            print('#' * 80)
            print('CALLSTACK:')
            for row in util.get_callstack():
                print('  @{} {}'.format(row[0], row[1]))
            #
            util.raise_error('QUERY_ERROR', str(e).splitlines()[0])
        #
        self.cols = [row[0].lower() for row in self.curs.description]
        self.desc = {}
        for row in self.curs.description:
            self.desc[row[0].lower()] = row
        #
        self.curs.rowfactory = self.row_as_dict(self.curs)
        #
        if limit > 0:
            self.curs.arraysize = limit
            return h.fetchmany(limit)
        #
        self.curs.arraysize = 5000
        return h.fetchall()



    def fetch_value(self, query, **binds):
        self.curs = self.conn.cursor()
        self.curs.arraysize = 1
        data = self.curs.execute(query.strip(), **self.get_binds(query, binds)).fetchmany(1)
        #
        self.cols = [row[0].lower() for row in self.curs.description]
        self.desc = {}
        for row in self.curs.description:
            self.desc[row[0].lower()] = row
        #
        if len(data):
            return data[0][0]
        return None



    def execute(self, query, **binds):
        self.curs = self.conn.cursor()
        try:
            r = self.curs.execute(query.strip(), **self.get_binds(query, binds))
            return r
        except oracledb.DatabaseError as e:
            if self.debug:
                print('#' * 80)
                print(self.debug_query(query, **binds))
                print()
            #
            print('#' * 80)
            print('CALLSTACK:')
            for row in util.get_callstack():
                print('  @{} {}'.format(row[0], row[1]))
            #
            util.raise_error('QUERY_ERROR', str(e).splitlines()[0])



    def executemany(self, query, **binds):
        self.curs = self.conn.cursor()
        return self.curs.executemany(query.strip(), **self.get_binds(query, binds))



    def drop_object(self, object_type, object_name):
        try:
            self.execute('DROP {} {}'.format(object_type, object_name))
        except:
            pass



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

