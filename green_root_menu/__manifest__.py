# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

{
    'name': 'Green Master menu',
    'version': '1.0',
    'category': 'Menu',
    'sequence': 5,
    'summary': 'Green Logistic Menu',
    'website': 'https://micronaet.com',
    'depends': [
        'base',
        'green_logistic_management',
        'carrier_mbe_soap',
        ],
    'data': [
        'views/menu_view.xml',
        ],
    'demo': [],
    'css': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    }
