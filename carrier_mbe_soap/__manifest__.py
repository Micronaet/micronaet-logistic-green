# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

{
    'name': 'Carrier MBE Soap',
    'version': '11.0.2.0.0',
    'category': 'Shipment',
    'description': '''
        Manage MBE Carrier via SOAP
        ''',
    'summary': 'Carrier, MBE, SOAP',
    'author': 'Micronaet S.r.l. - Nicola Riolini',
    'website': 'http://www.micronaet.it',
    'license': 'AGPL-3',
    'depends': [
        'sale',
        'green_logistic_carrier',  # TODO remove?!
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/soap_view.xml',
        # 'data/color_data.xml',
    ],
    'external_dependencies': {
        'python': ['zeep'],
    },
    'application': False,
    'installable': True,
    'auto_install': False,
}
