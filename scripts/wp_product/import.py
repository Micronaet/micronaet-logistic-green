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

# Le Georgiche:
wcapi = woocommerce.API(
    url='https://www.venditapianteonline.it',
    consumer_key='ck_433f21a50a7e52ef28db2b739602aa659eec75fb',
    consumer_secret='cs_b17b5c3b6faf8ea0e4f360c4f0fbc12253ea341e',
    wp_api=True,
    version='wc/v3',
    query_string_auth=True,
    timeout=600,
    )

# load from file:
check_product = {}
parameter = {'per_page': 100, 'page': 1}
variation_param = {'per_page': 20, 'page': 1}
while True:
    reply = wcapi.get('products', params=parameter)
    print '\n\n\n Page %s, Record: %s' % (
        parameter['page'], parameter['page'] * parameter['per_page'])

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
        image_list = []

        # ---------------------------------------------------------------------
        # Extract data from record:
        # ---------------------------------------------------------------------
        wp_id = record['id']
        sku = record['sku']
        name = record['name']
        images = record['images']
        variations = record['variations']
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
        #default_attributes

        # ---------------------------------------------------------------------
        # Clean sku for default_code
        # ---------------------------------------------------------------------
        sku, default_code, supplier, child, barcode = clean_code(sku) 
        
        # Check product
        if default_code not in check_product:
            check_product[default_code] = []
        check_product[default_code].append(sku)

        # ---------------------------------------------------------------------
        # Prepare data:
        # ---------------------------------------------------------------------
        # A. Fixed data:
        data = {
            'wp_published': True,
            'name': name,
            'wp_id': wp_id,
            'default_code': sku,
            'wp_sku': sku,
            'lst_price': regular_price,
            'description_sale': description,
            'weight': weight,
            # TODO wp_type: 'variable', #simple, grouped, external and variable. 
            }
        if barcode:
            data['barcode'] = barcode

        if variations:
            data['wp_master'] = True
        else:    
            data['wp_master'] = False
            
            
        # ---------------------------------------------------------------------
        # Update ODOO:
        # ---------------------------------------------------------------------
        product_ids = product_pool.search([
            ('wp_id', '=', wp_id),
            ])
                    
        if product_ids:
            print 'Update product %s [%s]' % (default_code, sku)
            product_pool.write(product_ids, data)
            product_id = product_ids[0]
        else:    
            print 'Create product %s [%s]' % (default_code, sku)
            product_id = product_pool.create(data).id

        image_list.append((wp_id, images))

        # ---------------------------------------------------------------------
        #                        VARIATIONS
        # ---------------------------------------------------------------------
        if variations:
            variation_param['page'] = 1

            while True:        
                var_reply = wcapi.get(
                    'products/%s/variations' % wp_id, 
                    params=variation_param,
                    )
                variation_param['page'] += 1    

                if var_reply.status_code >= 300:
                    print 'Error getting category list', var_reply
                    break
                            
                variants = var_reply.json()            
                if not variants:
                    break

                for variant in variants:
                    variant_id = variant['id']
                    variant_sku = variant['sku']
                    variant_images = variant['image']
                    #stock_status = variant['stock_status']
                    #product_type = variant['type']
                    #status = variant['status']

                    if variant_images:
                        # Only one:
                        image_list.append((variant_id, [variant_images]))
                    
                    variant_data = {
                        'wp_published': True,
                        'name': name,
                        'wp_id': variant['id'],
                        'default_code': variant_sku,
                        'wp_sku': variant_sku,
                        'lst_price': variant['regular_price'],
                        'description_sale': variant['description'],
                        'weight': variant['weight'],
                        'wp_master_id': product_id,
                        # TODO attribute terms!
                        }                        
                    variant_ids = product_pool.search([
                            ('wp_id', '=', variant_id),
                            ])
                                
                    if variant_ids:
                        product_pool.write(variant_ids, variant_data)
                        variant_id = product_ids[0]
                        print '   >> Update %s variants' % variant_sku
                    else:    
                        variant_id = product_pool.create(variant_data).id
                        print '   >> Create %s variants' % variant_sku
            
        # ---------------------------------------------------------------------
        # Image download:
        # ---------------------------------------------------------------------
        for reference_id, images in image_list:
            counter = -1        
            for image in images:
                counter += 1
                image_src = urllib.quote(image['src'].encode('utf8'), ':/')
                filename = '%s.%03d.jpg' % (
                    reference_id,
                    counter,
                    )
                    
                fullname = os.path.join(image_path, filename)
                if not os.path.isfile(fullname):
                    urllib.urlretrieve(image_src, fullname)                
                    print '          >> Get image saved as%s' % filename

pickle_file = open('product.supplier.data.pik', 'wb')
pickle.dump(check_product, pickle_file)

