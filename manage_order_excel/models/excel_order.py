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

    # Static position for Excel file columns:
    _column_position = {
        'id': 0,
        'order_qty': 8,
        'internal_qty': 12,
        'supplier_qty': 14,
        'supplier_code': 15,
        'supplier_price': 16,
    }

    @api.model
    def get_suppinfo_supplier(self, product):
        for supplier in product.seller_ids:
            # First only:
            return (
                supplier.name.id,
                supplier.name.name,
                supplier.name.ref,
                supplier.price,
            )
        return False, '', '', 0

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
            ('order_id.logistic_state', 'in', ('confirmed', )),  # Order conf.
            ('logistic_state', '=', 'draft'),  # Only draft line
            ('product_id.is_expense', '=', False),  # No expense product
            ])

        title = (
            '',
            _('Sale order pending'),
            )

        header = (
            'ID',
            _('Connector'), _('Order'), _('Date'), _('Status'),
            _('Code'), _('Name'), _('Category'),
            _('Q.'), _('Price'),
            _('ID Supplier'), _('Supplier'),
            _('Int. Stock'), _('Q. Int.'),
            _('Supp. Stock'), _('Q. Supp.'), _('Ref.'), _('Cost'),
            _('Status'),
        )
        column_width = (
            1,
            20, 8, 15, 10,
            12, 48, 25,
            7, 7,
            1, 25,
            10, 10,
            10, 10, 8, 10,
            10,
        )
        total_col = len(column_width)

        ws_name = _('Pending sale order')
        report_pool.create_worksheet(ws_name, format_code='DEFAULT')
        report_pool.column_width(ws_name, column_width)

        # Title:
        report_pool.column_hidden(ws_name, [0, 10])  # Hide ID columns
        row = 0
        report_pool.write_xls_line(ws_name, row, title, style_code='title')

        # Header:
        row += 1
        report_pool.write_xls_line(ws_name, row, header, style_code='header')

        # Collect:
        # TODO manage order from wizard
        for line in sorted(
                lines,
                key=lambda x: (x.product_id.default_code or '')):
            row += 1
            product = line.product_id

            # Jump service product (not used):
            if product.type == 'service':
                _logger.warning(
                    'Excluded service from report: %s' % product.default_code)
                continue

            # Readability:
            order = line.order_id
            supplier_id, supplier_name, supplier_code, supplier_price = \
                self.get_suppinfo_supplier(product)

            # Category:
            category = ', '.join(
                [item.name for item in product.wp_category_ids])

            # Color setup:
            supplier_color = 'number_total' if supplier_id else 'number'
            qty_needed = line.product_uom_qty
            qty_available = product.qty_available
            # TODO manage incremental for this report!
            if qty_available >= qty_needed:
                qty_covered = qty_needed
            else:
                qty_covered = qty_available

            report_pool.write_xls_line(ws_name, row, (
                line.id,

                order.connector_id.name or '',
                order.name or '',
                order.date_order or '',
                order.wp_status or '',

                product.default_code or '',
                product.name or '',
                category or '',

                (qty_needed, 'number_ok'),
                (line.price_unit, 'number'),

                supplier_id,
                supplier_name,

                # Internal:
                (qty_available, 'number'),
                (qty_covered, 'number_total'),

                # Supplier:
                (0 if supplier_id else '/', 'number'),
                (0 if supplier_id else '', supplier_color),
                (supplier_code, 'text_total'),
                (supplier_price, 'number_total'),
            ), style_code='text')

            formula = '=IF({0}+{1}-{2}=0, "OK", ' \
                      'IF({0}+{1}-{2}<0, "INCOMPLETO", "ECCEDENTE")'.format(
                          report_pool.row_col_to_cell(row, 13),
                          report_pool.row_col_to_cell(row, 15),
                          report_pool.row_col_to_cell(row, 8),
                      )

            report_pool.write_formula(
                ws_name, row, total_col - 1, formula,
                value='INCOMPLETO',
                format_code='text',
            )
        return report_pool.return_attachment(_('current_sale_order_pending'))

    # -------------------------------------------------------------------------
    # Workflow confirmed to pending (or ready if all line are ready)
    # -------------------------------------------------------------------------
    @api.multi
    def import_pending_order(self):
        """ Import sale order line selected where q. is present
        """
        purchase_pool = self.env['purchase.order']
        line_pool = self.env['sale.order.line']
        po_line_pool = self.env['purchase.order.line']
        product_pool = self.env['product.product']
        quant_pool = self.env['stock.quant']
        partner_pool = self.env['res.partner']

        now = fields.Datetime.now()
        gap = 0.000001  # For approx quantity check

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
        import pdb; pdb.set_trace()

        # Parameters from company (for assign qty):
        company = self.env.user.company_id  # TODO read from order?
        company_id = company.id
        location_id = company.logistic_location_id.id
        # sort = company.logistic_order_sort

        # Store for manage after Excel loop:
        purchase_data = []
        internal_data = []
        order_touched = []  # For end operation (dropship, default suppl.)
        line_touched = []  # For end operation (dropship, default suppl.)

        log = {
            'error': [],
            'warning': [],
            'info': [],
        }
        start_import = False
        for row in range(ws.nrows):
            line_id = ws.cell_value(row, self._column_position['id'])
            if not start_import and line_id == 'ID':
                start_import = True
                _logger.info('%s. Header line' % row)
                continue
            if not start_import:
                _logger.info('%s. Jump line' % row)
                continue

            # Extract needed data:
            order_qty = ws.cell_value(
                row, self._column_position['order_qty'])
            internal_qty = ws.cell_value(
                row, self._column_position['internal_qty'])
            supplier_qty = ws.cell_value(
                row, self._column_position['supplier_qty'])
            supplier_code = ws.cell_value(
                row, self._column_position['supplier_code'])
            supplier_price = ws.cell_value(
                row, self._column_position['supplier_price'])

            # -----------------------------------------------------------------
            # Check data in line:
            # -----------------------------------------------------------------
            # A. Check ID line
            line_id = int(line_id)
            if not line_id:
                log['error'].append(_('%s. No ID for this line') % row)
                continue

            lines = partner_pool.search([('id', '=', line_id)])
            if not lines:
                log['error'].append(
                    _('%s. No lined found with ID: %s') % (
                        row, line_id))
                continue
            line = lines[0]

            # B. Check quantity:
            if not internal_qty and not supplier_qty:
                log['info'].append(_('%s. No qty, line not imported') % row)
                continue

            if abs(order_qty - supplier_qty - internal_qty) > gap:
                log['error'].append(
                    _('%s. Quantity used different from ordered') % row)
                continue

            # C. Check supplier code and price
            supplier = False
            if supplier_qty:
                if not supplier_code:
                    log['error'].append(
                        _('%s. No supplier code but qty present') % row)
                    continue

                if not supplier_price:
                    log['warning'].append(
                        _('%s. No supplier price but qty present') % row)
                    # continue  # TODO convert in error?

                suppliers = partner_pool.search([('ref', '=', supplier_code)])
                if not suppliers:
                    log['error'].append(
                        _('%s. No supplier found with code: %s') % (
                            row, supplier_code))
                    continue

                if len(suppliers) > 1:
                    log['error'].append(
                        _('%s. More supplier with code: %s [# %s]') % (
                            row, supplier_code, len(suppliers)))
                    continue
                supplier = suppliers[0]

            if log['error']:
                # TODO manage what to do
                pass

            # 1. Assign management (Internal stock):
            if internal_qty:
                internal_data.append((line, internal_qty))

            # 2. Purchase management:
            if supplier:   # So supplier qty present!
                log['info'].append(_('%s. Line add in purchase order') % row)
                purchase_data.append(
                    (supplier, line, supplier_qty, supplier_price))

            # For final logistic state update TODO (use ID?!?)
            line_touched.append(line)  # Line
            if line.order_id not in order_touched:  # Order
                order_touched.append(line.order_id)

        # ---------------------------------------------------------------------
        #                 Assign management (Internal stock):
        # ---------------------------------------------------------------------
        for line, internal_qty in internal_data:
            product = line.product_id
            # TODO no check in stock, was done during assign
            data = {
                'company_id': company.id,
                'in_date': now,
                'location_id': location_id,
                'product_id': product.id,
                'quantity': - internal_qty,
                'logistic_assigned_id': line.id,  # Link field
                # 'product_tmpl_id': used_product.product_tmpl_id.id,
                # 'lot_id'
                # 'package_id'
            }
            try:
                quant_pool.create(data)
            except:
                raise exceptions.Warning('Cannot create quants!')

        # ---------------------------------------------------------------------
        #                      Purchase management:
        # ---------------------------------------------------------------------
        purchase_orders = {}
        for supplier, line, supplier_qty, supplier_price in purchase_data:
            supplier_id = supplier.id

            # -----------------------------------------------------------------
            # Create purchase order (header):
            # -----------------------------------------------------------------
            if supplier_id not in purchase_orders:
                purchase_orders[supplier_id] = purchase_pool.create({
                    'partner_id': supplier_id,
                    'date_order': now,
                }).id
            order_id = purchase_orders[supplier_id]

            # Create purchase order line from sale:
            product = line.product_id
            po_line_pool.create({
                'order_id': order_id,
                'product_id': product.id,
                'name': product.name,
                'product_qty': supplier_qty,
                'product_uom': product.uom_id.id,
                'price_unit': supplier_price,
                'date_planned': now,
            })

        # ---------------------------------------------------------------------
        #                     Update order logistic status:
        # ---------------------------------------------------------------------
        # Update logistic state for line after all
        for line in line_touched:
            product = line.product_id
            if not product.logistic_remain_qty:  # All assigned or received
                line.write({
                    'logistic_state': 'ready',
                })
            elif product.logistic_purchased_qty:  # Waiting order not received
                line.write({
                    'logistic_state': 'pending',
                })
            # Stay in draft mode

        # Update logistic state for order after all
        all_ready = set(['ready'])
        for order in order_touched:
            order_states = set(
                [line.logistic_state for line in order.order_line])
            if order_states == all_ready:
                order.write({
                    'logistic_state': 'ready',
                })

        if purchase_orders:
            # For printing purchase order
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
                    ('id', 'in', purchase_orders.values())],
                'context': self.env.context,
                'target': 'current',
                'nodestroy': False,
                }
        else:
            # Open sale order when purchase not present
            return {
                'type': 'ir.actions.act_window',
                'name': _('Orders updated'),
                'view_type': 'form',
                'view_mode': 'tree,form',
                'res_id': False,
                'res_model': 'sale.order',
                'view_id': False,
                'views': [(False, 'tree'), (False, 'form')],
                'domain': [
                    ('id', 'in', [o.id for o in order_touched])],
                'context': self.env.context,
                'target': 'current',
                'nodestroy': False,
                }

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    file = fields.Binary('XLSX file', filters=None)
