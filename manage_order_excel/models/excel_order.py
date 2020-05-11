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

    @api.multi
    def export_pending_order(self):
        """ Export XLSX file for select product
        """
        report_pool = self.env['excel.report']
        line_pool = self.env['sale.order.line']
        lines = line_pool.search([
            # TODO only open
            ])

        title = (
            '',
            _('%s Sale order pending'),
            )

        header = (
            'ID',
            _('Order'), _('Date'),
            _('Code'), _('Name'), _('Category'),
            _('Q.'), _('Price'),
            _('ID Supplier'), _('Supplier'),
            _('Internal Stock'), _('From Internal'),
            _('Supplier Stock'), _('From Supplier'),
        )
        column_width = (
            1,
            25, 12, 20,
            15, 40,
            1, 30,
            5, 7
            5, 7,
        )

        # TODO hide columns!

        ws_name = _('Pending sale order')
        report_pool.create_worksheet(ws_name, format_code='DEFAULT')
        report_pool.column_width(ws_name, column_width)

        # Title:
        report_pool.column_hidden(ws_name, [0])  # Hide first columns
        row = 0
        report_pool.write_xls_line(ws_name, row, title, style_code='title')

        # Header:
        row += 1
        report_pool.write_xls_line(ws_name, row, header, style_code='header')

        # Collect:
        # TODO manage order from wizard
        for line in sorted(lines, key=lambda x: x.product_id.default_code):
            row += 1
            product = line.product_id
            order = line.order_id
            report_pool.write_xls_line(ws_name, row, (
                line.id,

                order.name,
                order.order_date,

                product.default_code,
                product.name,
                product.categ_id,

                (line.product_uom_qty, 'number'),
                (line.list_price, 'number'),

                (0, 'number'),  # Internal Stock
                (0, 'number'),  # Assigned internal

                (0, 'number'),  # Supplier Stock
                (0, 'number'),  # Assigned supplier
            ), style_code='text')
        return report_pool.return_attachment(_('current_sale_order_pending'))

    @api.multi
    def export_pending_order(self):
        """ Import sale order line selected where q. is present
        """
        purchase_pool = self.env['purchase.order']
        line_pool = self.env['sale.order.line']

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
        no_data = True
        start_import = False
        order_id = False

        purchase_orders = {}
        for row in range(ws.nrows):
            line_id = ws.cell_value(row, 0)
            # TODO manage partner_id (depend on column quantity:
            partner_id = 1

            if not start_import and line_id == 'ID':
                start_import = True
                _logger.info('%s. Header line' % row)
                continue

            if not start_import:
                _logger.info('%s. Jump line' % row)
                continue
            line_id = int(line_id)
            lst_price = ws.cell_value(row, 3)
            product_qty = ws.cell_value(row, 4)

            if not product_qty:
                _logger.info('%s. No quantity' % row)
                continue  # Jump empty line
            else:
                _logger.info('%s. Import line' % row)

            if no_data:
                no_data = False

                # -------------------------------------------------------------
                # Create sale order:
                # -------------------------------------------------------------
                if partner_id not in purchase_orders:
                    purchase_orders[partner_id] = purchase_pool.create({
                        'partner_id': self.portal_partner_id.id,
                        'user_id': self.user_id.id,
                        'date_order': now,
                        }).id

            # Create sale order line:
            line = line_pool.browse(line_id)
            product = line.product_id
            line_pool.create({
                'user_id': self.user_id.id,
                'order_id': order_id,
                'product_id': product.id,
                'name': product.name,
                'product_uom_qty': product_qty,
                #'price_unit': lst_price,
                })

        if purchase_orders:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Purchase orders created'),
                'view_type': 'form',
                'view_mode': 'tree,form',
                'res_id': False,
                'res_model': 'purchase.order',
                'view_id': False,
                'views': [(False, 'tree'), (False, 'form')],
                'domain': [('id', 'in', purchase_orders.keys())],
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
