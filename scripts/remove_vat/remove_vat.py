import os
import erppeek
import ConfigParser
import pdb

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
port = config.get('dbaccess', 'port')   # verify if it's necessary: getint

# -----------------------------------------------------------------------------
# Connect to ODOO:
# -----------------------------------------------------------------------------
odoo = erppeek.Client(
    'http://%s:%s' % (server, port),
    db=dbname, user=user, password=pwd,
    )

# Pool used:
line_pool = odoo.model('sale.order.line')
product_pool = odoo.model('product.product')

# Remove from product:
product_ids = product_pool.search([])
pdb.set_trace()
for product in product_pool.browse(product_ids):
    print('Product remove VAT: %s' % product.default_code)
    product_pool.write([product.id], {
        'taxes_id': False,
        'supplier_taxes_id': False,
    })

# Remove from sale order line:
line_ids = line_pool.search([])
for line in line_pool.browse(line_ids):
    print('Line remove VAT: %s' % line.name)
    line_pool.write([line.id], {
        'tax_id': False,
    })
