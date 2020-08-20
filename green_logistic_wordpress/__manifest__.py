# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

{
    'name': 'Logistic with Wordpress order',
    'version': '11.0.2.0.0',
    'category': 'Logistic',
    'description': '''
        Integrate Logistic management with Wordpress connector
        ''',
    'summary': 'Logistic, Wordpress',
    'author': 'Micronaet S.r.l. - Nicola Riolini',
    'website': 'http://www.micronaet.it',
    'license': 'AGPL-3',
    'depends': [
        'sale',
        'wordpress_connector',
        'wordpress_order',
        'green_logistic_management',
    ],
    'data': [
        'views/wordpress_logistic_view.xml',
    ],
    'external_dependencies': {},
    'application': False,
    'installable': True,
    'auto_install': False,
}
