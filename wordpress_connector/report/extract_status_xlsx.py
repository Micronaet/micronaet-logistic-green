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
from odoo import models, fields, api, exceptions

_logger = logging.getLogger(__name__)


class ConnectorServer(models.Model):
    """ Model name: ConnectorServer
    """
    _inherit = 'connector.server'

    @api.multi
    def extract_wordpress_published_report(self):
        """ Extract list of published elements:
        """
        stock_status = True

        # Pool used:
        excel_pool = self.pool.get('excel.writer')
        product_pool = self.pool.get('product.product')

        # ---------------------------------------------------------------------
        #                         Excel report:
        # ---------------------------------------------------------------------
        connector = self
        album_ids = []  # TODO not used for now

        ws_name = 'Prodotti wordpress'
        excel_pool.create_worksheet(ws_name)

        # Load formats:
        excel_format = {
            'title': excel_pool.get_format('title'),
            'header': excel_pool.get_format('header'),
            'black': {
                'text': excel_pool.get_format('text'),
                'number': excel_pool.get_format('number'),
                },
            'red': {
                'text': excel_pool.get_format('bg_red'),
                'number': excel_pool.get_format('bg_red_number'),
                },
            'yellow': {
                'text': excel_pool.get_format('bg_yellow'),
                'number': excel_pool.get_format('bg_yellow_number'),
                },
            }

        # ---------------------------------------------------------------------
        # Published product:
        # ---------------------------------------------------------------------
        # Width
        excel_pool.column_width(ws_name, [
            5, 15, 20,
            30, 70,
            30, 70,
            50, 10, 15, 15,
            10, 10,
            5, 20,
            20,
            40, 40,
            ])

        # Print header
        row = 0
        excel_pool.write_xls_line(
            ws_name, row, [
            'Pubbl.', 'Codice', 'Colore',
            'Nome', 'Descrizione',
            '(Name)', '(Description)',
            'Categorie', 'Mag.', 'Prezzo ODOO', 'Prezzo WP',
            'Cat. Stat.', 'Peso',
            'Mod. imb.', 'Imballo',
            'Magazzino', 'Immagini', 'Link',
            ], default_format=excel_format['header'])

        for product in sorted(
                product_pool.search([]),
                key=lambda x: (x.default_code, x.name)):
            default_code = product.default_code or ''

            # -----------------------------------------------------------------
            # Parameters:
            # -----------------------------------------------------------------
            # Images:
            image = []

            # Stock:
            stock = 0.0  # int(product.mx_net_mrp_qty)
            color_format = excel_format['black']  # TODO color

            excel_pool.write_xls_line(
                ws_name, row, [
                    default_code,
                    '',
                    '',
                    ', '.join(tuple(
                        [c.name for c in product.wp_categ_ids])),

                    product.weight,
                    '%s x %s x %s' % (
                        product.length, product.height, product.width),
                    ], default_format=color_format['text'])
        return excel_pool.return_attachment('web_product')
