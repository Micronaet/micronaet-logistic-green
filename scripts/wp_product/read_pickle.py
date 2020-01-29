import os
import woocommerce
import pickle
import urllib
import sys
import erppeek
import ConfigParser
import pickle

# -----------------------------------------------------------------------------
# Load previous export data:
# -----------------------------------------------------------------------------
pickle_file = open('product.supplier.pik', 'rb')
check_product = pickle.load(pickle_file)

# -----------------------------------------------------------------------------
# Update supplier:
# -----------------------------------------------------------------------------
i = 0
for default_code in check_product:
    i += 1
    if not default_code:
        continue

    # Extract set of supplier from pickle data:    
    code = []
    for sku in sorted(check_product[default_code]):
        code.append(sku)

    print default_code, '|', '|'.join(code)
    
