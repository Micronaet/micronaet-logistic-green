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
        
    '''
    if child:
        if len(child) > 1:
            print 'SKU child error: %s' % sku            
            import pdb; pdb.set_trace()
        else:    
            code = '%s_%02d' % (
                code,
                ord(child) - 64,
                )
    '''
    return sku, code, supplier, child, ean13
    
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
# Update supplier:
# -----------------------------------------------------------------------------
i = 0
not_found = []
product_ids = product_pool.search([])
products = product_pool.browse(product_ids)
for product in products:
    sku = product.wp_sku
    sku, code, supplier, child, ean13 = clean_code(sku)
    
    i += 1
    if not sku:
        print '%s. Jump empty code!' % i
        continue

    if not product.seller_ids:
        print 'Add supplier to SKU %s' % sku
        supplier_id = supplier_db.get(supplier, False)
        if supplier_id:
            supplinfo_pool.create({
                'name': supplier_id,
                'product_tmpl_id': product.id,
                'min_qty': 1,
                'price': 0.0,            
                })

    # TODO manage child association!    
                
print 'Supplier not found: %s' % (not_found, )
