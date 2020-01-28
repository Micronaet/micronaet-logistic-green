import os
import woocommerce
import pickle
import urllib
import sys
import erppeek
import ConfigParser

# Local:
image_path = '/home/thebrush/ETL/Georgiche/Images'

# Server:
#image_path = './images'

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
#cfg_file = os.path.expanduser('../openerp.cfg')
cfg_file = os.path.expanduser('../local.cfg')

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
product_pool = odoo.model('product.template') 

# Le Georgiche:
wcapi = woocommerce.API(
    url='https://www.venditapianteonline.it',
    consumer_key='ck_433f21a50a7e52ef28db2b739602aa659eec75fb',
    consumer_secret='cs_b17b5c3b6faf8ea0e4f360c4f0fbc12253ea341e',
    wp_api=True,
    version='wc/v3',
    query_string_auth=True,
    )

# load from file:
parameter = {'per_page': 10, 'page': 1}
while True:
    reply = wcapi.get('products', params=parameter)
    parameter['page'] += 1    

    try:
        if reply.status_code >= 300:
            print 'Error getting category list', reply
            break
    except:
        pass # Records present 
                
    records = reply.json()            
    if not records:
        break

    for record in records:
        # ---------------------------------------------------------------------
        # Extract data from record:
        # ---------------------------------------------------------------------
        wp_id = record['id']
        sku = record['sku']
        name = record['name']
        images = record['images']
        regular_price = record['regular_price']
        related_ids = record['related_ids']
        tags = record['tags']
        weight = record['weight']
        stock_status = record['stock_status']
        product_type = record['type']
        status = record['status']
        description = record['description']
        attributes = record['attributes']
        slug = record['slug']
        categories = record['categories']

        # ---------------------------------------------------------------------
        # Clean sku for default_code
        # ---------------------------------------------------------------------
        sku, default_code, supplier, child, ean13 = clean_code(sku) 

        # ---------------------------------------------------------------------
        # Prepare data:
        # ---------------------------------------------------------------------
        # A. Fixed data:
        data = {
            'name': name,
            'wp_id': wp_id,
            'default_code': default_code,
            'wp_sku': sku,
            'lst_price': regular_price,
            'description_sale': description,
            'weight': weight,
            }

        # ---------------------------------------------------------------------
        # Update ODOO:
        # ---------------------------------------------------------------------
        if sku:
            product_ids = product_pool.search([
                ('default_code', '=', default_code),
                ])
        else:
            product_ids = product_pool.search([
                ('wp_id', '=', wp_id),
                ])
                    
        if product_ids:
            print 'Update product %s' % default_code
            product_pool.write(product_ids, data)
        else:    
            print 'Create product %s' % default_code
            product_pool.create(data)
            
        # ---------------------------------------------------------------------
        # Image download:
        # ---------------------------------------------------------------------
        if not sku:
            print '   > Product %s without code!' % name            
            continue  # No download image!
        counter = 0
        for image in images:
            image_src = urllib.quote(image['src'].encode('utf8'), ':/')
            # image_name = image['name']
            # image_id = image['id']
            
            urllib.urlretrieve(
                image_src,
                os.path.join(
                    image_path, '%s.%03d.jpg' % (default_code, counter)))
            counter += 1

