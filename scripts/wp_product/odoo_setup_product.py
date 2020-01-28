import os
import woocommerce
import pickle
import urllib
import sys
import erppeek
import ConfigParser
import pickle

# -----------------------------------------------------------------------------
# Utility:
# -----------------------------------------------------------------------------
def clean_code(sku):
    """ Clean code
    """
    sku = (sku or '').strip()
    
    if len(sku) == 13 and sku.isdigit():
        ean13 = sku
    else:
        ean13 = ''    

    sku_part = sku.split('-')
    code = sku_part[0]
    supplier = ''
    child = ''
    if len(sku_part) > 1:
        supplier = sku_part[1].upper()
        if len(supplier) > 2:
            if supplier[2:3].isalpha():                
                child = supplier[2:]
                supplier = supplier[:2]
            else:    
                child = supplier[3:]
                supplier = supplier[:3]
        else:            
            child = supplier[3:]
            supplier = supplier[:3]
        
    if child:
        code = '%s_%02d' % (
            code,
            ord(child) - 64,
            )
    return sku, code, supplier, child, ean13
    
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
partner_pool = odoo.model('res.partner') 
supplinfo_pool = odoo.model('product.supplierinfo') 

# -----------------------------------------------------------------------------
# Load supplier
# -----------------------------------------------------------------------------
supplier_ids = partner_pool.search([
    ('ref', '!=', False),
    ])
supplier_db = {}
for supplier in partner_pool.browse(supplier_ids):
    supplier_db[supplier.ref] = supplier.id    

# -----------------------------------------------------------------------------
# Load previous export data:
# -----------------------------------------------------------------------------
pickle_file = open('product.supplier.pik', 'rb')
check_product = pickle.load(pickle_file)

# -----------------------------------------------------------------------------
# Update supplier:
# -----------------------------------------------------------------------------
i = 0
import pdb; pdb.set_trace()
for default_code in check_product:
    i += 1
    if not default_code:
        print '%s. Jump empty code!' % i
        continue

    supplier_set = set()

    # Extract set of supplier from pickle data:    
    for sku in check_product[default_code]:
        sku, default_code, supplier, child, ean13 = clean_code(sku)
        
        if not supplier:
            continue
        supplier_id = supplier_db.get(supplier, False)
        if not supplier_id:
            print 'Not found supplier code: %s' % supplier
            sys.exit()
            
        supplier_set.add(supplier_id)

    # Extract set of supplier from ODOO:
    product_ids = product_pool.search([
        ('default_code', '=', default_code),
        ])
    product = product_pool.browse(product_ids)[0]
    for supplier in product.seller_ids:
        supplier_set.remove(supplier.name.id)

    for supplier_id in supplier_set:
        supplier_info.create({
            'name': supplier_id,
            'product_tmpl_id': product.id,
            'min_qty': 1,
            'price': 0.0,            
            })

    # TODO manage child association!    
                

