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

order_ids = order_pool.search([
    ('wp_status', 'in', (
        'delivered', 'on-hold', 'pending', 'processing', 'sent-to-gsped')),
])
total = len(order_ids)
print('Update order status [Tot. %s]' % total)
import pdb; pdb.set_trace()
i = 0
for order in order_pool.browse(order_ids):
    i += 1
    name = order.name
    try:
        order.wp_wf_refresh_status()
        print('[INFO] Refresh order: %s [%s] (%s/%s)' % (
            name, order.wp_status, i, total))
    except:
        print('[ERR] Cannot Refresh order: %s [%s] (%s/%s)' % (
            name, order.wp_status, i, total))

