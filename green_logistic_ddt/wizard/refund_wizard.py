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

import logging
from odoo import models, fields, api
from odoo.tools.translate import _


_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    """ Extra function
    """
    _inherit = 'stock.picking'

    # -------------------------------------------------------------------------
    # Override function
    # -------------------------------------------------------------------------
    @api.multi
    def refund_confirm_state_event(self):
        """ Confirm operation (will be overrided)
        """
        return self.write({
            'state': 'done',
        })


class StockPickingRefundDocumentWizard(models.TransientModel):
    """ Wizard for generate refund document
    """
    _name = 'stock.picking.refund.wizard'

    # -------------------------------------------------------------------------
    # Wizard button event:
    # -------------------------------------------------------------------------
    @api.multi
    def create_refund(self):
        """ Event for button done
        """
        # Pool used:
        picking_pool = self.env['stock.picking']
        move_pool = self.env['stock.move']
        quant_pool = self.env['stock.quant']
        company_pool = self.env['res.company']

        # ---------------------------------------------------------------------
        # Parameters:
        # ---------------------------------------------------------------------
        # A. From company:
        company = company_pool.search([])[0]

        # XXX use out pick type:
        logistic_pick_refund_type = company.logistic_pick_out_type_id

        # XXX Invert transfer location:
        location_to = logistic_pick_refund_type.default_location_src_id.id
        location_from = logistic_pick_refund_type.default_location_dest_id.id
        location_id = company.logistic_location_id.id

        # B. Parameter from wizard:
        from_picking = self.picking_id
        # stock.picking.refund.sequence

        # Readability:
        now = fields.Datetime.now()
        partner = from_picking.partner_id  # sale_order_id ref.
        order = from_picking.sale_order_id
        origin = from_picking.invoice_number or from_picking.ddt_number or \
            from_picking.name

        to_picking = picking_pool.create({
            'refund_origin_id': from_picking.id,
            'stock_mode': 'in',  # refund mode
            'sale_order_id': order.id,  # XXX need?
            'partner_id': partner.id,
            'scheduled_date': now,
            'origin': origin,
            # 'move_type': 'direct',
            'picking_type_id': logistic_pick_refund_type.id,
            'group_id': False,
            'location_id': location_from,
            'location_dest_id': location_to,
            # 'priority': 1,
            'state': 'draft',  # XXX To do manage done phase (for invoice)!!
            })
        to_picking_id = to_picking.id

        for line in self.line_ids:
            product = line.product_id
            product_qty = line.refund_qty  # Q refunded
            quant_qty = line.stock_qty  # Q. in stock

            # TODO no service load!?!

            if product_qty <= 0:
                continue  # no refund line

            move_id = move_pool.create({
                'picking_id': to_picking_id,

                'company_id': company.id,
                'partner_id': partner.id,
                'product_id': product.id,
                'name': product.name or ' ',
                'date': now,
                'date_expected': now,
                'location_id': location_from,
                'location_dest_id': location_to,
                'product_uom_qty': product_qty,
                'product_uom': product.uom_id.id,
                'state': 'done',
                'origin': origin,
                'price_unit': product.standard_price,
                'logistic_refund_id': line.line_id.id,

                # Sale order line link:
                # 'logistic_unload_id': line.id,

                # group_id
                # reference'
                # sale_line_id
                # procure_method,
                # 'product_qty': select_qty,
                }).id

            if quant_qty <= 0:
                continue  # no stock load

            quant_id = quant_pool.create({
                'company_id': company.id,
                'in_date': now,
                'location_id': location_id,
                'product_id': product.id,
                'quantity': quant_qty,
                # 'product_tmpl_id': used_product.product_tmpl_id.id,
                # 'lot_id' #'package_id'
                })

        # ---------------------------------------------------------------------
        # Confirm picking (Refund and Credit note)
        # ---------------------------------------------------------------------
        to_picking.refund_confirm_state_event()

        # ---------------------------------------------------------------------
        # Return view:
        # ---------------------------------------------------------------------
        return {
            'type': 'ir.actions.act_window',
            'name': _('Refund document'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_id': to_picking_id,
            'res_model': 'stock.picking',
            'view_id': False,  # view_id,
            'views': [(False, 'form'), (False, 'tree')],
            'domain': [('id', '=', to_picking_id)],
            'context': self.env.context,
            'target': 'current',
            'nodestroy': False,
            }

    # -------------------------------------------------------------------------
    # Columns:
    # -------------------------------------------------------------------------
    picking_id = fields.Many2one(
        'stock.picking', 'From document', required=True)


class StockPickingRefundDocumentLineWizard(models.TransientModel):
    """ Wizard for generate refund document
    """
    _name = 'stock.picking.refund.line.wizard'

    # -------------------------------------------------------------------------
    # Columns:
    # -------------------------------------------------------------------------
    wizard_id = fields.Many2one(
        'stock.picking.refund.wizard', 'Wizard')
    product_id = fields.Many2one(
        'product.product', 'Product')
    product_qty = fields.Float(
        'Q. origin', digits=(16, 2))
    refund_qty = fields.Float(
        'Q. refund', digits=(16, 2),
        help='Refund q. from customer delivery document')
    stock_qty = fields.Float(
        'Q. in stock', digits=(16, 2),
        help='Refund q. real returned in stock, generate load of stock')
    line_id = fields.Many2one(
        'sale.order.line', 'Refund reference')


class StockPickingRefundDocumentWizardRelation(models.TransientModel):
    """ Wizard for generate refund document
    """
    _inherit = 'stock.picking.refund.wizard'

    # -------------------------------------------------------------------------
    # Columns:
    # -------------------------------------------------------------------------
    line_ids = fields.One2many(
        'stock.picking.refund.line.wizard', 'wizard_id',
        'Picking line')
