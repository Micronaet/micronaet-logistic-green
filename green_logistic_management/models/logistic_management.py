# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import os
import sys
import logging
import pdb
from odoo import api, fields, models, tools, exceptions, SUPERUSER_ID
from odoo.addons import decimal_precision as dp
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class ProductSuppinfo(models.Model):
    """ Model name: Product supplier info
    """

    _inherit = 'product.supplierinfo'

    supplier_stock_qty = fields.Float(string='Supplier stock')


class ResCompany(models.Model):
    """ Model name: Res Company
    """

    _inherit = 'res.company'

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    # Logistic parameters:
    # TODO Needed (maybe for export in Excel)?
    logistic_order_sort = fields.Selection([
        ('create_date', 'Create date'),
        ('validity_date', 'Validity date'),
        ], 'Order sort', default='create_date',
        help='Sort order to assign stock availability',
        required=True,
        )
    logistic_location_id = fields.Many2one(
        'stock.location', 'Stock Location IN',
        help='Stock location for q. created',
        required=True,
        )

    # Pick type for load / unload:
    logistic_pick_in_type_id = fields.Many2one(
        'stock.picking.type', 'Pick in type',
        help='Picking in type for load documents',
        required=True,
        )
    logistic_pick_out_type_id = fields.Many2one(
        'stock.picking.type', 'Pick out type',
        help='Picking in type for unload documents',
        required=True,
        )


class ProductTemplate(models.Model):
    """ Template add fields
    """
    _inherit = 'product.template'

    # -------------------------------------------------------------------------
    # Columns:
    # -------------------------------------------------------------------------
    is_expense = fields.Boolean(
        'Expense product',
        help='Expense product is not order and produced')
    is_refund = fields.Boolean(
        'Refund product',
        help='Refund product use for mark value for total')


class PurchaseOrder(models.Model):
    """ Model name: Sale Order
    """

    _inherit = 'purchase.order'

    # -------------------------------------------------------------------------
    #                           UTILITY:
    # -------------------------------------------------------------------------
    @api.multi
    def extract_purchase_order_report(self):
        """ Extract PDF report
        """
        folder = os.path.expanduser(
            '~/.local/share/Odoo/filestore/%s/Data/document/purchase' %
            self.env.cr.dbname)
        os.system('mkdir -p %s' % folder)

        # TODO Sanitize file name:
        filename = (self.name or self.id).replace('/', '_')
        filename = filename + '.pdf'
        fullname = os.path.join(folder, filename)

        REPORT_ID = 'purchase.action_report_purchase_order'
        pdf = self.env.ref(REPORT_ID).render_qweb_pdf(self.ids)
        f_pdf = open(fullname, 'wb')
        f_pdf.write(pdf[0])
        f_pdf.close()
        _logger.info('Extract purchase order: %s' % fullname)
        return fullname

    @api.model
    def return_purchase_order_list_view(self, purchase_ids):
        """ Return purchase order tree from ids
        """
        tree_view_id = form_view_id = False

        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase order selected:'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'purchase.order',
            'view_id': tree_view_id,
            'views': [(tree_view_id, 'tree'), (form_view_id, 'form')],
            'domain': [('id', 'in', purchase_ids)],
            'context': self.env.context,
            'target': 'current',
            'nodestroy': False,
            }

    @api.model
    def check_order_confirmed_done(self, purchase_ids=None):
        """ Check passed purchase IDs passed or all confirmed order
            if not present
        """
        if purchase_ids:
            purchases = self.browse(purchase_ids)
        else:
            purchases = self.search([('logistic_state', '=', 'confirmed')])

        for purchase in purchases:
            done = True

            for line in purchase.order_line:
                if line.logistic_undelivered_qty > 0:
                    done = False
                    break

            # Update if all line hasn't undelivered qty
            if done:
                purchase.logistic_state = 'done'
        return True

    # -------------------------------------------------------------------------
    #                            BUTTON:
    # -------------------------------------------------------------------------
    @api.multi
    def open_purchase_line(self):
        """ Open purchase line detail view:
        """
        model_pool = self.env['ir.model.data']
        tree_view_id = model_pool.get_object_reference(
            'green_logistic_management', 'view_purchase_order_line_tree')[1]
        form_view_id = model_pool.get_object_reference(
            'green_logistic_management', 'view_purchase_order_line_form')[1]

        line_ids = [item.id for item in self.order_line]

        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase line'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'purchase.order.line',
            'view_id': tree_view_id,
            'views': [(tree_view_id, 'tree'), (form_view_id, 'form')],
            'domain': [('id', 'in', line_ids)],
            'context': self.env.context,
            'target': 'current',
            'nodestroy': False,
            }

    # Workflow button:
    @api.multi
    def set_logistic_state_confirmed(self):
        """ Set purchase order as confirmed
        """
        # TODO for the future: Export if needed the purchase order
        # self.export_purchase_order()
        now = fields.Datetime.now()

        fullname = self.extract_purchase_order_report()
        return self.write({
            'logistic_state': 'confirmed',
            'date_planned': now,
            })

    # -------------------------------------------------------------------------
    #                                COLUMNS:
    # -------------------------------------------------------------------------
    logistic_state = fields.Selection([
        ('draft', 'Order draft'),  # Draft purchase
        ('confirmed', 'Confirmed'),  # Purchase confirmed
        ('done', 'Done'),  # All loaded in stock
        # TODO direct to confirm?
        ], 'Logistic state', default='draft',
        )


