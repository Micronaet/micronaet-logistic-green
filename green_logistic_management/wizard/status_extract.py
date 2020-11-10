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


class SaleOrderStatusExtractWizard(models.TransientModel):
    _name = 'sale.order.status.extract.wizard'
    _description = 'Extract sale order line'

    # -------------------------------------------------------------------------
    #                               BUTTON EVENT:
    # -------------------------------------------------------------------------
    # Order phase:
    @api.multi
    def excel_extract(self):
        """ Extract excel movement for selected order
        """
        line_pool = self.env['sale.order.line']
        excel_pool = self.env['excel.writer']

        # Domain generation:
        domain = []
        if self.order_logistic_state:
            domain.append(
                ('order_id.logistic_state', '=', self.order_logistic_state))

        if self.logistic_state:
            domain.append(
                ('logistic_state', '=', self.logistic_state))

        if self.from_date:
            domain.append(
                ('order_id.date_order', '>=', '%s 00:00:00' % self.from_date))
        if self.to_date:
            domain.append(
                ('order_id.date_order', '<=', '%s 23:59:59' % self.to_date))

        # ---------------------------------------------------------------------
        #                       Excel Extract:
        # ---------------------------------------------------------------------
        ws_name = 'Order status'
        excel_pool.create_worksheet(ws_name)

        # ---------------------------------------------------------------------
        # Format:
        # ---------------------------------------------------------------------
        excel_pool.set_format()
        f_title = excel_pool.get_format('title')
        f_header = excel_pool.get_format('header')

        f_white_text = excel_pool.get_format('text')
        #f_green_text = excel_pool.get_format('bg_green')
        #f_yellow_text = excel_pool.get_format('bg_yellow')

        f_white_number = excel_pool.get_format('number')
        #f_green_number = excel_pool.get_format('bg_green_number')
        #f_yellow_number = excel_pool.get_format('bg_yellow_number')

        # ---------------------------------------------------------------------
        # Setup page:
        # ---------------------------------------------------------------------
        excel_pool.column_width(ws_name, [
            20, 15, 25, 2, 2, 20, 10,
            8, 8, 8, 8, 8, 8, 8, 8,
            20, 20,
            ])

        # ---------------------------------------------------------------------
        # Extra data:
        # ---------------------------------------------------------------------
        now = fields.Datetime.now()

        row = 0
        excel_pool.write_xls_line(ws_name, row, [
            'Filtro = Stato ordine: %s - Stato riga: %s [Data: %s - %s]' % (
                self.order_logistic_state,
                self.logistic_state,
                self.from_date or '/',
                self.to_date or '/',
                )], default_format=f_title)

        row += 1
        excel_pool.write_xls_line(ws_name, row, [
             'Ordine', 'Data', 'Prodotto', 'Kit', 'Serv.', 'Originale', 'Modo',

             'Q.', 'Coperta', 'Non coperata', 'Ordinata', 'Ricevuta',
             'Residua', 'Consegnata', 'Da consegnare',

             'Lavorazione', 'Stato',
             ], default_format=f_header)

        # ---------------------------------------------------------------------
        # Read data
        # ---------------------------------------------------------------------
        lines = line_pool.search(domain)
        _logger.warning('Report status filter with: %s [Tot. %s]' % (
            domain, len(lines)))
        for line in lines: # TODO sort?
            row +=1
            order = line.order_id
            template = line.product_id.product_tmpl_id
            origin = line.origin_product_id.product_tmpl_id

            excel_pool.write_xls_line(ws_name, row, [
                # description
                order.name,
                order.date_order,
                template.default_code or template.name,
                template.is_kit,
                'x' if template.type == 'service' else '',
                origin.default_code if origin else '',
                line.linked_mode,
                #template.name,

                # Q. block:
                line.product_uom_qty,
                line.logistic_covered_qty,
                line.logistic_uncovered_qty,
                line.logistic_purchase_qty,
                line.logistic_received_qty,
                line.logistic_remain_qty,
                line.logistic_delivered_qty,
                line.logistic_undelivered_qty,

                # State
                line.mrp_state,
                line.logistic_state,
                ], default_format=f_white_text)

        # ---------------------------------------------------------------------
        # Save file:
        # ---------------------------------------------------------------------
        return excel_pool.return_attachment('Stato_righe_ordini')

    # -------------------------------------------------------------------------
    #                             COLUMNS DATA:
    # -------------------------------------------------------------------------
    logistic_state = fields.Selection([
        ('draft', 'Custom order'), # Draft, customer order
        ('ordered', 'Ordered'), # Supplier order uncovered
        ('ready', 'Ready'), # Order to be picked out (all in stock)
        ('done', 'Done'), # Delivered qty (order will be closed)
        ], 'Line Logistic state')

    order_logistic_state = fields.Selection([
        ('draft', 'Order draft'), # Draft, new order received
        # Start automation:
        ('confirmed', 'Order confirmed'), # Quotation transformed in order
        ('pending', 'Pending delivery'), # Waiting for delivery
        ('ready', 'Ready'), # Ready for transfer
        ('done', 'Done'), # Delivered or closed XXX manage partial delivery
        ], 'Order Logistic state')

    from_date = fields.Date('From date')
    to_date = fields.Date('To date')

