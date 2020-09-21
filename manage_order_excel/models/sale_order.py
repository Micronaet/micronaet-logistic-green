# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import xlrd
import logging
import base64
import pdb
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
        'supplier_id': 4,
        'order_qty': 3,
        'internal_qty': 8,
        'supplier_qty': 10,
        'supplier_code': 11,
        'supplier_price': 12,
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
        partner_pool = self.env['res.partner']

        lines = line_pool.search([
            ('order_id.logistic_state', 'in', (
                'confirmed', 'pending')),  # Order conf. or pending for partial
            ('logistic_state', 'in', ('draft', 'ordered')),  # Only draft line
            ('product_id.is_expense', '=', False),  # No expense product
            ])

        title = (
            '',
            _('Sale order pending'),
            )

        header = (
            'ID',
            _('Code'), _('Name'),
            # _('Category'),
            _('Q. ord.'),
            _('ID Supplier'), _('Default supplier'),
            _('Q. need'), _('Disp. stock'), _('Q. Int.'),
            _('Supp. Stock'), _('Q. Supp.'), _('Suppl. Ref.'), _('Buy price'),
            _('Status'),
        )
        column_width = (
            1,
            12, 48,
            # 25,
            7,
            1, 25,
            10, 10, 10,
            10, 10, 8, 10,
            10,
        )
        total_col = len(column_width)

        # 2 Pages:
        ws_name = _('Pending sale order')
        report_pool.create_worksheet(ws_name, format_code='DEFAULT')
        report_pool.column_width(ws_name, column_width)

        ws_supplier_page = _('Supplier')
        report_pool.create_worksheet(ws_supplier_page, format_code='DEFAULT')
        report_pool.column_width(ws_supplier_page, (10, 45))

        # ---------------------------------------------------------------------
        # PAGE: Supplier list
        suppliers = partner_pool.search([
            ('supplier', '=', True),
            ('ref', '!=', False),
        ])
        row = 0
        report_pool.write_xls_line(
            ws_supplier_page, row, ['Codice', 'Nome'], style_code='header')
        for supplier in sorted(suppliers, key=lambda s: int(s.ref)):
            row += 1
            report_pool.write_xls_line(ws_supplier_page, row, (
                supplier.ref,
                supplier.name,
            ), style_code='text')

        # ---------------------------------------------------------------------
        # PAGE: Order data
        # Title:
        report_pool.column_hidden(ws_name, [
            self._column_position['id'],
            self._column_position['supplier_id'],
        ])  # Hide ID columns
        row = 0
        report_pool.write_xls_line(ws_name, row, title, style_code='title')

        # Header:
        row += 1
        report_pool.write_xls_line(ws_name, row, header, style_code='header')

        # Collect:
        # TODO manage order from wizard
        collect_data = {}
        for line in sorted(
                lines,
                key=lambda x: (x.order_id.name or '')
                ):
            product = line.product_id

            # Jump service product (not used):
            if product.type == 'service':
                _logger.warning(
                    'Excluded service from report: %s' % product.default_code)
                continue
            if product in collect_data:
                collect_data[product][1] += line.product_uom_qty
                collect_data[product][2] += line.logistic_uncovered_qty
                collect_data[product][3].append(line)
            else:
                collect_data[product] = [
                    product.qty_available,  # Stock availability
                    line.product_uom_qty,  # order from file
                    line.logistic_uncovered_qty,  # remain to assign / ord.
                    [line],  # List of lines
                    ]

        for product in collect_data:
            qty_available, order_qty, qty_needed, lines = \
                collect_data[product]
            # qty available is used once (remember: grouped by product)

            # Readability:
            supplier_id, supplier_name, supplier_code, supplier_price = \
                self.get_suppinfo_supplier(product)

            # Category:
            # category = ', '.join(
            #     [item.name for item in product.wp_category_ids])

            if qty_needed <= 0.0:
                continue  # No uncovered qty remain

            row += 1
            # TODO manage incremental for this report!
            if qty_available >= qty_needed:
                qty_covered = qty_needed
                formula_value = 'OK'
            else:
                if qty_available > 0:
                    qty_covered = qty_available
                    collect_data[product.id] -= qty_available
                else:
                    qty_covered = 0.0
                formula_value = 'INCOMPLETO'

            report_pool.write_xls_line(ws_name, row, (
                '|'.join([str(item.id) for item in lines]),

                product.default_code or '',
                product.name or '',
                # category or '',

                (order_qty, 'number'),
                supplier_id,
                supplier_name,

                # Internal:
                (qty_needed, 'number_ok'),
                (qty_available, 'number'),
                (qty_covered, 'number_total'),

                # Supplier:
                (0 if supplier_id else '/', 'number'),
                (0 if supplier_id else '', 'number_total'),
                (supplier_code, 'text_total'),
                (supplier_price, 'number_total'),
            ), style_code='text')

            formula = '=IF({0}+{1}-{2}=0, "OK", ' \
                      'IF({0}+{1}-{2}<0, "INCOMPLETO", "ECCEDENTE")'.format(
                          report_pool.row_col_to_cell(
                              row, self._column_position['internal_qty']),
                          report_pool.row_col_to_cell(
                              row, self._column_position['supplier_qty']),
                          report_pool.row_col_to_cell(
                              row, self._column_position['order_qty']),
                      )

            # TODO Aggiungere colonna per cerca vert:
            #  =SE.ERRORE(
            #   CERCA.VERT(A7;Fornitori.$A$1:$B$3;2; 0); "CODICE ERRATO!")
            report_pool.write_formula(
                ws_name, row, total_col - 1, formula,
                value=formula_value,
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
        quant_pool = self.env['stock.quant']
        partner_pool = self.env['res.partner']

        gap = 0.000001  # For approx quantity check

        # ---------------------------------------------------------------------
        # Save passed file:
        # ---------------------------------------------------------------------
        b64_file = base64.decodebytes(self.file)
        now = ('%s' % fields.Datetime.now())[:19]
        filename = '/tmp/sale_%s.xlsx' % \
                   now.replace(':', '_').replace('-', '_')
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

        # Parameters from company (for assign qty):
        company = self.env.user.company_id  # TODO read from order?
        location_id = company.logistic_location_id.id

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
                row, self._column_position['order_qty']) or 0.0
            internal_qty = ws.cell_value(
                row, self._column_position['internal_qty']) or 0.0
            supplier_qty = ws.cell_value(
                row, self._column_position['supplier_qty']) or 0.0
            supplier_code = ws.cell_value(
                row, self._column_position['supplier_code']) or ''
            supplier_price = ws.cell_value(
                row, self._column_position['supplier_price']) or 0.0

            if type(supplier_code) == float:
                supplier_code = str(int(supplier_code))

            # -----------------------------------------------------------------
            # Check data in line:
            # -----------------------------------------------------------------
            # A. Check ID line
            line_id = int(line_id)
            if not line_id:
                log['error'].append(_('%s. No ID for this line') % row)
                continue

            lines = line_pool.search([('id', '=', line_id)])
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

            # TODO Import also incompleted line?!?
            # if abs(order_qty - supplier_qty - internal_qty) > gap:
            #    log['error'].append(
            #        _('%s. Quantity used different from ordered') % row)
            #    continue

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
        # TODO check remain quantity before create order or assigned qty
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
                reload_line = line_pool.browse(line.id)
                if reload_line.logistic_uncovered_qty:
                    reload_line.logistic_state = 'draft'  # not present state!
                else:
                    reload_line.logistic_state = 'ready'
            except:
                raise exceptions.Warning('Cannot create quants!')

        # ---------------------------------------------------------------------
        #                      Purchase management:
        # ---------------------------------------------------------------------
        purchase_orders = {}  # Supplier: Purchase order ID
        for supplier, line, supplier_qty, supplier_price in purchase_data:
            supplier_id = supplier.id

            # -----------------------------------------------------------------
            # Create purchase order (header):
            # -----------------------------------------------------------------
            if supplier_id not in purchase_orders:
                purchase_orders[supplier_id] = purchase_pool.create({
                    'partner_id': supplier_id,
                    'date_order': now,
                    'date_planned': now,
                }).id
            order_id = purchase_orders[supplier_id]

            # -----------------------------------------------------------------
            # Check over request:
            # -----------------------------------------------------------------
            reload_line = line_pool.browse(line.id)
            logistic_remain_qty = reload_line.logistic_remain_qty
            line_loop = []
            if supplier_qty > logistic_remain_qty:
                # Extra to stock:
                line_loop.append(
                    (supplier_qty - logistic_remain_qty, False)
                )
                supplier_qty = logistic_remain_qty

            # Remain or arrived:
            line_loop.append(
                (supplier_qty, line.id)
            )
            for qty, logistic_sale_id in line_loop:
                # Create purchase order line from sale:
                product = line.product_id
                po_line_pool.create({
                    'order_id': order_id,
                    'product_id': product.id,
                    'name': product.name,
                    'product_qty': qty,
                    'product_uom': product.uom_id.id,
                    'price_unit': supplier_price,
                    'date_planned': now,

                    # Link to sale:
                    'logistic_sale_id': logistic_sale_id,
                })

        # ---------------------------------------------------------------------
        #                     Update order logistic status:
        # ---------------------------------------------------------------------
        # Update logistic state for line after all
        for line in line_touched:
            if not line.logistic_remain_qty:  # All assigned or received
                line.write({
                    'logistic_state': 'ready',
                })
            elif line.logistic_purchase_qty:  # Waiting order not received
                line.write({
                    'logistic_state': 'ordered',
                })
            # else: Stay in draft mode

        # Update logistic state for order after all
        for order in order_touched:
            order.check_and_update_order_status()

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
                    ('id', 'in', [
                        po_id for po_id in purchase_orders.values()])],
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