class PurchaseOrderLine(models.Model):
    """ Model name: Purchase Order Line
    """

    _inherit = 'purchase.order.line'

    @api.multi
    def unlink_for_undo(self):
        """ Launch procedure for sale order
        """
        return self.logistic_sale_id.unlink_for_undo()

    # COLUMNS:
    logistic_sale_id = fields.Many2one(
        'sale.order.line', 'Link to generator',
        help='Link generator sale order line: one customer line=one purchase',
        index=True, ondelete='set null',
        )


class StockMoveIn(models.Model):
    """ Model name: Stock Move
    """

    _inherit = 'stock.move'

    # COLUMNS:
    # Direct link to sale order line (generated from purchase order):
    logistic_refund_id = fields.Many2one(
        'sale.order.line', 'Link refund to sale',
        help='Link pick refund line to original sale line',
        index=True, ondelete='set null',
        )
    # Direct link to sale order line (generated from purchase order):
    logistic_load_id = fields.Many2one(
        'sale.order.line', 'Link load to sale',
        help='Link pick in line to original sale line (bypass purchase)',
        index=True, ondelete='set null',
        )
    # DELIVER: Pick out
    logistic_unload_id = fields.Many2one(
        'sale.order.line', 'Link unload to sale',
        help='Link pick out line to sale order',
        index=True, ondelete='set null',
        )
    # SUPPLIER ORDER: Purchase management:
    logistic_purchase_id = fields.Many2one(
        'purchase.order.line', 'Link load to purchase',
        help='Link pick in line to generate purchase line',
        index=True, ondelete='set null',
        )
    # LOAD WITHOUT SUPPLIER: Load management:
    logistic_quant_id = fields.Many2one(
        'stock.quant', 'Stock quant',
        help='Link to stock quant generated (load / unload data).',
        index=True, ondelete='cascade',
        )


class PurchaseOrderLineRelations(models.Model):
    """ Model name: Purchase Order Line
    """

    _inherit = 'purchase.order.line'

    # -------------------------------------------------------------------------
    # Function fields:
    # -------------------------------------------------------------------------
    @api.multi
    def _get_logistic_status_field(self):
        """ Manage all data for logistic situation in sale order:
        """
        _logger.warning('Update logistic qty fields now')
        for line in self:
            logistic_delivered_qty = 0.0
            for move in line.load_line_ids:
                logistic_delivered_qty += move.product_uom_qty
            # Generate data for fields:
            line.logistic_delivered_qty = logistic_delivered_qty
            line.logistic_undelivered_qty = \
                line.product_qty - logistic_delivered_qty

    # COLUMNS:
    # COMPUTED:
    logistic_delivered_qty = fields.Float(
        'Delivered qty', digits=dp.get_precision('Product Price'),
        help='Qty delivered with load documents',
        readonly=True, compute='_get_logistic_status_field', multi=True,
        store=False,
        )
    logistic_undelivered_qty = fields.Float(
        'Undelivered qty', digits=dp.get_precision('Product Price'),
        help='Qty undelivered, remain to load',
        readonly=True, compute='_get_logistic_status_field', multi=True,
        store=False,
        )
    # TODO logistic state?
    # RELATIONAL:
    load_line_ids = fields.One2many(
        'stock.move', 'logistic_purchase_id', 'Linked load to purchase',
        help='Load linked to this purchase line',
        )


