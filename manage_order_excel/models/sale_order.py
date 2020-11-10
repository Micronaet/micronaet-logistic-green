# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import xlrd
import logging
import base64
import pdb
from odoo import models, fields, api, exceptions
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    """ Extra parameters
    """
    _inherit = 'res.company'

    sale_export_ref = fields.Char(
        'Sale export ref.',
        help='Last file exported, used for check in import'
    )
    purchase_export_ref = fields.Char(
        'Purchase export ref.',
        help='Last file exported, used for check in import'
    )


class SaleOrderExcelManageWizard(models.TransientModel):
    """ Model name: Order wizard (import / export)
    """
    _name = 'sale.order.excel.manage.wizard'
    _description = 'Extract pricelist wizard'

    # Static position for Excel file columns:
    _column_position = {
        'id': 0,
        'needed_qty': 5,
        'internal_qty': 7,
        'supplier_qty': 9,
        'supplier_code': 10,
        'supplier_price': 11,
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

        # Counter on report:
        title_counter = self.env['ir.sequence'].next_by_code(
            'sale.order.excel.export.sequence')
        company = self.env.user.company_id
        company.write({'sale_export_ref': title_counter})

        title = (
            title_counter,
            _('Sale order pending: %s' % title_counter),
            )

        header = (
            'ID',
            _('Ordini'),
            _('Codice'), _('Nome'),
            # _('Category'),
            _('Fornitore pred.'),
            _('Q. necess.'), _('Disp. magazz.'), _('Q. da mag.'),

            _('Disp. forn.'), _('Q. ord. forn.'), _('Rif. forn.'),
            _('Prezzo acq.'),

            _('Status'),
        )
        column_width = (
            1, 20,
            12, 48,
            # 25,
            25,
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
        ])  # Hide ID columns
        row = 0
        report_pool.write_xls_line(ws_name, row, title, style_code='title')

        # Header:
        row += 1
        report_pool.write_xls_line(ws_name, row, header, style_code='header')
        report_pool.autofilter(ws_name, (row, 0, row, total_col-1))

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

        for product in sorted(collect_data, key=lambda p: p.name):
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
                    collect_data[product][0] -= qty_available
                else:
                    qty_covered = 0.0
                formula_value = 'INCOMPLETO'

            report_pool.write_xls_line(ws_name, row, (
                '|'.join([str(item.id) for item in lines]),
                ', '.join([item.order_id.name for item in lines]),

                product.default_code or '',
                product.name or '',
                # category or '',

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
                              row, self._column_position['needed_qty']),
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

        # Check sheet mode:
        sheet_mode = ws.cell_value(0, 0)
        company = self.env.user.company_id
        title_counter = company.sale_export_ref
        if sheet_mode != title_counter:
            raise exceptions.Warning(
                'Wrong Excel file mode, expected: %s, got: %s' % (
                    title_counter, sheet_mode))

        # Parameters from company (for assign qty):
        company = self.env.user.company_id  # TODO read from order?
        location_id = company.logistic_location_id.id

        # Store for manage after Excel loop:
        purchase_data = []
        internal_data = []
        order_touched = []  # For end operation (dropship, default suppl.)
        line_touched_ids = []  # For end operation (dropship, default suppl.)

        log = {
            'error': [],
            'warning': [],
            'info': [],
        }
        start_import = False
        for row in range(ws.nrows):
            line_ref = ws.cell_value(row, self._column_position['id'])
            if not start_import and line_ref == 'ID':
                start_import = True
                _logger.info('%s. Header line' % row)
                continue
            if not start_import:
                _logger.info('%s. Jump line' % row)
                continue

            # Extract needed data:
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
            line_ids = [int(line_id) for line_id in line_ref.split('|')]
            if not line_ids:
                log['error'].append(_('%s. No ID for this line') % row)
                continue

            lines = sorted(
                line_pool.browse(line_ids),
                key=lambda l: l.order_id.date_order,
            )
            if not lines:
                log['error'].append(
                    _('%s. No lined found with ID: %s') % (
                        row, line_ids))
                continue

            # B. Check quantity:
            if not internal_qty and not supplier_qty:
                log['info'].append(_('%s. No qty, line not imported') % row)
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

            for line in lines:
                remain_to_cover_qty = line.logistic_remain_qty
                product = line.product_id

                # 1. Assign management (Internal stock):
                if remain_to_cover_qty <= internal_qty:
                    internal_data.append((line, remain_to_cover_qty, 'ready'))
                    internal_qty -= remain_to_cover_qty  # Remain
                    remain_to_cover_qty = 0
                elif internal_qty:  # There's internal but not for all
                    internal_data.append((line, internal_qty, 'draft'))
                    remain_to_cover_qty -= internal_qty  # correct remain qty
                    internal_qty = 0  # Used all

                if remain_to_cover_qty > 0:  # more remain qty to cover
                    # 2. Purchase management (for not covered):
                    if supplier:   # So supplier qty present!
                        log['info'].append(
                            _('%s. Line add in purchase order') % row)

                        if remain_to_cover_qty <= supplier_qty:  # Cover all
                            purchase_data.append((
                                supplier,
                                line.id,
                                product,
                                remain_to_cover_qty,
                                supplier_price,
                            ))
                            supplier_qty -= remain_to_cover_qty  # Remain
                        else:  # Partially covered
                            purchase_data.append((
                                supplier,
                                line.id,
                                product,
                                supplier_qty,
                                supplier_price,
                            ))
                            supplier_qty = 0  # Used all

                    # For final logistic state update TODO (use ID?!?)
                    line_touched_ids.append(line.id)  # Line (only purchased)

                # All must be checked:
                if line.order_id not in order_touched:  # Order
                    order_touched.append(line.order_id)

            # TODO check if remain something
            # if internal_qty not checked (assigned more, dismiss!)
            if supplier_qty:  # Check if something for internal stock
                purchase_data.append((
                    supplier,
                    False,
                    product,
                    supplier_qty,
                    supplier_price,
                ))

        # ---------------------------------------------------------------------
        #                 Assign management (Internal stock):
        # ---------------------------------------------------------------------
        # TODO check remain quantity before create order or assigned qty
        for line, internal_qty, new_state in internal_data:
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
                # pdb.set_trace()
                line.write({'logistic_state': new_state})
            except:
                raise exceptions.Warning('Cannot create quants!')

        # ---------------------------------------------------------------------
        #                      Purchase management:
        # ---------------------------------------------------------------------
        purchase_orders = {}  # Supplier: Purchase order ID
        for supplier, line_id, product, supplier_qty, supplier_price \
                in purchase_data:
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
            # Create purchase order line from sale:
            po_line_pool.create({
                'order_id': order_id,
                'product_id': product.id,
                'name': product.name,
                'product_qty': supplier_qty,
                'product_uom': product.uom_id.id,
                'price_unit': supplier_price,
                'date_planned': now,

                # Link to sale:
                'logistic_sale_id': line_id,
            })

        # ---------------------------------------------------------------------
        #                     Update order logistic status:
        # ---------------------------------------------------------------------
        # Update logistic state for line after all
        for line in line_pool.browse(line_touched_ids):
            if line.logistic_remain_qty <= 0.0:  # All assigned or received
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
