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
        product_pool = self.env['product.supplierinfo']

        supplier = self.supplier_id

        # Collect data:
        domain = []
        if supplier:
            domain.append(
                ('name', '=', supplier.id))
        products = product_pool.search(domain)

        # Excel file configuration:
        title = ('', 'Product pricelist', )
        header = (
            'Nome', 'Codice', 'Categoria', 'Fornitore', 'Listini', 'Nuovo')

        column_width = (40, 30, 20, 30, 10, 10)

        ws_name = _(supplier.name or '/')
        report_pool.create_worksheet(ws_name, format_code='DEFAULT')
        report_pool.column_width(ws_name, column_width)

        # Title:
        row = 0
        report_pool.write_xls_line(ws_name, row, title, style_code='title')

        # Header:
        row += 1
        report_pool.write_xls_line(ws_name, row, header, style_code='header')

        # Data lines:
        for supplierinfo in sorted(products,
                key=lambda x: (x.name, x.product_id.name)):
            row += 1

            product = supplierinfo.product_tmpl_id

            # Write data:
            report_pool.write_xls_line(ws_name, row, (
                product.name,
                product.default_code or '',
                product.categ_id.name or '',
                supplierinfo.name.name or '',
                (product.list_price, 'number'),
                ('', 'number'),
                ), style_code='text')

        # Save file:
        return report_pool.return_attachment('Report_Product')
