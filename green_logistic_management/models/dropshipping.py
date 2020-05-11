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
import odoo
import logging
from odoo import models, fields, api
from odoo.tools.translate import _


_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    """ Model name: Partner for dropshipp
    """
    
    _inherit = 'res.partner'
    
    # -------------------------------------------------------------------------
    # Columns:
    # -------------------------------------------------------------------------
    dropship_manage = fields.Boolean('Dropship manage')
    

class SaleOrder(models.Model):
    """ Model name: Sale Order management
    """
    
    _inherit = 'sale.order'
    
    # -------------------------------------------------------------------------
    # Utility:
    # -------------------------------------------------------------------------
    # Sale order mark dropshipping:
    @api.model
    def check_dropshipping_order(self, order_ids):
        ''' Check dropshipping orders:
        '''
        for order in self.browse(order_ids):
            dropship_supplier = False # Save last supplier (or not)
            for line in order.order_line:               
                product = line.product_id

                # -------------------------------------------------------------
                # No dropship clause (check before expence):
                # -------------------------------------------------------------
                # Internal lavoration (state present):
                if line.mrp_state:
                    dropship_supplier = False
                    break
                
                # TODO check stock assign >> no dropship
                
                # -------------------------------------------------------------
                # Jump line:
                # -------------------------------------------------------------
                # Expence product: (service # TODO after only is_expence)
                if product.is_expence or product.type == 'service':
                    continue

                # Kit line:
                if logistic_state == 'unused': 
                    continue

                # -------------------------------------------------------------
                # Supplier check:
                # -------------------------------------------------------------
                supplier = product.default_supplier_id
                
                # Found one line without dropship supplier (or no supplier)
                if not supplier or not supplier.dropship_manage:
                    dropship_supplier = False
                    break
                    
                if dropship_supplier:
                    if supplier != dropship_supplier:
                        dropship_supplier = False
                        break
                else: # assign and go ahear
                    dropship_supplier = supplier # save for future check                    
                    
            if dropship_supplier:
                # Mark order and default supplier:
                order.write({
                    'logistic_state': 'dropshipped',
                    'default_supplier_id': supplier.id,
                    })
                # TODO Dropshipped extra actions TODO Here
                # TODO MAnage status of the line!!!! XXX IMPORTANT
                    
        return True

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