class StockPicking(models.Model):
    """ Model name: Stock picking
    """

    _inherit = 'stock.picking'

    # TODO CHECK:
    @api.multi
    def refund_confirm_state_event(self):
        """ Confirm operation (will be override)
        """
        # Confirm document:
        self.workflow_ready_to_done_done_picking()
        return True

    # UTILITY:
    # TODO Not used, remove?!?
    @api.model
    def workflow_ready_to_done_all_done_picking(self):
        """ Confirm draft picking documents
        """
        pickings = self.search([
            ('state', '=', 'draft'),
            # TODO out document! (),
            ])
        return pickings.workflow_ready_to_done_done_picking()

    # BUTTON:
    @api.multi
    def workflow_ready_to_done_done_picking(self):
        """ Confirm draft picking documents
        """
        # ---------------------------------------------------------------------
        # Confirm picking for DDT and Invoice:
        # ---------------------------------------------------------------------
        ddt_ids = []  # For extra operation after
        invoice_ids = []  # For extra operation after
        for picking in self:
            partner = picking.partner_id
            order = picking.sale_order_id
            if not order:
                _logger.error('Picking without order linked')

            # Need invoice check:
            need_invoice = order.fiscal_position_id.need_invoice or \
                partner.need_invoice

            # Assign always DDT number:
            picking.assign_ddt_number()
            ddt_ids.append(picking.id)

            # Invoice procedure (check rules):
            if need_invoice:
                picking.assign_invoice_number()
                invoice_ids.append(picking.id)

            picking.write({
                'state': 'done',  # TODO needed?
                })

        # ---------------------------------------------------------------------
        # DDT extra operations: (require reload)
        # ---------------------------------------------------------------------
        # Reload picking data:
        for picking in self.browse(ddt_ids):
            sale_order = picking.sale_order_id

            # -----------------------------------------------------------------
            #                 DDT Extract:
            # -----------------------------------------------------------------
            # 1. DDT Extract procedure:
            # -----------------------------------------------------------------
            # TODO extract for Accounting
            # original_fullname = picking.extract_account_ddt_report()

        # ---------------------------------------------------------------------
        # Invoice extra operations: (require reload)
        # ---------------------------------------------------------------------
        for picking in self.browse(invoice_ids):
            # -----------------------------------------------------------------
            #                 Invoice Extract:
            # -----------------------------------------------------------------
            # 1. Invoice Extract procedure:
            # TODO extract for accounting
            # original_fullname = picking.extract_account_invoice_report()
            pass

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    sale_order_id = fields.Many2one(
        'sale.order', 'Sale order', help='Sale order generator')


class ResPartner(models.Model):
    """ Model name: Res Partner
    """

    _inherit = 'res.partner'

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    need_invoice = fields.Boolean('Always invoice')


class AccountFiscalPosition(models.Model):
    """ Model name: Account Fiscal Position
    """

    _inherit = 'account.fiscal.position'

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    need_invoice = fields.Boolean('Always invoice')


class StockQuant(models.Model):
    """ Model name: Stock quant
    """

    _inherit = 'stock.quant'

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    logistic_assigned_id = fields.Many2one(
        'sale.order.line', 'Link covered to generator',
        help='Link to sale line the assigned qty',
        index=True, ondelete='cascade',  # remove stock move when delete order
        )

    logistic_purchase_id = fields.Many2one(
        'purchase.order.line', 'Link purchase generator',
        help='Link to purchase line the assigned qty',
        index=True, ondelete='cascade',  # remove stock move when delete order
        )


