import os
import woocommerce
import pickle
import urllib
import sys
import erppeek
import ConfigParser

# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
# From config file:
date_order = '2020-03-10'
dry_run = False

print('Clean before: %s' % date_order)
import pdb; pdb.set_trace()
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
    ('date_order', '<=', date_order),
    ('wp_status', 'in', (
        'delivered',
        'sent-to-gsped',
        # 'processing',
        # 'on-hold',
        # 'pending',
    )),
    ])

print('Order to be cleaned: %s' % len(order_ids))
now = ('%s' % datetime.now()).replace('\\', '_').replace(':', '').replace(
    ' ', '').replace('-', '_').replace('/', '_')
log_file = open('./log/export_%s.csv' % now, 'w')
for order in order_pool.browse(order_ids):
    # Update confirmed
    if dry_run:
        print('Marked completed: %s' % order.name)
    else:
        log_file.write('%s (da %s a completed)\n' % (
            order.name,
            order.wp_status,
        ))
        order.wp_wf_completed()
