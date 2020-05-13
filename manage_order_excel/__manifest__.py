# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

{
    'name': 'Excel - Manage order',
    'version': '11.0.2.0.0',
    'category': 'Sale',
    'description': '''
        Manage order sale and purchase from excel
        ''',
    'summary': 'Wordpress, Connector',
    'author': 'Micronaet S.r.l. - Nicola Riolini',
    'website': 'http://www.micronaet.it',
    'license': 'AGPL-3',
    'depends': [
        'base',
        'sale',
        'xlsxwriter_report',
        'wordpress_order',
        ],
    'data': [
        'security/ir.model.access.csv',
        'views/excel_order_view.xml',
        ],
    'external_dependencies': {},
    'application': False,
    'installable': True,
    'auto_install': False,
    }
