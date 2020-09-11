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

        orders = order_pool.search([
            # ('wp_state', '=', ''),
        ])

        header = (
            'Data', 'Ordine', 'Cliente',
            'SKU', 'Q.', 'Descrizione',
            # 'Vaso',
            'Categoria', 'Fornitore',
            'Costo', 'Prezzo', 'Totale',
        )

        column_width = (
            11, 15, 40,
            12, 8, 40,
            25, 25,
            10, 10, 12,
        )
        total_col = len(column_width)
        ws_name = _('Wordpress')
        report_pool.create_worksheet(ws_name, format_code='DEFAULT')
        report_pool.column_width(ws_name, column_width)
        # report_pool.column_hidden(ws_name, [0, 1])  # Hide ID columns

        # Header:
        row = 0
        report_pool.write_xls_line(ws_name, row, header, style_code='header')
        report_pool.autofilter(ws_name, [row, 0, row, column_width])

        # Data loop:
        for order in orders:
            for line in order.order_line:
                row += 1

                # Readability:
                product = line.product_id
                partner = order.partner_id
                header_row = row

                # TODO test delivery cost!
                delivery_cost = ''

                report_pool.write_xls_line(ws_name, row, (
                    (order.date_order or '')[:10],
                    order.name or '',
                    partner.name or '',

                    product.default_code or '',
                    (line.product_uom_qty, 'number'),
                    product.name or '',

                    # Vaso
                    '',  # Category
                    '',  # Supplier

                    (line.subtotal, 'number'),
                    ('', 'ok_number'),
                    (delivery_cost, 'ok_number'),  # TODO
                ), style_code='text')

            # Write total order:
            report_pool.write_xls_line(ws_name, header_row, (
                (order.total, 'number'),
            ), style_code='text', col=total_col)
        return report_pool.return_attachment(_('order_statistic_total'))
