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
import pdb
from odoo import models, fields, api, exceptions

_logger = logging.getLogger(__name__)


class WPConnector(models.Model):
    """ Model name: Wordpress Connector
    """
    _inherit = 'wp.connector'

    @api.multi
    def extract_wordpress_published_report(self):
        """ Extract list of published elements:
        """
        # Pool used:
        report_pool = self.env['excel.report']
        product_pool = self.env['product.template']
        attribute_pool = self.env['wp.attribute']

        attributes = attribute_pool.search([
            ('connector_out_id', '!=', False),
        ])
        attribute_col = {}
        counter = 0
        for attribute in sorted(attributes, key=lambda x: x.name):
            attribute_col[attribute.name] = counter
            counter += 1

        # ---------------------------------------------------------------------
        #                         Excel report:
        # ---------------------------------------------------------------------
        ws_name = 'Prodotti wordpress'
        report_pool.create_worksheet(ws_name, format_code='DEFAULT')

        # ---------------------------------------------------------------------
        # Published product:
        # ---------------------------------------------------------------------
        # Width
        columns = [
            # Anagrafica:
            15, 40, 30, 40,
            # WP:
            15, 15, 25,
            # Master / Slave:
            10, 12,
            # Prezzo:
            10, 10,
            # Magazzino:
            10, 10, 10,
            # Tassonomia:
            25, 25, 25, 25, 25, 25, 25, 25,
            # Botanico:
            25, 25, 25, 25, 25, 25,
            # Cura:
            15, 15, 15, 15,
            # Immagini:
            40,
            # Link prodotti:
            40, 40,
            # Anagrafiche collegate:
            50, 50,
        ]
        columns.extend([20 for i in range(len(attribute_col))])
        report_pool.column_width(ws_name, columns)

        # Print header
        row = 0
        header = [
            # Anagrafica:
            'Codice', 'Nome',
            'Descrizione breve', 'Descrizione',

            # WP:
            'Tipo', 'Stato', 'Slug',

            # Master / Slave:
            'Modo', 'Master',

            # Prezzo:
            'Prezzo', 'Scontato',

            # Magazzino:
            'Gest. mag.', 'Backorders', 'Stato Magazzino',

            # Tassonomia:
            'Nome volgare', 'Nome scientifico', 'Famiglia', 'Genere',
            'Specie', u'Varietà', 'Origine', 'Progenitori',

            # Botanico:
            'Dimensione fiore', 'Note profumo', 'Tipologia fioritura',
            'Altezza fioritura', 'Dimensione', u'Rusticità',

            # Cura:
            'Potatura', 'Cura e coltivazione', 'Propagazione',
            'Parassiti e malattie',

            # Immagini:
            'Immagini',

            # Link prodotti:
            'Up sell', 'Cross sell',

            # Anagrafiche collegate:
            'Categorie', 'Tags',
            ]
        header.extend(sorted(attribute_col.keys()))

        report_pool.write_xls_line(
            ws_name, row, header, style_code='header')

        products = product_pool.search([
            '&',
            ('wp_connector_out_id', '!=', False),
            '|',
            ('wp_master', '=', True),
            ('wp_type', '=', 'simple'),
        ])
        # [Master + Slaves] or [Simple only]
        # report_pool.freeze_panes(ws_name, row+1, 2)

        empty = ['' for i in range(len(attribute_col))]
        for wordpress_product in sorted(
                products, key=lambda x: (x.default_code or '', x.name)):
            product_list = [wordpress_product]
            if wordpress_product.wp_master:
                product_list.extend(
                    [t for t in wordpress_product.wp_slave_ids])
            for product in product_list:
                row += 1
                default_code = product.default_code or ''

                if product.wp_master:
                    mode = 'Padre'
                elif product.wp_master_id:
                    mode = 'Figlio'
                else:
                    mode = 'Semplice'

                data = [
                    # Anagrafica:
                    default_code or '',
                    product.name or '',

                    product.wp_short_description or '',
                    product.wp_description or '',

                    # WP:
                    product.wp_type,
                    product.wp_status,
                    product.wp_slug,

                    # Master / Slave:
                    mode,
                    product.wp_master_id.default_code or '',

                    # Prezzo:
                    product.list_price, product.wp_sale_price,

                    # Magazzino:
                    'X' if product.wp_manage_stock else '',
                    'X' if product.wp_backorders else '',
                    product.wp_stock_status,

                    # Tassonomia:
                    product.wp_vulgar_name or '',
                    product.wp_scientific_name or '',
                    product.wp_family or '',
                    product.wp_genre or '',
                    product.wp_specie or '',
                    product.wp_variety or '',
                    product.wp_origin or '',
                    product.wp_ancestor or '',

                    # Botanico:
                    product.wp_flower_dimension or '',
                    product.wp_scent_note or '',
                    product.wp_flowering_type or '',
                    product.wp_flowering_height or '',
                    product.wp_dimension_width or '',
                    product.wp_rusticity or '',

                    # Cura:
                    product.wp_pruning or '',
                    product.wp_care or '',
                    product.wp_propagation or '',
                    product.wp_disease or '',

                    # Immagini:
                    '[]',

                    # Link prodotti:
                    '',
                    '',

                    # Anagrafiche collegate:
                    ', '.join([(t.default_code or t.name) for t in
                              product.wp_up_sell_ids]),
                    ', '.join([(t.default_code or t.name) for t in
                              product.wp_cross_sell_ids]),
                    ]

                # -------------------------------------------------------------
                # Write attribute block if present:
                # -------------------------------------------------------------
                attribute_data = empty[:]
                for line in product.wp_attribute_ids:
                    attribute = line.attribute_id
                    terms = ', '.join(
                        [term.name for term in line.term_ids])
                    col = attribute_col.get(attribute.name)
                    attribute_data[col] = terms
                data.extend(attribute_data)

                # Write row:
                report_pool.write_xls_line(
                    ws_name, row, data,
                    style_code='text')

        return report_pool.return_attachment('web_product')
