# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import logging
import sys
import pdb
from odoo import models, fields, api
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    """ Add report in sale order
    """
    _inherit = 'sale.order'

    @api.model
    def sale_order_statistic_report(self):
        """ Sale order report
        """
        report_pool = self.env['excel.report']
        order_pool = self.env['sale.order']

        # ---------------------------------------------------------------------
        # Page detail:
        # ---------------------------------------------------------------------
        orders = order_pool.search([
            ('wp_status', 'in', ('completed', 'delivered')),
        ])

        header = (
            'Ord.', 'Data', 'Ordine', 'Cliente',
            'SKU', 'Q.', 'Descrizione',
            # 'Vaso',
            'Categoria', 'Fornitore',
            'Costo', 'Prezzo', 'Costo sp.',
            'Totale',
        )

        column_width = (
            2, 11, 15, 40,
            12, 8, 40,
            25, 25,
            10, 10, 10, 12
        )
        total_col = len(column_width)
        ws_name = _('Wordpress')
        report_pool.create_worksheet(ws_name, format_code='DEFAULT')
        report_pool.column_width(ws_name, column_width)
        # report_pool.column_hidden(ws_name, [0, 1])  # Hide ID columns

        # Header:
        row = 0
        report_pool.write_xls_line(ws_name, row, header, style_code='header')
        report_pool.autofilter(ws_name, [row, 0, row, total_col - 5])
        report_pool.freeze_panes(ws_name, 1, 2)

        # Data loop:
        year_page = {}
        for order in orders:
            partner = order.partner_id
            date_order = order.date_order
            period = date_order[:4], date_order[5:7]
            if period not in year_page:
                year_page[period] = 0.0  # TODO other market!
            order_row = row + 1
            order_check = 'S'
            for line in order.order_line:
                row += 1

                # Readability:
                product = line.product_id
                sku = product.default_code
                subtotal = line.price_subtotal

                # TODO test delivery cost!
                if sku == 'shipping':
                    delivery_cost = order.carrier_cost or 0.0
                    delivery_format = 'number_error'
                else:
                    delivery_cost = ''
                    delivery_format = 'number'

                # Total:
                year_page[period] += subtotal
                report_pool.write_xls_line(ws_name, row, (
                    order_check,
                    (date_order or '')[:10],
                    order.name or '',
                    partner.name or '',

                    sku or '',
                    (line.product_uom_qty, 'number'),
                    product.name or '',

                    # Vaso
                    '',  # Category
                    '',  # Supplier

                    ('', 'number'),  # TODO Cost not present for now
                    (subtotal, 'number_ok'),
                    (delivery_cost, delivery_format),
                    ('', 'number'),
                ), style_code='text')
                order_check = 'N'
            # Total line:
            report_pool.write_xls_line(ws_name, order_row, (
                (order.amount_total, 'number_ok'),  # amount_untaxed
            ), style_code='text', col=total_col - 1)

        # ---------------------------------------------------------------------
        # Page period total:
        # ---------------------------------------------------------------------
        header = ('Anno', 'Mese', 'Wordpress', 'Totale', 'Annuale')

        column_width = (
            8, 4, 10, 10,
        )
        total_col = len(column_width)

        ws_name = _('Totali')
        report_pool.create_worksheet(ws_name, format_code='DEFAULT')
        report_pool.column_width(ws_name, column_width)

        # Header:
        row = 0
        report_pool.write_xls_line(ws_name, row, header, style_code='header')
        report_pool.autofilter(ws_name, [row, 0, row, total_col - 1])
        report_pool.freeze_panes(ws_name, 1, 2)

        total = 0.0
        last_year = False
        for period in sorted(year_page):
            row += 1
            wordpress_total = year_page[period]
            year, month = period

            if not last_year or last_year != year:
                if last_year:  # Write previous year total:
                    report_pool.write_xls_line(ws_name, row - 1, [
                        total,
                    ], style_code='text', col=4)

                total = 0.0
                last_year = year

            total += wordpress_total
            report_pool.write_xls_line(ws_name, row, [
                period[0],
                period[1],
                wordpress_total,
                wordpress_total,
            ], style_code='text')

        # Write previous year total (last not printed):
        if year_page:
            report_pool.write_xls_line(ws_name, row - 1, [
                wordpress_total,
            ], style_code='text', col=3)

        return report_pool.return_attachment(_('order_statistic_total'))
