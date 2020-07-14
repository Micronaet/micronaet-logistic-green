import os
from datetime import datetime
import erppeek
import ConfigParser

# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
# From config file:
cfg_file = os.path.expanduser('./openerp.cfg')

config = ConfigParser.ConfigParser()
config.read([cfg_file])
dbname = config.get('dbaccess', 'dbname')
user = config.get('dbaccess', 'user')
pwd = config.get('dbaccess', 'pwd')
server = config.get('dbaccess', 'server')
port = config.get('dbaccess', 'port')   # verify if it's necessary: getint

# -----------------------------------------------------------------------------
# Connect to ODOO:
# -----------------------------------------------------------------------------
odoo = erppeek.Client(
    'http://%s:%s' % (server, port),
    db=dbname, user=user, password=pwd,
    )

# Pool used:
connector_pool = odoo.model('wp.connector')
name = 'Vendita Piante [OLD]'
connector_ids = connector_pool.search([('name', '=', name)])
if not connector_ids:
    print('Error no %s connector found' % name)

now = ('%s' % datetime.now())[:19].replace(' ', 'T')
now = now + 'T'

odoo.context = {
    'extend_params': {
        'after': now,

        'per_page': 50,
        'page': 1,
    },
    'end_page': 50,
}

import pdb; pdb.set_trace()
connector_pool.button_load_order(connector_ids)

