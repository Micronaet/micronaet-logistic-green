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
    mode = fields.Selection(
        string='Mode',
        selection=[
            ('supplier', 'Supplier per page'),
            ('internal', 'Internal'),
            ],
        required=True, default='supplier')

    @api.multi
    def excel_product_report(self, ):
        """ Button event, call correct mode
        """
        if self.mode == 'supplier':
            return self.excel_product_report_supplier_mode()
        else:
            return self.excel_product_report_internal_mode()

    @api.multi
    def excel_product_report_internal_mode(self, ):
        """ Mode: Internal
        """
        report_pool = self.env['excel.report']
        product_pool = self.env['product.template']

        # Excel file configuration:
        header = (
            'Ref.', 'Padre', 'Nome', 'Figlio',
            'Categoria', 'Listino',
            )
        column_width = (
            5, 5, 15, 55, 15,
            20, 10,
            )
        from_col = len(header)

        ws_name = 'Prodotti'
        report_pool.create_worksheet(ws_name, format_code='DEFAULT')
        report_pool.column_width(ws_name, column_width)
        report_pool.column_hidden(ws_name, [0])  # Hide 1st column

        # Title:
        row = 0
        title = ('', 'Tipo', 'Elenco prodotti con fornitori abbinati')
        report_pool.write_xls_line(
            ws_name, row, title, style_code='title')

        # Header:
        row += 1
        report_pool.write_xls_line(
            ws_name, row, header, style_code='header')

        max_level = 0
        for product in sorted(
                product_pool.search([]),
                key=lambda x: (x.wp_master_id.name or '', x.name or '')):
            row += 1
            if product.wp_master_id:
                product_type = 'Figlio'
            elif product.wp_master:
                product_type = 'Padre'

            report_pool.write_xls_line(ws_name, row, (
                product.id,
                product_type,
                product.wp_master_id.default_code or '',
                product.name,
                product.default_code or '',

                product.categ_id.name or '',
                (product.list_price, 'number'),
                ('', 'number'),
            ), style_code='text')

            supplier_block = []
            supplier_total = len(product.seller_ids)
            if supplier_total > max_level:
                max_level = supplier_total

            for supplier in product.seller_ids:
                supplier_block.extend([
                    supplier.name.name,
                    (supplier.price, 'number')])

            report_pool.write_xls_line(
                ws_name, row, supplier_block, style_code='text', col=from_col)

        # ---------------------------------------------------------------------
        # Setup columns for extra header:
        # ---------------------------------------------------------------------
        row = 1
        for i in range(max_level):
            header_col = from_col + 2 * i
            report_pool.column_width(ws_name, (30, 8), col=header_col)
            report_pool.write_xls_line(
                ws_name, row,
                ('Fornitore %s' % (i + 1), 'Costo %s' % (i + 1)),
                style_code='header', col=header_col)

        # ---------------------------------------------------------------------
        # Return file:
        # ---------------------------------------------------------------------

        return report_pool.return_attachment('Report_Product')

    @api.multi
    def excel_product_report_supplier_mode(self, ):
        """ Mode: Supplier
        """
        report_pool = self.env['excel.report']
        detail_pool = self.env['product.supplierinfo']

        # Wizard parameters:
        supplier = self.supplier_id

        # Collect data:
        domain = []
        if supplier:
            domain.append(
                ('name', '=', supplier.id))
        details = detail_pool.search(domain)

        # Excel file configuration:
        header = (
            'Ref.', 'Nome', 'Codice',
            'Categoria', 'Listino',
            'Nome (f)', 'Codice (f)',
            'Q. min (f)', 'T. cons.', 'Costo (f)',
            'Nuovo',
            )

        column_width = (
            5, 55, 15,
            20, 10,
            55, 15,
            10, 10, 10,
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
                supplier.id, 'Elenco prodotti fornitore: %s [%s]' % (
                    supplier.name, supplier.ref))
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

                    product.categ_id.name or '',
                    (product.list_price, 'number'),

                    detail.product_name or '',
                    detail.product_code or '',
                    detail.min_qty or '',
                    detail.delay or '',
                    detail.price or '',
                    ('', 'number'),
                    ), style_code='text')

        # Return file:
        return report_pool.return_attachment('Report_Product')
