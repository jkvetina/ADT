# coding: utf-8
import sys, os, subprocess, collections
import oracledb

class Oracle:

  def __init__(self, args, debug = False, client = None):
    self.client = client
    self.conn   = None    # recent connection link
    self.curs   = None    # recent cursor
    self.cols   = []      # recent columns mapping (name to position) to avoid associative arrays
    self.desc   = {}      # recent columns description (name, type, display_size, internal_size, precision, scale, null_ok)
    self.tns    = {
      'lang'    : '.AL32UTF8',
    }
    self.tns.update(args)

    # check args
    if debug:
      print('ARGS:\n--')
      for (key, value) in self.tns.items():
        if not (key in ('pwd', 'wallet_pwd')):
          print('{:>8} = {}'.format(key, value))
      print('')

    # auto connect
    self.connect()



  def connect(self):
    os.environ['NLS_LANG'] = self.tns['lang']

    # try wallet first
    if 'wallet' in self.tns and self.tns['wallet']:
      self.conn = oracledb.connect(user = self.tns['user'], password = self.tns['pwd'], dsn = self.tns['dsn'],\
        wallet_location = self.tns['wallet'], wallet_password = self.tns['wallet_pwd'], encoding = 'utf8')
      #
      return

    # might need to adjust client for classic connections
    if not self.client:
      # find instant client
      try:
        self.client = subprocess.check_output('where oci.dll', shell = True).decode('utf-8').split()[0]
      except:
        pass
    #
    try:
      oracledb.init_oracle_client(lib_dir = os.path.dirname(self.client))
      print('CLIENT =', os.path.dirname(self.client))
    except:
      try:
        oracledb.init_oracle_client()  # for password issues
      except:
        pass

    # connect
    if not 'dsn' in self.tns:
      if 'sid' in self.tns:
        #self.tns['dsn'] = cx_Oracle.makedsn(self.tns['host'], self.tns['port'], sid = self.tns['sid'])
        self.tns['dsn'] = oracledb.makedsn(self.tns['host'], self.tns['port'], sid = self.tns['sid'])
      else:
        self.tns['dsn'] = oracledb.makedsn(self.tns['host'], self.tns['port'], service_name = self.tns['service'])
      #self.tns['dsn'] = '{}:{}/{}'.format(self.tns['host'], self.tns['port'], self.tns['sid'])
    #self.conn = cx_Oracle.connect(user = self.tns['user'], password = self.tns['pwd'], dsn = self.tns['dsn'], encoding = 'utf8')
    self.conn = oracledb.connect(user = self.tns['user'], password = self.tns['pwd'], dsn = self.tns['dsn'], encoding = 'utf8')



  def get_binds(self, query, autobind):
    out = {}
    try:
      binds = autobind._asdict()
    except:
      binds = autobind
    #
    for key in binds:  # convert namedtuple to dict
      if ':' + key in query:
         out[key] = binds[key] if key in binds else ''
    return out



  def execute(self, query, autobind = None, **binds):
    if autobind and len(autobind):
      binds = self.get_binds(query, autobind)
    #
    self.curs = self.conn.cursor()
    return self.curs.execute(query.strip(), **binds)



  def executemany(self, query, binds):
    self.curs = self.conn.cursor()
    return self.curs.executemany(query.strip(), binds)



  def fetch(self, query, limit = 0, autobind = None, **binds):
    if autobind and len(autobind):
      binds = self.get_binds(query, autobind)
    #
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



  def fetch_assoc(self, query, limit = 0, autobind = None, **binds):
    if autobind and len(autobind):
      binds = self.get_binds(query, autobind)
    #
    self.curs = self.conn.cursor()
    h = self.curs.execute(query.strip(), **binds)
    self.cols = [row[0].lower() for row in self.curs.description]
    self.desc = {}
    for row in self.curs.description:
      self.desc[row[0].lower()] = row
    #
    self.curs.rowfactory = collections.namedtuple('ROW', [d[0].lower() for d in self.curs.description])
    #
    if limit > 0:
      self.curs.arraysize = limit
      return h.fetchmany(limit)
    #
    self.curs.arraysize = 5000
    return h.fetchall()



  def fetch_value(self, query, autobind = None, **binds):
    if autobind and len(autobind):
      binds = self.get_binds(query, autobind)
    #
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
    return data



  def commit(self):
    try: self.conn.commit()
    except:
      return



  def rollback(self):
    try: self.conn.rollback()
    except:
      return

