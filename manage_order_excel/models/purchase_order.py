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
        'supplier_price': 7,
        'remain_qty': 8,
        'arrived_qty': 9,
        'all_qty': 10,
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

        # Counter on report:
        title_counter = self.env['ir.sequence'].next_by_code(
            'purchase.order.excel.export.sequence')
        company = self.env.user.company_id
        company.write({'purchase_export_ref': title_counter})

        title = (
            title_counter,
            '',
            _('Awaiting delivery: %s' % title_counter),
            )

        header = (
            'ID', 'ID supplier',
            _('Purchase order'), _('Supplier'), _('Date'),

            _('Code'), _('Name'), _('Buy Price'),

            _('Q.remain'), _('Q. arrived'), _('All'),
            _('Status'),
        )
        column_width = (
            1, 1,
            20, 15, 30,

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
        report_pool.autofilter(ws_name, [row, 2, row, 4])

        # Collect:
        # TODO supplier filter?
        collect_data = {}
        for line in lines:
            waiting_qty = line.logistic_undelivered_qty  # Remain from PO
            if waiting_qty <= 0:
                continue
            # Readability:
            product = line.product_id
            order = line.order_id
            supplier = order.partner_id
            key = (supplier, product)
            if key not in collect_data:
                collect_data[key] = [
                    0.0,
                    []
                ]
            collect_data[key][0] += waiting_qty
            collect_data[key][1].append(line)

        for key in sorted(collect_data, key=lambda k: (k[0].name, k[1].name)):
            waiting_qty, lines = collect_data[key]
            supplier, product = key
            first_line = lines[0]
            row += 1

            report_pool.write_xls_line(ws_name, row, (
                '|'.join([str(line.id) for line in lines]),
                supplier.id,

                first_line.order_id.name,
                supplier.name,
                first_line.order_id.date_order,

                product.default_code or '',
                product.name or '',
                (first_line.price_unit or '', 'number'),
                # TODO confirm price?

                (waiting_qty, 'number_ok'),
                (0, 'number_total'),
                ('', 'text_total'),
            ), style_code='text')

            formula = '=IF({0}={1}, "OK", ' \
                      'IF({0}<{1}, "ECCEDENTE", "INCOMPLETO")'.format(
                          report_pool.row_col_to_cell(
                              row, self._column_position['remain_qty']),
                          report_pool.row_col_to_cell(
                              row, self._column_position['arrived_qty']),
                          # TODO manage All: 11
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

        # Check sheet mode:
        sheet_mode = ws.cell_value(0, 0)
        company = self.env.user.company_id
        title_counter = company.purchase_export_ref
        if not title_counter:
            raise exceptions.Warning(
                'Wrong Excel file mode, last was yet imported')

        if sheet_mode != title_counter:
            raise exceptions.Warning(
                'Wrong Excel file mode, expected: %s, got: %s' % (
                    title_counter, sheet_mode))
        company.purchase_export_ref = False  # Clean when imported

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
        picking_data = {}  # arrived data from supplier (key was supplier)
        internal_data = []  # extra data from supplier
        order_touched = []  # For end operation (dropship, default suppl.)

        log = {
            'error': [],
            'warning': [],
            'info': [],
        }
        start_import = False
        # Read and stock in dict data information:
        for row in range(ws.nrows):
            line_ref = ws.cell_value(row, self._column_position['id'])
            if not start_import and line_ref == 'ID':
                start_import = True
                _logger.info('%s. Header line' % row)
                continue
            if not start_import:
                _logger.info('%s. Jump line' % row)
                continue

            # A. Check ID line
            line_ids = [int(line_id) for line_id in line_ref.split('|')]

            if not line_ids:
                log['error'].append(_('%s. No ID for this line') % row)
                continue
            lines = line_pool.browse(line_ids)

            if not lines:
                log['error'].append(
                    _('%s. No lined found with ID: %s') % (
                        row, line_ids))
                continue

            # Extract needed data:
            supplier_id = ws.cell_value(
                row, self._column_position['supplier_id'])
            supplier_price = ws.cell_value(
                row, self._column_position['supplier_price']) or 0.0
            all_qty = ws.cell_value(
                row, self._column_position['all_qty'])

            if all_qty:
                # Manage not delivered to client
                arrived_qty = sum([l.logistic_undelivered_qty for l in lines])
            else:
                arrived_qty = ws.cell_value(
                    row, self._column_position['arrived_qty']) or 0.0

            # -------------------------------------------------------------
            # Check if arrived is present:
            # -------------------------------------------------------------
            if not arrived_qty:
                log['info'].append(
                    _('%s. No qty, line not imported') % row)
                continue

            # -------------------------------------------------------------
            # A. Check supplier data
            # -------------------------------------------------------------
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

            lines = sorted(
                lines,
                # Before linked order create first after internal stock:
                key=lambda l: (not l.logistic_sale_id, l.create_date),
            )
            for line in lines:
                if not arrived_qty:  # Nothing remain
                    break

                # Not read reload from DB remain to delivery (waiting):
                logistic_sale_id = line.logistic_sale_id  # Linked sale order!
                undelivered_qty = line.logistic_undelivered_qty

                # Extract used qty for this line:
                if undelivered_qty <= arrived_qty:
                    used_qty = undelivered_qty
                else:
                    used_qty = arrived_qty
                if used_qty < 0:
                    continue
                arrived_qty -= used_qty

                # -------------------------------------------------------------
                # Populate data for next job:
                # -------------------------------------------------------------
                if supplier not in picking_data:
                    picking_data[supplier] = []

                # Always create stock move:
                log['info'].append(_('%s. Delivery for sale order') % row)

                # Purchase / picking data:
                picking_data[supplier].append(
                    (line, used_qty, supplier_price, False))

                if not logistic_sale_id:  # Quants data (goes also in internal)
                    internal_data.append(
                        (supplier, line, used_qty, supplier_price)
                    )

                # For final logistic state update
                if line.order_id not in order_touched:  # Purchase Order
                    order_touched.append(line.order_id)

            # -----------------------------------------------------------------
            # Extra goes in internal stock:
            # -----------------------------------------------------------------
            if arrived_qty > 0:
                # line was last line of the list (extra will be attached here)
                # NOTE: always present:
                picking_data[supplier].append(
                    (line, arrived_qty, supplier_price, True))

                internal_data.append(
                    (supplier, line, arrived_qty, supplier_price)
                )

        # =====================================================================
        #                     Final Stock operations:
        # =====================================================================
        # A. Internal stock:
        # ------------------
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

        # ----------------------
        # B. Load purchased line
        # ----------------------
        sale_lines = []  # To check status
        for supplier in picking_data:
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
            for record in picking_data[supplier]:
                # Readability data:
                line, arrived_qty, supplier_price, go_internal = record
                product = line.product_id
                if go_internal:
                    sale_line_id = False
                else:
                    sale_line_id = line.logistic_sale_id.id
                    if sale_line_id:  # Update status at the end
                        sale_lines.append(line.logistic_sale_id)

                origin = line.order_id.name

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
            for order in orders:  # TODO reload?
                states = set(
                    [line.logistic_state for line in order.order_line])
                if states == all_ready:
                    order.write({'logistic_state': 'ready'})

            # -----------------------------------------------------------------
            # Check Purchase order ready
            # -----------------------------------------------------------------
            _logger.info('Check purchase order closed:')
            for purchase in order_touched:
                for po_line in purchase.order_line:
                    if po_line.logistic_undelivered_qty > 0:
                        break
                else:  # If exit without break >> all delivered!
                    purchase.write({
                        'logistic_state': 'done',
                    })

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    file = fields.Binary('XLSX file', filters=None)
