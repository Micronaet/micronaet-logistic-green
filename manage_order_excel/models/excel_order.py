# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import xlrd
import logging
import base64
from odoo import models, fields, api, exceptions
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class SaleOrderExcelManageWizard(models.TransientModel):
    """ Model name: Order wizard (import / export)
    """
    _name = 'sale.order.excel.manage.wizard'
    _description = 'Extract pricelist wizard'

    @api.model
    def get_suppinfo_supplier(self, product):
        for supplier in product.seller_ids:
            # First only:
            return supplier.name.id, supplier.name.name
        return False, ''

    @api.model
    def get_suppinfo_price(self, product):
        for supplier in product.seller_ids:
            # First only:
            return supplier.price
        return 0

    @api.multi
    def export_pending_order(self):
        """ Export XLSX file for select product
        """
        report_pool = self.env['excel.report']
        line_pool = self.env['sale.order.line']
        lines = line_pool.search([
            # TODO only open
            ('connector_id', '!=', False),
            ('wp_status', 'in', ('pending', ))
            ])

        title = (
            '',
            _('Sale order pending'),
            )

        header = (
            'ID',
            _('Connettore'), _('Order'), _('Date'),
            _('Code'), _('Name'), _('Category'),
            _('Q.'), _('Price'),
            _('ID Supplier'), _('Supplier'),
            _('Int. Stock'), _('Q. Int.'),
            _('Supp. Stock'), _('Q. Supp.'),
            _('Status'),
        )
        column_width = (
            1,
            15, 12, 15,
            10, 45, 25,
            7, 7,
            1, 30,
            10, 10,
            10, 10,
            4,
        )
        total_col = len(column_width)

        ws_name = _('Pending sale order')
        report_pool.create_worksheet(ws_name, format_code='DEFAULT')
        report_pool.column_width(ws_name, column_width)

        # Title:
        report_pool.column_hidden(ws_name, [0, 9])  # Hide ID columns
        row = 0
        report_pool.write_xls_line(ws_name, row, title, style_code='title')

        # Header:
        row += 1
        report_pool.write_xls_line(ws_name, row, header, style_code='header')

        # Collect:
        # TODO manage order from wizard
        for line in sorted(lines,
                key=lambda x: (x.product_id.default_code or '')):
            row += 1
            product = line.product_id
            if product.type == 'service':
                _logger.warning(
                    'Excluded service from report: %s' % product.default_code)
                continue
            order = line.order_id
            supplier_id, supplier_name = self.get_suppinfo_supplier(product)
            report_pool.write_xls_line(ws_name, row, (
                line.id,

                order.connector_id.name or '',
                order.name,
                order.date_order,

                product.default_code,
                product.name,
                product.categ_id.name or ' ',

                (line.product_uom_qty, 'number'),
                (line.price_unit, 'number'),

                supplier_id,
                supplier_name,

                # Internal:
                (0, 'number'),
                (0, 'number_total'),
                # Supplier:
                (0 if supplier_id else '/', 'number'),
                (0, 'number_total'),
                '',  # TODO add formula after:
            ), style_code='text')
            # report_pool.write_formula(
            #     ws_name, row, total_col - 1, '=SE(M3+O3 = H3;"OK";"KO")',
            #     # format_code = 'number_ok', value='',
            # )
        return report_pool.return_attachment(_('current_sale_order_pending'))

    @api.multi
    def import_pending_order(self):
        """ Import sale order line selected where q. is present
        """
        purchase_pool = self.env['purchase.order']
        line_pool = self.env['sale.order.line']
        po_line_pool = self.env['purchase.order.line']

        # ---------------------------------------------------------------------
        # Save passed file:
        # ---------------------------------------------------------------------
        b64_file = base64.decodebytes(self.file)
        now = ('%s' % fields.Datetime.now())[:19]
        filename = '/tmp/tx_%s.xlsx' % now.replace(':', '_').replace('-', '_')
        f = open(filename, 'wb')
        f.write(b64_file)
        f.close()

        # ---------------------------------------------------------------------
        # Open Excel file:
        # ---------------------------------------------------------------------
        try:
            wb = xlrd.open_workbook(filename)
        except:
            raise exceptions.Warning(_('Cannot read XLS file'))

        ws = wb.sheet_by_index(0)
        start_import = False
        company_id = 1  # TODO read from order?

        purchase_orders = {}
        # import pdb; pdb.set_trace()
        for row in range(ws.nrows):
            line_id = ws.cell_value(row, 0)
            if not start_import and line_id == 'ID':
                start_import = True
                _logger.info('%s. Header line' % row)
                continue
            if not start_import:
                _logger.info('%s. Jump line' % row)
                continue

            purchase_data = []
            if ws.cell_value(row, 12):
                purchase_data.append(
                    (company_id, ws.cell_value(row, 12)))
            if ws.cell_value(row, 14):
                purchase_data.append(
                    (ws.cell_value(row, 13), ws.cell_value(row, 14)))
            if not purchase_data:
                _logger.warning('%s. No data jump row' % row)
                continue

            line_id = int(line_id)
            for partner_id, product_qty in purchase_data:
                _logger.info('%s. Import line [Supplier %s]' % (
                    row, partner_id))

                # -------------------------------------------------------------
                # Create purchase order (header):
                # -------------------------------------------------------------
                if partner_id not in purchase_orders:
                    purchase_orders[partner_id] = purchase_pool.create({
                        'partner_id': partner_id,
                        'date_order': now,
                        }).id
                order_id = purchase_orders[partner_id]

                # Create purchase order line from sale:
                line = line_pool.browse(line_id)
                product = line.product_id
                po_line_pool.create({
                    'order_id': order_id,
                    'product_id': product.id,
                    'name': product.name,
                    'product_qty': product_qty,
                    'product_uom': product.uom_id.id,
                    'price_unit': self.get_suppinfo_price(product),  # TODO better
                    'date_planned': now,
                    })

        if purchase_orders:
            import pdb; pdb.set_trace()
            return {
                'type': 'ir.actions.act_window',
                'name': _('Purchase orders created'),
                'view_type': 'form',
                'view_mode': 'tree,form',
                'res_id': False,
                'res_model': 'purchase.order',
                'view_id': False,
                'views': [(False, 'tree'), (False, 'form')],
                'domain': [
                    ('id', 'in', [i for i in purchase_orders.values()])],
                'context': self.env.context,
                'target': 'current',
                'nodestroy': False,
                }
        else:
            raise exceptions.Warning('No selection on file!')

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    file = fields.Binary('XLSX file', filters=None)
