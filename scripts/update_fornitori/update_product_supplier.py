import os
import woocommerce
import pickle
import urllib
import sys
import erppeek
import ConfigParser
import pdb

# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
# From config file:
cfg_file = os.path.expanduser('../openerp.cfg')
#cfg_file = os.path.expanduser('../local.cfg')

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
partner_pool = odoo.model('res.partner')
product_pool = odoo.model('product.product')
suppinfo_pool = odoo.model('product.supplierinfo')

print('Read partner')
partners = {}
partner_ids = partner_pool.search([('ref', '!=', False)])
for partner in partner_pool.browse(partner_ids):
    partners[partner.ref] = partner.id

print('Start update product')
counter = 0
product_ids = product_pool.search([])
for product in product_pool.browse(product_ids):
    counter += 1
    if not counter % 10:
        print('Product counter %s' % counter)
    default_code = product.default_code or ''
    if '-' not in default_code:
        continue
    code_part = default_code.split('-')
    if len(code_part) != 2:
        continue

    ref = code_part[-1]
    if not ref.isdigit():
        continue

    partner_id = partners.get(ref)
    if not partner_id:
        continue

    if product.seller_ids:
        continue

    print('Created: %s' % default_code)
    suppinfo_pool.create({
        'product_id': product.id,
        'product_tmpl_id': product.product_tmpl_id.id,
        'name': partner_id,
        'price': 0.0,
        'min_qty': 1,
    })
