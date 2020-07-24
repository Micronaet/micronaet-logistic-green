# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

{
    'name': 'Green Logistic Management',
    'version': '1.0',
    'category': 'Logistic',
    'sequence': 5,
    'summary': 'Green Logistic Management, Sale, Supplier order and delivery',
    'website': 'https://micronaet.com',
    'depends': [
        'base',
        'sale',
        'sale_management',
        'product',
        'account',
        'stock',
        'purchase',
        # 'product_default_supplier',  # First supplier management
        # 'product_folder_image',  # For image management
        # 'excel_export',  # Export in Excel
        # 'logistic_account_report',  # DDT Report
        'green_logistic_ddt',  # DDT Extra data
        # 'l18n_it_fatturapa',  # Fattura PA Management
        ],
    'data': [
        'security/logistic_group.xml',
        # Views:
        'views/logistic_management_view.xml',

        # 'views/fatturapa_view.xml',
        # 'wizard/manual_operation_view.xml', # Test events
        # 'wizard/status_extract_view.xml', # Extract operation
        ],
    'demo': [],
    'css': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    }
