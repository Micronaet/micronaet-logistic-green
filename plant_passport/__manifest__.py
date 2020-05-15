# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

{
    'name': 'Plant passport management',
    'version': '11.0.2.0.0',
    'category': 'Product',
    'description': '''
        Manage passport information for plant
        ''',
    'summary': 'Product, passport, plant',
    'author': 'Micronaet S.r.l. - Nicola Riolini',
    'website': 'https://micronaet.com',
    'license': 'AGPL-3',
    'depends': [
        'base',
        'sale',
        'product',
        ],
    'data': [
        'security/ir.model.access.csv',
        'views/passport_view.xml',
        ],
    'external_dependencies': {},
    'application': False,
    'installable': True,
    'auto_install': False,
    }
