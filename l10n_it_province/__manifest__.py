# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

{
    'name': 'Italian Localisation - Province',
    'version': '11.0.1',
    'category': 'Localisation',
    'description': """
        Funcionalities:
        - Comuni italiani
        - res.partner.title italiani
        - Province e regioni
        """,
    'author': 'OpenERP Italian Community',
    'website': 'http://www.openerp-italia.org',
    'license': 'AGPL-3',
    'depends': [
        'base',
        'sale',  # For menu position
        ],
    'data': [
        'partner/partner_view.xml',
        'security/ir.model.access.csv',
        'data/res.region.csv',
        'data/res.province.csv',
        'data/res.city.csv',
        # 'data/res.partner.title.csv',
        ],
    'demo_xml': [],
    'active': False,
    'installable': True,
    }
