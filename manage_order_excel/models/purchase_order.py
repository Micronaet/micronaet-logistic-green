# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import xlrd
import logging
import base64
import pdb
from odoo import models, fields, api, exceptions
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class PurchaseOrderExcelManageWizard(models.TransientModel):
    """ Model name: Purchase order wizard (import / export)
    """
    _name = 'purchase.order.excel.manage.wizard'
    _description = 'Manage delivery via Excel file'

    # Static position for Excel file columns:
    _column_position = {
        'id': 0,  # PO line ID
        'supplier_id': 1,
        # 'awaiting_qty': 8,
        'arrived_qty': 9,
        'all_qty': 10,
        'supplier_price': 7,
    }
    # TODO save last price in product supp. info?

    @api.multi
    def export_waiting_delivery(self):
        """ Export XLSX file for select product
        """
        report_pool = self.env['excel.report']
        line_pool = self.env['purchase.order.line']
        lines = line_pool.search([
            ('order_id.logistic_state', 'in', ('confirmed', )),  # Order conf.
            ])

        title = (
            '',
            '',
            _('Awaiting delivery'),
            )

        header = (
            'ID', _('ID Supplier'),
            _('Purchase Order'), _('Supplier'), _('Date'),

            _('Code'), _('Name'), _('Buy Price'),

            _('Q.remain'), _('Q. arrived'), _('All'),
            _('Status'),
        )
        column_width = (
            1, 1,
            15, 30, 10,

            12, 48, 10,

            10, 10, 5,
            11,
        )
        total_col = len(column_width)

        ws_name = _('Awaiting delivery')
        report_pool.create_worksheet(ws_name, format_code='DEFAULT')
        report_pool.column_width(ws_name, column_width)

        # Title:
        report_pool.column_hidden(ws_name, [0, 1])  # Hide ID columns
        row = 0
        report_pool.write_xls_line(ws_name, row, title, style_code='title')

        # Header:
        row += 1
        report_pool.write_xls_line(ws_name, row, header, style_code='header')
        report_pool.autofilter(ws_name, [row, 2, row, 5])

        # Collect:
        # TODO supplier filter?
        for line in sorted(
                lines, key=lambda x: x.order_id.name):
            waiting_qty = line.logistic_undelivered_qty  # Remain
            if waiting_qty <= 0:
                continue
            row += 1

            if line.logistic_sale_id:
                color = 'number_ok'
            else:
                color = 'number_error'

            # Readability:
            product = line.product_id
            order = line.order_id
            supplier = order.partner_id

            report_pool.write_xls_line(ws_name, row, (
                line.id,
                supplier.id,

                order.name or '',
                supplier.name,
                (order.date_order or '')[:10],

                product.default_code or '',
                product.name or '',
                (line.price_unit, 'number'),
                # TODO confirm price?

                (waiting_qty, color),
                (0, 'number_total'),
                ('', 'text_total'),
            ), style_code='text')

            formula = '=IF({0}={1}, "OK", ' \
                      'IF({0}<{1}, "ECCEDENTE", "INCOMPLETO")'.format(
                          report_pool.row_col_to_cell(row, 8),
                          report_pool.row_col_to_cell(row, 9),
                      )
            report_pool.write_formula(
                ws_name, row, total_col - 1, formula,
                value='INCOMPLETO',
                format_code='text',
            )
        return report_pool.return_attachment(_('current_picking_awaiting'))

    # -------------------------------------------------------------------------
    # Workflow confirmed to pending (or ready if all line are ready)
    # -------------------------------------------------------------------------
    # TODO manage extra purchase go in stock (correct also generation of PO)
    @api.multi
    def import_delivery_picking(self):
        """ Import sale order line selected where q. is present
        """
        move_pool = self.env['stock.move']
        quant_pool = self.env['stock.quant']
        picking_pool = self.env['stock.picking']

        # Sale order detail:
        sale_line_pool = self.env['sale.order.line']

        # Purchase order detail:
        # purchase_pool = self.env['purchase.order']
        line_pool = self.env['purchase.order.line']

        # Partner:
        partner_pool = self.env['res.partner']

        # now = fields.Datetime.now()
        gap = 0.000001  # For approx quantity check

        # ---------------------------------------------------------------------
        # Save passed file:
        # ---------------------------------------------------------------------
        b64_file = base64.decodebytes(self.file)
        now = ('%s' % fields.Datetime.now())[:19]
        filename = '/tmp/stock_%s.xlsx' % \
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

        # ---------------------------------------------------------------------
        # Load parameters:
        # ---------------------------------------------------------------------
        company = self.env.user.company_id
        location_id = company.logistic_location_id.id
        logistic_pick_in_type = company.logistic_pick_in_type_id
        logistic_pick_in_type_id = logistic_pick_in_type.id
        location_from = logistic_pick_in_type.default_location_src_id.id
        location_to = logistic_pick_in_type.default_location_dest_id.id

        # Store for manage after Excel loop:
        purchase_data = {}  # arrived data from supplier (key was supplier)
        internal_data = []  # extra data from supplier
        order_touched = []  # For end operation (dropship, default suppl.)

        log = {
            'error': [],
            'warning': [],
            'info': [],
        }
        start_import = False
        # Read and stock in dict data information:
        pdb.set_trace()
        for row in range(ws.nrows):
            line_id = ws.cell_value(row, self._column_position['id'])
            if not start_import and line_id == 'ID':
                start_import = True
                _logger.info('%s. Header line' % row)
                continue
            if not start_import:
                _logger.info('%s. Jump line' % row)
                continue

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

            # Extract needed data:
            supplier_id = ws.cell_value(
                row, self._column_position['supplier_id'])
            supplier_price = ws.cell_value(
                row, self._column_position['supplier_price']) or 0.0
            arrived_qty = ws.cell_value(
                row, self._column_position['arrived_qty']) or 0.0
            all_qty = ws.cell_value(
                row, self._column_position['all_qty'])
            # Not read reload from DB remain to delivery (waiting):
            logistic_sale_id = line.logistic_sale_id  # Linked to sale order!
            awaiting_qty = logistic_sale_id.logistic_remain_qty

            # -----------------------------------------------------------------
            # Check data in line:
            # -----------------------------------------------------------------
            # Quantity check
            if not arrived_qty and not all_qty:
                log['info'].append(_('%s. No qty, line not imported') % row)
                continue
            if all_qty:  # Extract arrived qty:
                arrived_qty = awaiting_qty  # Note: remain awaiting, not excel!

            # Check waiting VS delivered to customer
            # logistic_undelivered_qty = line.logistic_undelivered_qty  # PO
            # if abs(awaiting_qty - logistic_undelivered_qty) > gap:
            #     log['error'].append(
            #         _('%s. Order quantity > than remain to deliver: %s') % (
            #             row, line_id))
            #     continue

            # -----------------------------------------------------------------
            # A. Check supplier data
            # -----------------------------------------------------------------
            if not supplier_id:
                log['error'].append(_('%s. No ID for supplier') % row)
                continue
            supplier_id = int(supplier_id)
            suppliers = partner_pool.search([('id', '=', supplier_id)])
            if not suppliers:
                log['error'].append(
                    _('%s. No supplier found with ID: %s') % (
                        row, supplier_id))
                continue
            supplier = suppliers[0]

            if not supplier_price:
                log['warning'].append(
                    _('%s. No purchase price but qty present') % row)
                # continue  # TODO convert in error?

            # -----------------------------------------------------------------
            # Manage extra awaiting qty to stock:
            # -----------------------------------------------------------------
            internal_qty = 0
            if logistic_sale_id and arrived_qty > awaiting_qty:
                internal_qty = arrived_qty - awaiting_qty  # remain to load!
                arrived_qty = awaiting_qty
                log['warning'].append(
                    _('%s. Extra qty, go to internal stock') % row)
            elif not logistic_sale_id:
                log['warning'].append(
                    _('%s. Extra qty for all, go to internal stock') % row)
                internal_qty = arrived_qty  # All to internal stock
            if log['error']:
                # TODO manage what to do
                pass

            # -----------------------------------------------------------------
            # Populate data for next job:
            # -----------------------------------------------------------------
            if arrived_qty:
                log['info'].append(_('%s. Delivery for sale order') % row)
                if supplier not in purchase_data:
                    purchase_data[supplier] = []
                purchase_data[supplier].append(
                    (line, arrived_qty, supplier_price))

            if internal_qty:
                log['info'].append(_('%s. Delivery for internal stock') % row)
                internal_data.append(
                    (supplier, line, internal_qty, supplier_price)
                )

            # For final logistic state update
            if line.order_id not in order_touched:  # Purchase Order
                order_touched.append(line.order_id)

        # ---------------------------------------------------------------------
        #                 Assign management (Internal stock):
        # ---------------------------------------------------------------------
        for supplier, line, internal_qty, supplier_price in internal_data:
            product = line.product_id
            data = {
                'company_id': company.id,
                'in_date': now,
                'location_id': location_id,
                'product_id': product.id,
                'quantity': internal_qty,

                # Link:
                'logistic_purchase_id': line.id,
                # 'logistic_assigned_id': line.id,  # Link field
                # 'product_tmpl_id': used_product.product_tmpl_id.id,
                # 'lot_id'
                # 'package_id'
            }
            try:
                quant_pool.create(data)
            except:
                raise exceptions.Warning('Cannot create quants!')

        # ---------------------------------------------------------------------
        #                      Load purchased line
        # ---------------------------------------------------------------------
        sale_lines = []  # To check status
        for supplier in purchase_data:
            # Readability data:
            now = '{}'.format(fields.Datetime.now())[:10]
            origin = 'Del. {}'.format(now)

            # -----------------------------------------------------------------
            # Create new picking:
            # -----------------------------------------------------------------
            picking = picking_pool.create({
                'partner_id': supplier.id,
                'scheduled_date': now,
                'origin': origin,
                # 'move_type': 'direct',
                'picking_type_id': logistic_pick_in_type_id,
                'group_id': False,
                'location_id': location_id,
                'location_dest_id': location_to,
                # 'priority': 1,
                'state': 'done',  # immediately!
            })

            # -----------------------------------------------------------------
            # Append stock.move detail
            # -----------------------------------------------------------------
            for record in purchase_data[supplier]:
                # Readability data:
                line, arrived_qty, supplier_price = record
                product = line.product_id
                sale_line_id = line.logistic_sale_id.id
                origin = line.order_id.name
                if sale_line_id:  # Update status at the end
                    sale_lines.append(line.logistic_sale_id)

                # -------------------------------------------------------------
                # Create movement (not load stock):
                # -------------------------------------------------------------
                move_pool.create({
                    'company_id': company.id,
                    'partner_id': supplier.id,
                    'picking_id': picking.id,
                    'product_id': product.id,
                    'name': product.name or ' ',
                    'date': now,
                    'date_expected': now,
                    'location_id': location_id,
                    'location_dest_id': location_to,
                    'product_uom_qty': arrived_qty,
                    'product_uom': product.uom_id.id,
                    'state': 'done',
                    'origin': origin,

                    # Sale order line link:
                    'logistic_load_id': sale_line_id,

                    # Purchase order line line:
                    'logistic_purchase_id': line.id,

                    # 'purchase_line_id': load_line.id, # XXX needed?
                    # 'logistic_quant_id': quant.id, # XXX no quants here

                    # group_id
                    # reference'
                    # sale_line_id
                    # procure_method,
                    # 'product_qty': select_qty,
                })

            # -----------------------------------------------------------------
            # Update logistic status: Sale order
            # -----------------------------------------------------------------
            # Mark Sale Order Line ready:
            _logger.info('Update sale order line as ready:')
            orders = []
            for order_line in sale_lines:
                order = order_line.order_id
                if order not in orders:
                    orders.append(order)

                # Reload line to check remain awaiting:
                if sale_line_pool.browse(
                        order_line.id).logistic_remain_qty <= gap:
                    order_line.write({
                        'logistic_state': 'ready',
                    })

            all_ready = {'ready'}
            for order in orders:
                states = set(
                    [line.logistic_state for line in order.order_line])
                if states == all_ready:
                    order.write({
                        'logistic_state': 'ready'})

            # -----------------------------------------------------------------
            # Check Purchase order ready
            # -----------------------------------------------------------------
            _logger.info('Check purchase order closed:')
            for purchase in order_touched:
                for po_line in purchase.order_line:
                    if po_line.logistic_undelivered_qty:
                        break
                else:  # If exit without break >> all delivered!
                    purchase.write({
                        'logistic_state': 'done',
                    })

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    file = fields.Binary('XLSX file', filters=None)
