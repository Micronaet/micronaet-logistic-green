import os
import sys
from datetime import datetime, timedelta
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
name = config.get('dbaccess', 'connector_name')

# -----------------------------------------------------------------------------
# Connect to ODOO:
# -----------------------------------------------------------------------------
odoo = erppeek.Client(
    'http://%s:%s' % (server, port),
    db=dbname, user=user, password=pwd,
    )

# Pool used:
connector_pool = odoo.model('wp.connector')
connector_ids = connector_pool.search([('name', '=', name)])
if not connector_ids:
    print('Error no %s connector found' % name)
    sys.exit()
print('Found connector name: %s' % name)

now = ('%s' % (datetime.now() - timedelta(days=1)))[:10]
after = '%sT00:00:00Z' % now
print('Updating from %s' % after)

odoo.context = {
    'extend_params': {
        'after': after,

        'per_page': 50,
        'page': 1,
    },
    'end_page': 50,
}

connector_pool.button_load_order(connector_ids)
print('Update done!')

