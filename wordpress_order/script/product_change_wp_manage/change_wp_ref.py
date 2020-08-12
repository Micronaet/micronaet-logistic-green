import os
import sys
from datetime import datetime, timedelta
import erppeek
import ConfigParser

# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
# From config file:
cfg_file = os.path.expanduser('../openerp.cfg')

config = ConfigParser.ConfigParser()
config.read([cfg_file])
dbname = config.get('dbaccess', 'dbname')
user = config.get('dbaccess', 'user')
pwd = config.get('dbaccess', 'pwd')
server = config.get('dbaccess', 'server')
port = config.get('dbaccess', 'port')  # verify if it's necessary: getint

# -----------------------------------------------------------------------------
# Connect to ODOO:
# -----------------------------------------------------------------------------
odoo = erppeek.Client(
    'http://%s:%s' % (server, port),
    db=dbname, user=user, password=pwd,
    )

# Pool used:
template_pool = odoo.model('product.template')
template_ids = template_pool.search([])

if not template_ids:
    print('Error no product found')
    sys.exit()

for template in template_pool.browse(template_ids):
    default_code = template.default_code  # wp_sku
    wp_id = template.wp_id
    template_pool.write({
        'wp_id_in': wp_id,
        'sku_in': default_code
    })
    print('Update: %s' % default_code)
