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
        ],
    'data': [
        'security/ir.model.access.csv',
        'views/carrier_view.xml',
        ],
    'test': [],
    'installable': True,
    'active': False,
    }