class SaleOrder(models.Model):
    """ Model name: Sale Order
    """

    _inherit = 'sale.order'

    @api.model
    def write_log_chatter_message(self, message):
        """ Write message for log operation in order chatter
        """
        user = self.env['res.users'].browse(self.env.uid)
        body = _('%s [User: %s]') % (
            message,
            user.name,
        )
        self.message_post(
            body=body,
            # subtype='mt_comment', partner_ids=followers
        )

    # BUTTON EVENTS:
    # Extra operation before WF
    @api.multi
    def return_order_line_list_view(self):
        """ Return order line in a tree view
        """
        self.ensure_one()
        line_ids = self[0].order_line.mapped('id')
        return self.env['sale.order.line'].return_order_line_list_view(
            line_ids)

    # -------------------------------------------------------------------------
    #                           UTILITY:
    # -------------------------------------------------------------------------
    @api.multi
    def check_and_update_order_status(self):
        """ Verify current order line status and update header
        """
        for order in self:
            current = order.logistic_state

            # 0. Order untouchable state:
            if current in ('draft', 'ready', 'done', 'cancel'):
                # No change
                continue

            new = 'ready'  # Assume better status
            for line in order.order_line:
                line_state = line.logistic_state

                # 1. Jump cancel line:
                if line_state == 'cancel':
                    continue

                # 2. Check expense (and update wrong state):
                product = line.product_id
                if product.is_expense:
                    if line_state not in ('ready', 'done'):
                        line.logistic_state = 'ready'
                    # Jump line
                    continue

                # 3. Check pending order:
                if line_state == 'ordered':
                    new = 'pending'  # Still checking next line

                # 4. Check still in confirmed:
                if line_state == 'draft':
                    new = 'confirmed'
                    break  # No more check!

            if new != current:
                order.write({
                    'logistic_state': new,
                })
                _logger.info('Order {} change status [{} > {}]'.format(
                    order.name, current, new,
                ))


    @api.multi
    def logistic_check_and_set_ready(self):
        """ Check if all line are in ready state (excluding unused)
        """
        order_ids = []
        for order in self:
            line_state = set(order.order_line.mapped('logistic_state'))
            # if some line are in done (multi delivery):
            line_state.discard('done')
            # line_state.discard('cancel')  # TODO if partial cancel

            if tuple(line_state) == ('ready', ):  # All ready
                order.write({
                    'logistic_state': 'ready',
                    })
                order_ids.append(order.id)
        _logger.warning('Closed because ready # %s order' % len(order_ids))
        return order_ids

    @api.multi
    def logistic_check_and_set_delivering(self):
        """ Check if all line are in done state (excluding unused)
        """
        """
        TODO No more used!
        for order in self:
            line_state = set(order.order_line.mapped('logistic_state'))
            if tuple(line_state) == ('done', ):  # All done
                order.write({
                    'logistic_state': 'delivering',  # XXX ex done
                    })
        return True
        """
        return True

    # Extra operation before WF
    @api.model
    def return_order_list_view(self, order_ids):
        """ Utility for return selected order in tree view
        """
        tree_view_id = form_view_id = False
        _logger.info('Return order tree view [# %s]' % len(order_ids))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Order confirmed'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            # 'res_id': 1,
            'res_model': 'sale.order',
            'view_id': tree_view_id,
            'views': [(tree_view_id, 'tree'), (form_view_id, 'form')],
            'domain': [('id', 'in', order_ids)],
            'context': self.env.context,
            'target': 'current',  # 'new'
            'nodestroy': False,
            }

    @api.model
    def check_product_first_supplier(self):
        """ Update product without first supplier:
        """
        log_message = True  # TODO change
        line_pool = self.env['sale.order.line']
        template_pool = self.env['product.template']

        lines = line_pool.search([
            ('order_id.logistic_state', '=', 'draft'),
            ('product_id.default_supplier_id', '=', False),
            ('product_id.type', '!=', 'service'),
            ])
        _logger.info('New order: generate first supplier [# %s]' % len(lines))
        template_ids = []
        update_ids = []
        for line in lines:
            template = line.product_id.product_tmpl_id
            if template.id in template_ids:
                continue
            template_ids.append(template.id)
            try:
                update_ids.append(template.id)
                template.get_default_supplier_from_code()
            except:
                pass

        # Check updated record:
        templates = template_pool.search([
            ('id', 'in', update_ids),  # Updated lines:
            ('default_supplier_id', '=', False),  # Not updated
            ])
        res = ''
        for template in templates:
            res += '%s<br/>' % template.default_code

        if log_message and res:
            mail_pool = self.env['mail.thread']
            body = _(
                '''<div class="o_mail_notification">
                    First supplier not found:<br/>
                    %s
                    </div>''') % res

            mail_pool.sudo().message_post(
                body=body,
                message_type='notification',
                subject=_('Default supplier not found'),
                )
        return True

    # -------------------------------------------------------------------------
    #                   WORKFLOW: [LOGISTIC OPERATION TRIGGER]
    # -------------------------------------------------------------------------
    # A. Logistic phase 1: Integration with  web, pending or cancel
    # -------------------------------------------------------------------------
    @api.multi
    def workflow_draft_to_confirmed(self):
        """ Assign logistic_state to secure order
            Button event (for one order only but used in loop)
        """
        for order in self:
            _logger.info('Update order: %s' % order.name)
            order.write({
                'logistic_state': 'confirmed',
            })

            lines = order.order_line.filtered(
                lambda l: l.product_id.is_expense)

            # Update line with service:
            _logger.info(
                'Order line expense go in ready [# %s]' % len(lines))
            return lines.write({
                'logistic_state': 'ready',  # immediately ready
            })

    # -------------------------------------------------------------------------
    # B. Logistic phase 2: payment > order
    # -------------------------------------------------------------------------
    @api.model
    def workflow_payment_to_order(self):
        """ Confirm payment order
        """
        orders = self.search([
            ('logistic_state', '=', 'payment'),
            ])
        selected_ids = []
        for order in orders:
            selected_ids.append(order.id)

            # C. Became real order:
            order.logistic_state = 'order'

        # Return view:
        return self.return_order_list_view(selected_ids)

    # -------------------------------------------------------------------------
    # B. Logistic delivery phase: ready > done
    # -------------------------------------------------------------------------
    @api.model
    def workflow_ready_to_done_draft_picking(self, limit=False):
        """ Confirm payment order
        """
        now = fields.Datetime.now()

        # Pool used:
        picking_pool = self.env['stock.picking']
        move_pool = self.env['stock.move']
        company_pool = self.env['res.company']

        # ---------------------------------------------------------------------
        # Parameters:
        # ---------------------------------------------------------------------
        company = company_pool.search([])[0]
        logistic_pick_out_type = company.logistic_pick_out_type_id

        logistic_pick_out_type_id = logistic_pick_out_type.id
        location_from = logistic_pick_out_type.default_location_src_id.id
        location_to = logistic_pick_out_type.default_location_dest_id.id

        # ---------------------------------------------------------------------
        # Select order to prepare:
        # ---------------------------------------------------------------------
        # TODO limit no more used?!?
        if limit:
            _logger.warning('Limited export: %s' % limit)
            orders = self.search([
                ('logistic_state', '=', 'ready'),
                ], limit=limit)
        else:
            orders = self.search([
                ('logistic_state', '=', 'ready'),
                ])

        verbose_order = len(orders)

        # ddt_list = []
        # invoice_list = []
        picking_ids = []  # return value
        i = 0
        for order in orders:
            i += 1
            _logger.warning('Generate pick out from order: %s / %s' % (
                i, verbose_order))

            # Create picking document:
            partner = order.partner_id
            origin = _('%s [%s]') % (order.name, order.create_date[:10])

            picking = picking_pool.create({
                'sale_order_id': order.id,  # Link to order
                'partner_id': partner.id,
                'scheduled_date': now,
                'origin': origin,
                # 'move_type': 'direct',
                'picking_type_id': logistic_pick_out_type_id,
                'group_id': False,
                'location_id': location_from,
                'location_dest_id': location_to,
                # 'priority': 1,
                'state': 'draft',  # XXX To do manage done phase (for invoice)!
                })
            picking_ids.append(picking.id)

            for line in order.order_line:
                product = line.product_id

                # =============================================================
                # Speed up (check if yet delivered):
                # -------------------------------------------------------------
                # TODO check if there's another cases: service, etc.
                if line.delivered_line_ids:
                    product_qty = line.logistic_undelivered_qty
                else:
                    product_qty = line.product_uom_qty

                # Update line status:
                line.write({'logistic_state': 'done', })
                # =============================================================

                # -------------------------------------------------------------
                # Create movement (not load stock):
                # -------------------------------------------------------------
                move_pool.create({
                    'company_id': company.id,
                    'partner_id': partner.id,
                    'picking_id': picking.id,
                    'product_id': product.id,
                    'name': product.name or ' ',
                    'date': now,
                    'date_expected': now,
                    'location_id': location_from,
                    'location_dest_id': location_to,
                    'product_uom_qty': product_qty,
                    'product_uom': product.uom_id.id,
                    'state': 'done',
                    'origin': origin,
                    'price_unit': product.standard_price,

                    # Sale order line link:
                    'logistic_unload_id': line.id,

                    # group_id
                    # reference'
                    # sale_line_id
                    # procure_method,
                    # 'product_qty': select_qty,
                    })
            # TODO check if DDT / INVOICE document:

        # ---------------------------------------------------------------------
        # Confirm picking (DDT and INVOICE)
        # ---------------------------------------------------------------------
        picking_pool.browse(picking_ids).workflow_ready_to_done_done_picking()

        # ---------------------------------------------------------------------
        # Order status:
        # ---------------------------------------------------------------------
        # Change status order ready > done
        orders.logistic_check_and_set_delivering()

        # Different return value if called with limit:
        if limit:
            _logger.warning('Check other order remain: %s' % limit)
            orders = self.search([
                ('logistic_state', '=', 'ready'),
                ], limit=limit)  # keep limit instead of search all
            return orders or False
        return picking_ids

    # -------------------------------------------------------------------------
    # C. delivering > done
    # -------------------------------------------------------------------------
    @api.multi
    def wf_set_order_as_done(self):
        """ Set order as done (from delivering)
        """
        self.ensure_one()
        self.logistic_state = 'done'

    # -------------------------------------------------------------------------
    # Columns:
    # -------------------------------------------------------------------------
    logistic_picking_ids = fields.One2many(
        'stock.picking', 'sale_order_id', 'Picking')

    logistic_state = fields.Selection([
        ('draft', 'Order draft'),  # Draft, new order received
        ('confirmed', 'Order confirmed'),  # Quotation transformed in order
        ('pending', 'Pending delivery'),  # Waiting for delivery
        ('ready', 'Ready'),  # Ready for transfer
        ('done', 'Done'),  # Delivered or closed XXX manage partial delivery

        ('cancel', 'Cancel'),  # Removed order
        ], 'Logistic state', default='draft',
        )


