import os
import woocommerce
import pickle
import urllib
import sys
import erppeek
import ConfigParser
import pickle

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
image_path = config.get('dbaccess', 'image_path')

  
# -----------------------------------------------------------------------------
# Connect to ODOO:
# -----------------------------------------------------------------------------
odoo = erppeek.Client(
    'http://%s:%s' % (server, port), 
    db=dbname, user=user, password=pwd,
    )
    
# Pool used:
product_pool = odoo.model('product.template') 

# -----------------------------------------------------------------------------
# Load previous export data:
# -----------------------------------------------------------------------------
pickle_file = open('parent.data.pik', 'rb')
parent_db = pickle.load(pickle_file)

# A. Clean master selection:
parent_ids = product_pool.search([
    ('wp_master', '=', True),
    ])
product_pool.write(parent_ids, {
    'wp_master': False,
    })    

# B. Clean slave selection:
slave_ids = product_pool.search([
    ('wp_master_id', '!=', False),
    ])
product_pool.write(slave_ids, {
    'wp_master_id': False,
    })    

import pdb; pdb.set_trace()
# -----------------------------------------------------------------------------
# Update supplier:
# -----------------------------------------------------------------------------
for parent_id in parent_db:
    # Setup parent in ODOO:    
    parent_ids = product_pool.search([
        ('wp_id', '=', parent_id),
        ])
    
    if not parent_ids:
        print 'Master %s not found!' % parent_id
        continue
    
    product_pool.write(parent_ids, {
        'wp_master': True
        })    

    for wp_id in parent_db[parent_id]:
        product_ids = product_pool.search([
            ('wp_id', '=', wp_id),
            ])
        product_pool.write(product_ids, {
            'wp_master_id': parent_ids[0],
            })

