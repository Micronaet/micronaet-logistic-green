# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2014 Abstract (http://www.abstract.it)
#    @author Davide Corio <davide.corio@abstract.it>
#    Copyright (C) 2014 Agile Business Group (http://www.agilebg.com)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

{
    'name': 'DdT extra data',
    'version': '1.0',
    'category': 'Localization/Italy',
    'summary': 'DDT, extra data',
    'description': '''
        Add extra data for print DDT report
        ''',
    'author': 'Nicola Riolini',
    'website': 'http://www.micronaet.com',
    'depends': [
        'stock',
        'sale',
        # 'l18n_it_fatturapa',
        ],
    'data': [
        'security/ir.model.access.csv',
        'data/stock_data.xml',
        'data/sequence_data.xml',
        'views/stock_view.xml',
        'wizard/refund_wizard_view.xml',
    ],
    'test': [],
    'installable': True,
    'active': False,
}
