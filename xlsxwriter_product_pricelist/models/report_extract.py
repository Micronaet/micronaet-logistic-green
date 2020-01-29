# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
import logging
from odoo import api, fields, models
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class ProductProductExcelReportWizard(models.TransientModel):
    _name = 'product.product.excel.report.wizard'
    _description = 'Extract product report'

    supplier_id = fields.Many2one('res.partner', 'Supplier')

    @api.multi
    def excel_product_report(self, ):
        report_pool = self.env['excel.report']
        detail_pool = self.env['product.supplierinfo']

        supplier = self.supplier_id

        # Collect data:
        domain = []
        if supplier:
            domain.append(
                ('name', '=', supplier.id))
        details = detail_pool.search(domain)

        # Excel file configuration:
        header = (
            'Ref.', 'Nome', 'Codice', 'Vecchio SKU',
            'Categoria', 'Listino',
            'Nome (f)', 'Codice (f)', 'Q. min (f)', 'T. cons.', 'Costo (f)',
            'Nuovo',
            )

        column_width = (
            5, 55, 15, 15
            20, 10,
            50, 30, 10, 10, 10,
            10,
            )

        data_report = {}
        for detail in details:
            if detail.name not in data_report:
                data_report[detail.name] = []
            data_report[detail.name].append(detail)

        for supplier in sorted(data_report, key=lambda x: x.name):
            ws_name = _(supplier.name or '/')
            report_pool.create_worksheet(ws_name, format_code='DEFAULT')
            report_pool.column_width(ws_name, column_width)
            report_pool.column_hidden(ws_name, [0])  # Hide 1st column

            # Title:
            row = 0
            title = (
                supplier.id, 'Elenco prodotti fornitore: %s' % supplier.name)
            report_pool.write_xls_line(
                ws_name, row, title, style_code='title')

            # Header:
            row += 1
            report_pool.write_xls_line(
                ws_name, row, header, style_code='header')

            # Data lines:
            for detail in sorted(
                    data_report[supplier],
                    key=lambda d: d.product_tmpl_id.name):
                row += 1
                product = detail.product_tmpl_id

                # Write data:
                report_pool.write_xls_line(ws_name, row, (
                    product.id,
                    product.name,
                    product.default_code or '',
                    product.wp_sku or '',

                    product.categ_id.name or '',
                    (product.list_price, 'number'),

                    detail.product_name or '',
                    detail.product_code or '',
                    detail.min_qty or '',
                    detail.delay or '',
                    detail.price or '',
                    ('', 'number'),
                    ), style_code='text')

        # Save file:
        return report_pool.return_attachment('Report_Product')