class SaleOrderLine(models.Model):
    """ Model name: Sale Order Line
    """

    _inherit = 'sale.order.line'

    # -------------------------------------------------------------------------
    #                           UTILITY:
    # -------------------------------------------------------------------------
    @api.model
    def logistic_check_ready_order(self, sale_lines=None):
        """ Mask as done sale order with all ready lines
            if not present find all order in pending state
        """
        order_pool = self.env['sale.order']
        if sale_lines:
            # Start from sale order line:
            order_checked = []
            for line in sale_lines:
                order = line.order_id
                if order in order_checked:
                    continue
                # Check sale.order logistic status (once):
                order.logistic_check_and_set_ready()
                order_checked.append(order)
        else:
            # Check pending order:
            orders = order_pool.search([('logistic_state', '=', 'pending')])
            return orders.logistic_check_and_set_ready()  # IDs order updated
        return True

    @api.model
    def return_order_line_list_view(self, line_ids):
        """ Return order line tree view (selected)
        """
        # Gef view
        model_pool = self.env['ir.model.data']
        tree_view_id = model_pool.get_object_reference(
            'green_logistic_management',
            'view_sale_order_line_logistic_tree')[1]
        form_view_id = model_pool.get_object_reference(
            'green_logistic_management',
            'view_sale_order_line_logistic_form')[1]

        return {
            'type': 'ir.actions.act_window',
            'name': _('Updated lines'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'sale.order.line',
            'view_id': tree_view_id,
            'views': [(tree_view_id, 'tree'), (form_view_id, 'form')],
            'domain': [('id', 'in', line_ids)],
            'context': self.env.context,
            'target': 'current',
            'nodestroy': False,
            }

    # BUTTON EVENT:
    @api.multi
    def open_view_sale_order(self):
        """ Open order view
        """
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sale order'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_id': self.order_id.id,
            'res_model': 'sale.order',
            # 'view_id': view_id, # False
            'views': [(False, 'form'), (False, 'tree')],
            'domain': [('id', '=', self.order_id.id)],
            # 'context': self.env.context,
            'target': 'current',
            'nodestroy': False,
            }

    @api.multi
    def open_view_sale_order_product(self):
        """ Open subsituted product
        """
        return {
            'type': 'ir.actions.act_window',
            'name': _('Product detail'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_id': self.product_id.id,
            'res_model': 'product.product',
            # 'view_id': view_id, # False
            'views': [(False, 'form'), (False, 'tree')],
            'domain': [('id', '=', self.product_id.id)],
            # 'context': self.env.context,
            'target': 'current',
            'nodestroy': False,
            }

    # TODO Remove?:
    @api.multi
    def open_view_sale_order_original_product(self):
        """ Open original product
        """
        return {
            'type': 'ir.actions.act_window',
            'name': _('Product detail'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_id': self.origin_product_id.id,
            'res_model': 'product.product',
            # 'view_id': view_id, # False
            'views': [(False, 'form'), (False, 'tree')],
            'domain': [('id', '=', self.origin_product_id.id)],
            # 'context': self.env.context,
            'target': 'current',
            'nodestroy': False,
            }

    # -------------------------------------------------------------------------
    #                   WORKFLOW: [LOGISTIC OPERATION TRIGGER]
    # -------------------------------------------------------------------------
    # A. Assign available q.ty in stock assign a stock movement / quants
    # Workflow confirmed to pending (managed externally from file XLSX)
    # Generate assigned qty and generate purchase order
    """ # purchase_qty = line.logistic_uncovered_qty
        # Bug: Close order pending but ready (nothing passed = check all)
        closed_order_ids = self.logistic_check_ready_order()

        # Check if some order linkable to other present with same partner:
        if closed_order_ids:
            _logger.warning('Order touched: %s' % len(order_touched_ids))
            order_touched_ids = tuple(
                set(order_touched_ids) - set(closed_order_ids))
            _logger.warning('Order touched real: %s' % len(order_touched_ids))

        # Return view:
        return purchase_pool.return_purchase_order_list_view(selected_ids)
    """

    # -------------------------------------------------------------------------
    #                            COMPUTE FIELDS FUNCTION:
    # -------------------------------------------------------------------------
    @api.multi
    def _get_logistic_status_field(self):
        """ Manage all data for logistic situation in sale order:
        """
        _logger.warning('Update logistic qty fields now')
        for line in self:
            # -------------------------------------------------------------
            #                       NORMAL PRODUCT:
            # -------------------------------------------------------------
            # state = 'draft'
            product = line.product_id

            # -------------------------------------------------------------
            # OC: Ordered qty:
            # -------------------------------------------------------------
            logistic_order_qty = line.product_uom_qty

            # -------------------------------------------------------------
            # ASS: Assigned:
            # -------------------------------------------------------------
            logistic_covered_qty = 0.0
            for quant in line.assigned_line_ids:
                logistic_covered_qty -= quant.quantity
            line.logistic_covered_qty = logistic_covered_qty

            # State valuation:
            # if logistic_order_qty == logistic_covered_qty:
            #     state = 'ready' # All in stock
            # else:
            #     state = 'uncovered' # To order

            # -------------------------------------------------------------
            # PUR: Purchase (order done):
            # -------------------------------------------------------------
            logistic_purchase_qty = 0.0

            # Purchase product:
            for purchase in line.purchase_line_ids:
                logistic_purchase_qty += purchase.product_qty
            line.logistic_purchase_qty = logistic_purchase_qty

            # -------------------------------------------------------------
            # UNC: Uncovered (to purchase) [OC - ASS - PUR]:
            # -------------------------------------------------------------
            logistic_uncovered_qty = \
                logistic_order_qty - logistic_covered_qty - \
                logistic_purchase_qty
            line.logistic_uncovered_qty = logistic_uncovered_qty

            # State valuation:
            # if state != 'ready' and not logistic_uncovered_qty: # XXX
            #    state = 'ordered' # A part (or all) is order

            # -------------------------------------------------------------
            # BF: Received (loaded in stock):
            # -------------------------------------------------------------
            logistic_received_qty = 0.0
            # Purchase product:
            for move in line.load_line_ids:
                # TODO verify:
                logistic_received_qty += move.product_uom_qty
            line.logistic_received_qty = logistic_received_qty

            # -------------------------------------------------------------
            # REM: Remain to receive [OC - ASS - BF]:
            # -------------------------------------------------------------
            logistic_remain_qty = \
                logistic_order_qty - logistic_covered_qty - \
                logistic_received_qty
            line.logistic_remain_qty = logistic_remain_qty

            # State valuation:
            # if state != 'ready' and not logistic_remain_qty: # XXX
            #    state = 'ready' # All present covered or in purchase

            # -------------------------------------------------------------
            # BC: Delivered:
            # -------------------------------------------------------------
            logistic_delivered_qty = 0.0
            for move in line.delivered_line_ids:
                logistic_delivered_qty += move.product_uom_qty  # TODO verify
            line.logistic_delivered_qty = logistic_delivered_qty

            # -------------------------------------------------------------
            # UND: Undelivered (remain to pick out) [OC - BC]
            # -------------------------------------------------------------
            logistic_undelivered_qty = \
                logistic_order_qty - logistic_delivered_qty
            line.logistic_undelivered_qty = logistic_undelivered_qty

            # State valuation:
            # if not logistic_undelivered_qty: # XXX
            #    state = 'done' # All delivered to customer

            # -------------------------------------------------------------
            # Write data:
            # -------------------------------------------------------------
            # line.logistic_state = state

    # -------------------------------------------------------------------------
    #                              UNDO Management:
    # -------------------------------------------------------------------------
    @api.multi
    def line_unlink_for_undo(self):
        """ Undo without stock load
        """
        line = self

        quant_pool = self.env['stock.quant']
        undo_mode = self.env.context.get('undo_mode')
        line.ensure_one()
        product = line.product_id

        # TODO manage service?
        comment = _('Undo Line: [%s] %s x q. %s\n') % (
            line.product_id.default_code, line.name, line.product_uom_qty,
        )
        if product.type == 'service':
            raise exceptions.Warning(_('Product is service, nothing to do!'))

        # A. Nothing to do (was hidden the button but keep the same):
        if line.logistic_state in ('draft', 'cancel'):
            raise exceptions.Warning(
                _('Line is in %s state, nothing to undo!') %
                line.logistic_state)

        # D. Check stock move:
        if line.load_line_ids:
            # Parameter for stock:
            company = self.env.user.company_id
            location_id = company.logistic_location_id.id
            now = fields.Datetime.now()

            for move in line.load_line_ids:
                comment += _(
                    _('Remove delivered q. %s (%s)\n') % (
                        move.product_uom_qty,
                        _('loaded in stock') if undo_mode == 'stock' else
                        _('refund product to supplier!'),
                    ))
                if undo_mode == 'stock':
                    # Generate stock.quants for purchase q.
                    data = {
                        'company_id': company.id,
                        'in_date': now,
                        'location_id': location_id,
                        'product_id': product.id,
                        'quantity': move.product_uom_qty,
                        # TODO show that is a load for undo?
                        }
                    try:
                        quant_pool.create(data)
                    except:
                        raise exceptions.Warning(_('Cannot create quants!'))
            # Delete stock move:
            line.load_line_ids.write({
                'state': 'draft',
            })
            line.load_line_ids.unlink()

        # C. Check Purchase Order:
        if line.purchase_line_ids:
            for po_line in line.purchase_line_ids:
                po_order = po_line.order_id
                comment += _(
                    _('Remove PO line (call supplier if not delivered %s) '
                      'Q. %s [Ref. %s]!\n') % (
                          po_order.partner_id.name,
                          line.product_uom_qty,
                          po_order.name,
                      ))
            line.purchase_line_ids.unlink()

        # B. Check quants:
        if line.assigned_line_ids:
            for quant in line.assigned_line_ids:
                comment += _(
                    'Free stock qty: %s\n') % -quant.quantity
            line.assigned_line_ids.unlink()

        # TODO check if is delivered (hide undo page?)

        # Change status and log on order:
        order = line.order_id
        order.write_log_chatter_message(comment)
        order.write({
            'logistic_state': 'confirmed',
        })
        # Update line:
        return self.write({
            'logistic_state': 'draft',
            })

    @api.multi
    def line_unlink_for_stock_undo(self):
        """ Undo with stock load
        """
        # Load in stock delivered qty:

        # Normal unlink operation:
        return self.with_context(undo_mode='stock').line_unlink_for_undo()

    @api.multi
    def unlink_for_undo(self):
        """ Button for unlink document and restart from draft
        """
        model_pool = self.env['ir.model.data']
        form_view_id = model_pool.get_object_reference(
            'green_logistic_management', 'view_undo_detail_form')[1]

        return {
            'type': 'ir.actions.act_window',
            'name': _('Line for undo'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sale.order.line',
            'res_id': self.id,
            'view_id': form_view_id,
            'views': [(form_view_id, 'form')],
            'domain': [],
            'context': self.env.context,
            'target': 'new',
            'nodestroy': False,
        }

    # -------------------------------------------------------------------------
    # Function field:
    # -------------------------------------------------------------------------
    @api.multi
    def _get_undo_comment(self, ):
        """ Generate undo comment for user
        """
        line = self
        line.ensure_one()
        undo_comment = ''
        product = line.product_id

        # TODO manage service?
        self.undo_mode = 'nothing'
        if product.type == 'service':
            self.undo_comment = _(
                'Product is a service, no need to undo nothing')
            return

        # A. Nothing to do:
        if self.logistic_state in ('draft', 'cancel'):
            self.undo_comment = _(
                'Order in <b>%s</b> mode: Nothing to do' % self.logistic_state)
            return

        # B. Check quants:
        self.undo_mode = 'purchase'
        if line.assigned_line_ids:
            undo_comment += _('<br><b>Assigned to remove:</b><br/>')
            for quant in line.assigned_line_ids:
                undo_comment += _(
                        'Stock free this q.: %s!<br/>' % -quant.quantity)

        # C. Check Purchase Order:
        if line.purchase_line_ids:
            undo_comment += _('<br><b>Purchase order to undo:</b><br/>')
            for po_line in line.purchase_line_ids:
                # TODO Manage dropship undo?
                po_order = po_line.order_id
                undo_comment += _(
                        'Call supplier (if not delivered): '
                        '%s to remove q. %s [Ref. %s]!<br/>' % (
                            po_order.partner_id.name,
                            line.product_uom_qty,
                            po_order.name,
                        )
                    )

        # D. Check stock move:
        if line.load_line_ids:
            self.undo_mode = 'stock'
            undo_comment += _(
                    '<br><b>Delivered q. to remove (goes in stock?):</b><br/>')

            for move in line.load_line_ids:
                undo_comment += _(
                        'Call supplier to refund q. %s or load in stock!'
                        '<br/>' % move.product_uom_qty
                    )

        # TODO check if is delivered (hide undo page?)
        self.undo_comment = undo_comment
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    undo_comment = fields.Text(
        'Undo comment', compute=_get_undo_comment, multi=True)
    undo_mode = fields.Selection(
        selection=[
            ('nothing', 'Nothing to do'),
            ('purchase', 'Purchase (only order to undo)'),
            ('stock', 'Also stock to reload'),
        ],
        string='Undo mode', compute=_get_undo_comment, multi=True)
    product_type = fields.Selection(
        string='Type', related='product_id.type',
    )

    # RELATION MANY 2 ONE:
    # A. Assigned stock:
    assigned_line_ids = fields.One2many(
        'stock.quant', 'logistic_assigned_id', 'Assign from stock',
        help='Assign all this q. to this line (usually one2one',
        )
    # B. Purchased:
    purchase_line_ids = fields.One2many(
        'purchase.order.line', 'logistic_sale_id', 'Linked to purchase',
        help='Supplier ordered line linked to customer\'s one',
        )
    load_line_ids = fields.One2many(
        'stock.move', 'logistic_load_id', 'Linked load to sale',
        help='Loaded movement in picking in documents',
        )

    # C. Deliver:
    delivered_line_ids = fields.One2many(
        'stock.move', 'logistic_unload_id', 'Linked to delivered',
        help='Deliver movement in pick out documents',
        )

    # -------------------------------------------------------------------------
    #                               FUNCTION FIELDS:
    # -------------------------------------------------------------------------
    # Computed q.ty data:
    logistic_covered_qty = fields.Float(
        'Covered qty', digits=dp.get_precision('Product Price'),
        help='Qty covered with internal stock',
        readonly=True, compute='_get_logistic_status_field', multi=True,
        store=False,
        )
    logistic_uncovered_qty = fields.Float(
        'Uncovered qty', digits=dp.get_precision('Product Price'),
        help='Qty not covered with internal stock (so to be purchased)',
        readonly=True, compute='_get_logistic_status_field', multi=True,
        store=False,
        )
    logistic_purchase_qty = fields.Float(
        'Purchase qty', digits=dp.get_precision('Product Price'),
        help='Qty order to supplier',
        readonly=True, compute='_get_logistic_status_field', multi=True,
        store=False,
        )
    logistic_received_qty = fields.Float(
        'Received qty', digits=dp.get_precision('Product Price'),
        help='Qty received with pick in delivery',
        readonly=True, compute='_get_logistic_status_field', multi=True,
        store=False,
        )
    logistic_remain_qty = fields.Float(
        'Remain qty', digits=dp.get_precision('Product Price'),
        help='Qty remain to receive to complete ordered',
        readonly=True, compute='_get_logistic_status_field', multi=True,
        store=False,
        )
    logistic_delivered_qty = fields.Float(
        'Delivered qty', digits=dp.get_precision('Product Price'),
        help='Qty deliverer  to final customer',
        readonly=True, compute='_get_logistic_status_field', multi=True,
        store=False,
        )
    logistic_undelivered_qty = fields.Float(
        'Not delivered qty', digits=dp.get_precision('Product Price'),
        help='Qty not deliverer to final customer',
        readonly=True, compute='_get_logistic_status_field', multi=True,
        store=False,
        )

    # State (sort of workflow):
    logistic_state = fields.Selection([
        ('draft', 'Custom order'),  # Draft, customer order
        ('ordered', 'Ordered'),  # Supplier order uncovered
        ('ready', 'Ready'),  # Order to be picked out (all in stock)
        ('done', 'Done'),  # Delivered qty (order will be closed)

        ('cancel', 'Cancel'),  # Cancel only this line
        ], 'Logistic state', default='draft',
        )
