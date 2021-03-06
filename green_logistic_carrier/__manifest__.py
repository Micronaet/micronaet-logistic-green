# -*- coding: utf-8 -*-
# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

{
    'name': 'Green manage carrier in order',
    'version': '1.0',
    'category': 'Localization/Italy',
    'summary': 'DDT, extra data',
    'description': '''
        Manage carrier in sale order
        ''',
    'author': 'Nicola Riolini',
    'website': 'http://www.micronaet.com',
    'depends': [
        'stock',
        'sale',
        'product',
        'plant_passport',  # Change report total
        # For CUPS operations (Micronaet/micronaet-logistic branch):
        'cups_printing',
        'wordpress_order',  # For selection of order
        'green_logistic_management',
        ],
    'data': [
        'security/ir.model.access.csv',
        'views/carrier_view.xml',
        'report/sales_label_report.xml',
        ],
    'test': [],
    'installable': True,
    'active': False,
    }
