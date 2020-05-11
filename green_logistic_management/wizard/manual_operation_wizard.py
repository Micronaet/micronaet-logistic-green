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
from odoo import api, fields, models, tools, exceptions, SUPERUSER_ID
from odoo.addons import decimal_precision as dp
from odoo.tools.translate import _


_logger = logging.getLogger(__name__)

class StockChangeStandardPrice(models.TransientModel):
    _name = 'logistic.manual.operation.wizard'
    _description = 'Logistic manual operation'

    # -------------------------------------------------------------------------
    #                               BUTTON EVENT:    
    # -------------------------------------------------------------------------    
    limit = fields.Integer('Limit', default=10)
    loop = fields.Integer('Loop', default=5, required=True)
    evaluation_date = fields.Date('Evaluation date')

    # -------------------------------------------------------------------------
    #                               BUTTON EVENT:    
    # -------------------------------------------------------------------------    
    # Order phase:
    @api.multi
    def confirm_payment(self):
        ''' A. Confirm draft order if payment is secure
        '''
        order_pool = self.env['sale.order']
        return order_pool.workflow_draft_to_payment()

    @api.multi
    def confirm_order(self):
        ''' B. Confirm quotation in order (explode kit)
        '''
        order_pool = self.env['sale.order']
        return order_pool.workflow_payment_to_order()

    @api.multi
    def assign_stock(self):
        ''' C. Assign stock product to open orders
        '''
        line_pool = self.env['sale.order.line']
        return line_pool.workflow_order_to_uncovered()

    # Purchase phase:
    @api.multi
    def generate_purchase(self):
        ''' D. Generate purchase order for not cover qty
        '''
        line_pool = self.env['sale.order.line']       
        return line_pool.workflow_uncovered_pending()

    @api.multi
    def confirm_generated_purchase(self):
        ''' D2. Confirm purchase order created
        '''
        purchase_pool = self.env['purchase.order']       
        purchases = purchase_pool.search([
            ('logistic_state', '=', 'draft'),
            ])
        # Lauch action button for change state and export:    
        return purchases.set_logistic_state_confirmed()

    # BF Load phase:        
    @api.multi
    def update_ready(self):
        ''' E. Update order ready with stock or load
        '''
        picking_pool = self.env['stock.picking']        
        return picking_pool.workflow_ordered_ready()

    """@api.multi
    def update_ready_purchase_check(self):
        ''' E2. Update purchase order if all delivered. 
            In production not necessary (just for demo test)
        '''
        purchase_pool = self.env['purchase.order']
        # Without args search all confirmed:
        return purchase_pool.check_order_confirmed_done() """
        
    # DDT Unload phase:
    @api.multi
    def generate_delivery(self):
        ''' F. Generate delivery order in draft mode
        '''
        
        # Create draft document:
        order_pool = self.env['sale.order']
        
        for times in range(0, self.loop):
            order_pool.workflow_ready_to_done_draft_picking(self.limit)

    @api.multi
    def closed_delivered(self):
        ''' G. Close delivery order
        '''
        return True

    # -------------------------------------------------------------------------
    # Report test:
    # -------------------------------------------------------------------------
    @api.multi
    def load_position_print(self):
        """ Print load position
        """
        excel_pool = self.env['excel.writer']

        ws_name = 'Carichi'
        excel_pool.create_worksheet(ws_name)
        
        excel_pool.save_file_as('/home/thebrush/position.xlsx')
        return True
        #return excel_pool.return_attachment('prova_report')

        
        self.ensure_one()
        
        move_pool = self.env['stock.move']    
        moves = move_pool.search([]) # TODO Change

        return self.env.ref(
            'logistic_management.load_stock_move_position').report_action(
                moves)

    @api.multi
    def print_report_account_fees_month(self):
        """ Account fees report
        """
        stock_pool = self.env['stock.picking']        
        return stock_pool.excel_report_extract_accounting_fees(
            self.evaluation_date)

    @api.multi
    def print_bug_check_pending_draft_line(self):
        """ Account Check pending order with draft lines
        """
        log_file = os.path.join(
            os.path.expanduser('~'), 
            'log.txt',
            )            
        log = open(log_file, 'w')

        line_pool = self.env['sale.order.line']
        lines = line_pool.search([
            ('logistic_state', '=', 'draft'),
            ('order_id.logistic_state', '=', 'pending'),
            ])
        for line in lines:
            product_uom_qty = line.product_uom_qty
            logistic_covered_qty = line.logistic_covered_qty  
            if product_uom_qty == logistic_covered_qty:
                log.write(line.order_id.name + '\n')
            line.logistic_state = 'ready'

        line_pool.logistic_check_ready_order()
        return True
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
