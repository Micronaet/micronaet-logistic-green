# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

{
    'name': 'Wordpress - Order',
    'version': '11.0.2.0.0',
    'category': 'Connector',
    'description': '''
        Import order from wordpress
        ''',
    'summary': 'Excel, utility, report',
    'author': 'Micronaet S.r.l. - Nicola Riolini',
    'website': 'http://www.micronaet.it',
    'license': 'AGPL-3',
    'depends': [
        'wordpress_connector',
        'sale',
        'l10n_it_province',  # For city localization
    ],
    'data': [
        'views/order_view.xml',
    ],
    'external_dependencies': {},
    'application': False,
    'installable': True,
    'auto_install': False,
}
