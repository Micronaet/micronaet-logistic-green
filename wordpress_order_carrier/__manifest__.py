# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

{
    'name': 'Wordpress - Order for carrier',
    'version': '11.0.2.0.0',
    'category': 'Connector',
    'description': '''
        Manage carrier order page
        ''',
    'summary': 'Sale, Carrier',
    'author': 'Micronaet S.r.l. - Nicola Riolini',
    'website': 'http://www.micronaet.it',
    'license': 'AGPL-3',
    'depends': [
        'base',
        'wordpress_order',
        'green_logistic_carrier',
        'sale',
    ],
    'data': [
        'views/carrier_order.xml',
    ],
    'external_dependencies': {},
    'application': False,
    'installable': True,
    'auto_install': False,
}
