import os
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
order_pool = odoo.model('sale.order')

print('Update order status')
order_ids = order_pool.search([
    ('wp_status', 'in', (
        'delivered', 'on-hold', 'pending', 'processing', 'sent-to-gsped')),
])
import pdb; pdb.set_trace()
for order in order_pool.browse(order_ids):
    name = order['name']
    print('Update order: %s [%s]' % (name, order.wp_status))
    order.wp_wf_refresh_status()
