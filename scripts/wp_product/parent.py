import os
import woocommerce
import pickle
import sys
import ConfigParser
import pickle

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
parent_db = {}
parameter = {'per_page': 100, 'page': 1}
import pdb; pdb.set_trace()
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
        # ---------------------------------------------------------------------
        # Extract data from record:
        # ---------------------------------------------------------------------
        wp_id = record['id']
        parent_id = record['parent_id']

        if not parent_id:
            continue
        
        # Parent:        
        if parent_id not in parent_db:
            parent_db[parent_id] = []
        parent_db[parent_id].append(wp_id)

pickle_file = open('parent.data.pik', 'wb')
pickle.dump(parent_db, pickle_file)

