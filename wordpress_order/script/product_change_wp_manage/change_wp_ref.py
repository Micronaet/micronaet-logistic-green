import os
import sys
import shutil
import pdb
from datetime import datetime, timedelta
import erppeek
import ConfigParser

# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
old_path = '/home/odoo/.local/share/Odoo/filestore/LeGeorgiche/Data/images'
new_path = '/home/odoo/.local/share/Odoo/filestore/LeGeorgiche/Data/wp_images'
extension = 'jpg'

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
pdb.set_trace()
for template in template_pool.browse(template_ids):
    # Mode WP reference:
    default_code = template.default_code  # wp_sku
    wp_id = template.wp_id
    product_id = template.id
    template_pool.write([product_id], {
        'wp_id_in': wp_id,
        'sku_in': default_code,
        })
    print('Update: %s' % default_code)

    # Move image:
    old_name = '%s.000.%s' % (wp_id, extension)
    new_name = '%s.000.%s' % (product_id, extension)

    try:
        shutil.copy(
            os.path.join(old_path, old_name),
            os.path.join(new_path, new_name),
        )
        print('Copied image: %s >> %s' % (old_name, new_name))
    except:
        print('Error copy image: %s >> %s' % (old_name, new_name))
