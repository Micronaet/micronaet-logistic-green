# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

{
    'name': 'Wordpress - Connector',
    'version': '11.0.2.0.0',
    'category': 'Report',
    'description': '''
        Manage wordpress connector data
        ''',
    'summary': 'Wordpress, Connector',
    'author': 'Micronaet S.r.l. - Nicola Riolini',
    'website': 'http://www.micronaet.it',
    'license': 'AGPL-3',
    'depends': [
        'base',
        'product',
        'xlsxwriter_report',
        ],
    'data': [
        'security/ir.model.access.csv',
        'views/wordpress_view.xml',
        ],
    'external_dependencies': {
        'python': ['woocommerce'],
        },
    'application': True,
    'installable': True,
    'auto_install': False,
    }
