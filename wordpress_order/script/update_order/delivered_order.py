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
port = config.get('dbaccess', 'port')  # verify if it's necessary: getint
name = config.get('dbaccess', 'connector_name')

# -----------------------------------------------------------------------------
# Connect to ODOO:
# -----------------------------------------------------------------------------
odoo = erppeek.Client(
    'http://%s:%s' % (server, port),
    db=dbname, user=user, password=pwd,
    )

# Pool used:
order_pool = odoo.model('sale.order')
order_ids = order_pool.search([
    ('carrier_soap_state', '=', 'sent'),
])

if not order_ids:
    print('No order in sent state for now')
    sys.exit()
print('Found sent order # %s' % len(order_ids))

for order_id in order_ids:
    result = order_pool.shipments_get_tracking_result(order_id)
    print(result or ('Order %s updated!' % order_id))
print('Check order delivery done!')
