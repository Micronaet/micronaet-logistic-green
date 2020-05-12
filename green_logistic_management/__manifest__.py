# -*- coding: utf-8 -*-
#!/usr/bin/python
###############################################################################
#
# ODOO (ex OpenERP)
# Open Source Management Solution
# Copyright (C) 2001-2018 Micronaet S.r.l. (<https://micronaet.com>)
# Developer: Nicola Riolini @thebrush (<https://it.linkedin.com/in/thebrush>)
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################

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
        # 'logistic_stock_position', # Stock position
        # 'order_line_explode_kit', # Sale kit explode
        # 'order_line_change_product', # Replaced link product
        # 'product_default_supplier', # First supplier management
        # 'product_folder_image', # For image management
        # 'excel_export', # Export in Excel
        # 'logistic_account_report', # DDT Report
        # 'logistic_ddt', # DDT Extra data
        # 'logistic_order_unification', # Order unification
        # 'l18n_it_fatturapa', # Fattura PA Management

        # 'logistic_purchase_export', # Export files
        ],
    'data': [
        # 'security/crm_security.xml',
        # 'security/ir.model.access.csv',

        # Views:
        # 'views/logistic_management_view.xml',

        # 'views/fatturapa_view.xml',
        # 'wizard/manual_operation_view.xml', # Test events
        # 'wizard/status_extract_view.xml', # Extract operation

        # 'views/account_parameter_view.xml', # XXX move in logistic_ddt

        # Report:
        # 'reports/load_position_report.xml',

        ],
    'demo': [],
    'css': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    }
