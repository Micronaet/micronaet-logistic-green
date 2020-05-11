#!/usr/bin/python
# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP) 
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<https://micronaet.com>)
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

import os
import sys
import logging
from odoo import api, models
from odoo import tools
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


"""class LoadMovePositionReport(models.AbstractModel):
    ''' Load move report:
    '''
    _name = 'report.logistic_management.report_load_position'
    
    @api.model
    def render_html(self, docids, data=None):
        ''' Render report parser:
        '''
        import pdb; pdb.set_trace()
        report_obj = self.env['report']
        report = report_obj._get_report_from_name(
            'logistic_management.report_load_position')
            
        move_pool = self.env['stock.move']    
        moves = move_pool.search([]) # TODO Change
        
        docids = moves.ids # list of IDs
        if not moves: #.exists()
             raise Warning(
                 _('No movement to print!'))
        
        docargs = {
            'doc_ids': docids,
            'doc_model': 'stock.move',
            'docs': moves,#self,
        }
        return report_obj.render(
            'logistic_management.report_load_position', 
            docargs,
            )
"""
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
