# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import logging
import sys
import pdb
from odoo import models, fields, api
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    """ Model name: Extend res partner
    """
    _inherit = 'res.partner'

    @api.model
    def update_partner_province(self):
        """ Setup partner province
        """
        city_pool = self.env['res.city']
        state_pool = self.env['res.country.state']

        city_name = self.city
        cities = city_pool.search([
            ('name', '=ilike', city_name),
        ])
        if not cities:
            return False
        if len(cities) > 1:
            _logger.error('More than one city!')
            return False

        province_code = cities[0].province_id.code
        states = state_pool.search([
            ('code', '=', province_code),
            ('country_id.code', '=', 'IT'),  # TODO Parameter for country
        ])
        if not states:
            return False
        self.write({
            'state_id': states[0].id,
        })


class AccountPaymentTerm(models.Model):
    """ Model name: Extend payment term
    """
    _inherit = 'account.payment.term'

    @api.model
    def get_payment_id_from_wordpress(self, code):
        """ Get or create payment from amazon code
        """
        if not code:
            return False

        payment_ids = self.search([('wp_payment_code', '=', code)])
        if payment_ids:
            return payment_ids[0].id
        record = self.create({
            'name': code.replace('_', ' ').title(),
            'wp_payment_code': code,
        })
        return record.id

    wp_payment_code = fields.Char(
        string='Wordpress payment code',
        size=25)


class WPConnector(models.Model):
    """ Model name: Connector
    """
    _inherit = 'wp.connector'

    # Columns:
    demo_partner = fields.Boolean(
        'Demo customer',
        help='Create demo customer in carriage operations')
    manage_delivery = fields.Boolean(
        'Manage delivery',
        help='The new order will be marked for manage delivery in ODOO')
    manage_web_status = fields.Boolean(
        'Manage web status',
        help='Will update wordpress order status during order operation')
    order_start_page = fields.Integer(
        'Order start page', default=1,
        help='Start reading orders from page',
    )
    order_stop_page = fields.Integer(
        'Order stop page', default=100,
        help='Stop reading orders from page (0 means unlimited)',
    )
    order_limit = fields.Integer(
        'Order limit', default=50,
        help='Limit of record page for order',
    )

    @api.model
    def extract_partner(self, record):
        """ Extract Partner data from order
        """

        def get_name(partner_block):
            """ Extract name from record
                partner_block: wordpress partner block
            """
            customer = '%s %s' % (
                    partner_block['first_name'],
                    partner_block['last_name'],
                    )
            if partner_block['company']:
                return '%s%s%s' % (
                    partner_block['company'],
                    ' - ' if customer else '',
                    customer,
                )
            else:
                return customer

        def get_country_id(partner_block):
            """ Extract name from record
                record: wordpress partner block
            """
            country_pool = self.env['res.country']
            country_code = partner_block['country']
            countries = country_pool.search([
                ('code', '=', country_code),
                ])
            if countries:
                return countries[0].id
            else:
                return False

        '''
        def get_state_id(partner_block):
            """ Extract name from record
                record: wordpress partner block
            """
            city_pool = self.env['res.city']
            state_pool = self.env['res.country.state']

            city_name = partner_block['city']
            cities = city_pool.search([
                ('name', '=ilike', city_name),
                ])
            if not cities:
                return False
            if len(cities) > 1:
                _logger.error('More than one city!')
                return False

            province_code = cities[0].province_id.code
            states = state_pool.search([
                ('code', '=', province_code),
                ('country_id.code', '=', 'IT'),  # TODO Parameter for country
            ])

            if not states:
                return False

            return states[0].id
        '''

        def same_partner_check(odoo_data):
            """ Check if same partner
            """
            # TODO check if correct (or some extra fields in billing):
            if odoo_data['billing'] == odoo_data['shipping']:
                return True
            else:
                return False

        # ---------------------------------------------------------------------
        # Procedure:
        # ---------------------------------------------------------------------
        # Pool used:
        partner_pool = self.env['res.partner']

        # ---------------------------------------------------------------------
        # A. Billing partner:
        # ---------------------------------------------------------------------
        odoo_data = {}
        for mode in ('billing', 'shipping'):
            partner_block = record[mode]

            # This records are generated with all fields to check same:
            odoo_data[mode] = {
                'is_company': True,
                'customer': True,
                'name': get_name(partner_block),
                'country_id': get_country_id(partner_block),
                # 'state_id': get_state_id(partner_block),
                'street': partner_block['address_1'],
                'street2': partner_block['address_2'],
                'city': partner_block['city'],
                'zip': partner_block['postcode'],
                # TODO 'property_account_position_id': 1,
                # TODO state_id

                # Billing only (keep also in shipping):
                'email': record['billing']['email'].lower(),
                'phone': record['billing']['phone'],
                }
        is_same = same_partner_check(odoo_data)

        # Email is the key:
        name = odoo_data['billing']['name']
        email = odoo_data['billing']['email']
        partners = partner_pool.search([
            ('email', '=', email),
            ('name', '=ilike', name),
            ])

        if partners:
            partner_invoice = partners[0]
        else:
            partner_invoice = partner_pool.create(odoo_data['billing'])
        if not partner_invoice.state_id:
            partner_invoice.update_partner_province()
        partner_invoice_id = partner_invoice.id

        # ---------------------------------------------------------------------
        # B. Shipping partner:
        # ---------------------------------------------------------------------
        partner_id = partner_invoice_id  # TODO for now is same!

        # Add Extra data for link partner:
        odoo_data['shipping'].update({
            'parent_id': partner_id,
            'type': 'delivery',
            })

        del(odoo_data['shipping']['email'])  # Removed no more used

        # Destination:
        if is_same:
            partner_shipping_id = partner_invoice_id
        else:
            #  Not same partner
            destinations = partner_pool.search([
                ('parent_id', '=', partner_id),
                ('city', '=', odoo_data['shipping']['city']),
                ('street', '=', odoo_data['shipping']['street']),
                ('street2', '=', odoo_data['shipping']['street2']),
                ('zip', '=', odoo_data['shipping']['zip']),
                ('country_id', '=', odoo_data['shipping']['country_id']),
                # TODO add other check:
                # ('state_id.name', '=', odoo_data['shipping']['state']),
                ])

            if destinations:
                # Not updated for now:
                # destinations.write(odoo_data['shipping'])
                partner_shipping = destinations[0]
            else:
                partner_shipping = partner_pool.create(
                    odoo_data['shipping'])

            if not partner_shipping.state_id:
                partner_shipping.update_partner_province()
            partner_shipping_id = partner_shipping.id

        # For now no alternative invoice partner:
        return partner_id, partner_invoice_id, partner_shipping_id

    # -------------------------------------------------------------------------
    #                           BUTTON EVENTS:
    # -------------------------------------------------------------------------
    @api.multi
    def button_load_order(self):
        """ Load order from Wordpress
        """
        # Pool used:
        product_pool = self.env['product.product']
        sale_pool = self.env['sale.order']
        line_pool = self.env['sale.order.line']
        payment_pool = self.env['account.payment.term']

        wcapi = self.get_connector()

        # ---------------------------------------------------------------------
        # Parameters:
        # ---------------------------------------------------------------------
        # A. ODOO Parameters:
        manage_delivery = self.manage_delivery
        connector_id = self.id
        start_page = self.order_start_page

        # WP params:
        params = {
            'per_page': self.order_limit,
            'page': start_page,
        }

        # B. External parameters (update):
        extend_params = self.env.context.get('extend_params')
        if extend_params:
            _logger.warning(
                'Extending params for call: %s' % (extend_params, ))
            params.update(extend_params)

        # C. Both check:
        end_page = self.env.context.get('end_page', self.order_stop_page)

        update_order_reached = []
        while True:
            # Log:
            _logger.info('Reading orders from %s [Record %s-%s]' % (
                self.name,
                params['per_page'] * (params['page'] - 1),
                params['per_page'] * params['page'],
                ))
            try:
                reply = wcapi.get('orders', params=params)
            except:
                _logger.error('Error calling WP: \n%s' % (sys.exc_info(), ))
                continue
            params['page'] += 1
            if not reply.ok:
                _logger.error('Error: %s' % reply.text)
                break

            records = reply.json()
            if not records:
                break

            for record in records:
                wp_id = record['id']
                number = record['number']
                shipping_total = float(record['shipping_total'])
                total = float(record['total'])
                total_tax = float(record['total_tax'])
                currency = record['currency']
                status = record['status']
                payment_method = record['payment_method']
                prices_include_tax = record['prices_include_tax']
                customer_note = record['customer_note']

                # Date:
                date_created = record['date_created']
                date_modified = record['date_modified']
                date_completed = record['date_completed']

                payment_term_id = payment_pool.get_payment_id_from_wordpress(
                    payment_method)
                sales = sale_pool.search([
                    # Wordpress Key:
                    ('connector_id', '=', connector_id),
                    ('wp_id', '=', wp_id),
                    ])

                partner_id, partner_invoice_id, partner_shipping_id = \
                    self.extract_partner(record)

                """
                {                 
                 'shipping_lines': [
                     {'id': 242519, 'method_id': 'table_rate_shipping',
                      'taxes': [], 'total': '11.50',
                      'method_title': 'Corriere espresso', 'meta_data': [],
                      'total_tax': '0.00', 'instance_id': '0'}],
                 'created_via': 'checkout',
                 'currency': 'EUR', 'order_key': 'wc_order_J7VSecMlSkF3Z',
                 'shipping_total': '11.50', 'date_completed': None,
                 'cart_tax': '0.00',
                 'customer_user_agent': 'Mozilla/5.0 (Windows NT 10.0; ...
                 'discount_tax': '0.00', 'date_paid': None,
                 'shipping_tax': '0.00',
                 'prices_include_tax': True,
                 'customer_ip_address': '5.89.6.17',
                 'id': 121605, 'customer_id': 0,
                 'payment_method_title': 'Paga con il tuo account Amazon',
                 'transaction_id': 'P02-5649172-2284784',
                 'discount_total': '0.00', 'total_tax': '0.00', 
                 'number': '121605', 'coupon_lines': [],
                 'cart_hash': 'e5c2a0e6b0e51b7edfd439faff26307c',
                 'total': '40.50',
                 'refunds': [], 'tax_lines': [], 'fee_lines': [],
                 'payment_method': 'amazon_payments_advanced', 
                 }
                """

                order_data = {  # Update mode:
                    'wp_status': status,
                    'wp_date_created': date_created,
                    'wp_date_modified': date_modified,
                    'wp_date_completed': date_completed,
                    'wp_customer_note': customer_note,
                    'payment_term_id': payment_term_id,
                    }
                created = False
                if sales:
                    _logger.warning(
                        'Yet present order: %s (update minimal)' % number)
                    # TODO Update (or state update only)
                    sales.write(order_data)
                    order = sales[0]
                else:  # Create mode
                    order_data.update({
                        'manage_delivery': manage_delivery,
                        'connector_id': connector_id,
                        'wp_id': wp_id,
                        'name': number,
                        'date_order': date_created,
                        'partner_id': partner_id,
                        'partner_shipping_id': partner_shipping_id,
                        'partner_invoice_id': partner_invoice_id,
                    })
                    created = True
                    try:
                        order = sale_pool.create(order_data)
                    except:
                        _logger.error('Problem create: %s order [%s]\n%s' % (
                            number, order_data, sys.exc_info()))
                        continue

                    order_id = order.id
                    # TODO <<<< back block of 4 char
                    # Create line:
                    """
                    'line_items': [
                    {'id': 242518, 'product_id': 17315, 'total': '29.00',
                    'variation_id': 0, 'total_tax': '0.00', 'tax_class': '',
                    'meta_data': [],
                    'name': 'Limone caviale verde – Finger lime',
                    'price': 29, 'subtotal': '29.00', 'taxes': [],
                    'quantity': 1, 'subtotal_tax': '0.00',
                    'sku': '01366-29'}], 
                    'meta_data': [
                        {'id': 3759624, 'key': 'is_vat_exempt', 'value': 'no'},
                        {'id': 3759628, 
                            'key': '_shipping_phone', 'value': '3292132098'},
                        {'id': 3759642, 
                            'key': 'amazon_reference_id', 
                            'value': 'P02-5649172-2284784'},
                        {'id': 3759644, 
                            'key': 'amazon_order_language', 'value': 'it-IT'},
                        {'id': 3759645, 
                            'key': 'is_vat_exempt', 'value': 'no'}
                        ],
                    """
                    # Check order if present:
                    shipping_line = False
                    origin_line_found = {}
                    """
                    TODO for now not update yet present order line:
                    if not created:  # Save current list of line
                        #  Check previous line present:
                        for origin_line in order.order_line:
                            product = origin_line.product_id
                            if product.default_code == 'shipping':
                                shipping_line = origin_line
                            else:  # Product line:
                                origin_line_found[origin_line.wp_line_id] = \
                                        origin_line
                    """
                    for line in record['line_items']:
                        wp_line_id = line['id']
                        sku = line['sku']
                        price = line['price']
                        qty = line['quantity']
                        name = line['name']
                        products = product_pool.search([
                            ('default_code', '=', sku),
                            ])

                        # Check product:
                        if products:
                            product_id = products[0].id
                        else:  # Create product not present!:
                            _logger.warning(
                                'Create product not present: %s' % sku)
                            product_id = product_pool.create({
                                'name': name,
                                'default_code': sku,
                                }).id

                        line_data = {
                            'order_id': order_id,
                            'wp_id': wp_line_id,
                            'product_id': product_id,
                            'name': name,
                            'product_uom_qty': qty,
                            'price_unit': price,
                            }

                        # Check if line is present: TODO not used for now
                        if wp_line_id in origin_line_found:
                            line.write(line_data)
                            del(origin_line_found[wp_line_id])
                        else:
                            line_pool.create(line_data)

                    # TODO not used for now
                    """
                    if origin_line_found:
                        # Sale order line to remove:
                        # TODO remove
                        _logger.warning('Remove line no more present')
                        origin_line_found.unlink()
                    """

                    # ---------------------------------------------------------
                    # Shipping product line:
                    # ---------------------------------------------------------
                    if shipping_total:
                        if shipping_line:
                            # A. Update shipping line total:
                            shipping_line.write({
                                'price_unit': shipping_total,
                                })
                        else:  # Search / Create shipping product:
                            products = product_pool.search([
                                ('default_code', '=', 'shipping'),
                                ])
                            if products:
                                shipping_product = products[0]
                            else:
                                _logger.info('Create shipping product')
                                shipping_product = product_pool.create({
                                    'default_code': 'shipping',
                                    'name': _('Shipping cost'),
                                    'type': 'service',
                                    })

                            # B. Create shipping line:
                            line_pool.create({
                                'order_id': order_id,
                                'product_id': shipping_product.id,
                                'name': shipping_product.name,
                                'product_uom_qty': 1,
                                'price_unit': shipping_total,
                                })
                    _logger.info('Create  order: %s' % number)

                    # After updating the web site:
                    if status == 'processing':
                        update_order_reached.append(order)

            # Block end limit check:
            if end_page and params['page'] >= end_page + 1:
                break

        # Update order from processing to sent-to-gsped (if regular import):
        if not manage_delivery:
            _logger.warning('Order are managed from Wordpress')
            return True

        # ---------------------------------------------------------------------
        #                      Check if need update status:
        # ---------------------------------------------------------------------
        _logger.warning('Orders are managed from ODOO')
        if self.manage_web_status:  # Connector manage status:
            for order in update_order_reached:
                order.wp_wf_set_to_state('sent-to-gsped')
            _logger.warning(
                'Updated Wordpress status # %s' % len(update_order_reached))
        return True


class SaleOrderLine(models.Model):
    """ Model name: Sale order line
    """
    _inherit = 'sale.order.line'

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    wp_id = fields.Integer(string='Wp ID')


class SaleOrder(models.Model):
    """ Model name: Sale order
    """
    _inherit = 'sale.order'

    # -------------------------------------------------------------------------
    # WP Workflow button:
    # -------------------------------------------------------------------------
    # Utility:
    @api.multi
    def wp_wf_refresh_status(self):
        """ Refresh order status
        """
        connector = False  # Updated in loop
        error = []
        for order in self:
            try:
                if self.connector_id != connector:
                    connector = self.connector_id
                    wcapi = connector.get_connector()
                reply = wcapi.get('orders/%s' % order.wp_id)
                if reply.ok:
                    json_reply = reply.json()
                    wp_status = json_reply['status']
                    if wp_status != order.wp_status:  # Update if different
                        order.write({'wp_status': wp_status})
                    else:
                        _logger.warning(
                            'No need to update order: %s' % order.name)
                else:
                    _logger.error('Order: %s error in update call' % reply)
            except:
                error.append(order)
                _logger.error('Order: %s not updated' % order.name)
        return True

    @api.multi
    def wp_wf_set_to_state_batch(self, state):
        """ Batch update all orders
        """
        data = {
            'update': [],
        }
        error = []
        connector = False
        for order in self:
            if not connector:
                connector = order.connector_id
                wcapi = connector.get_connector()
            try:
                reply = wcapi.put('orders/batch', data)
                if reply.ok:
                    # reply_json = reply.json()
                    # for item in reply_json:

                    order.write({'wp_status': state})
                else:
                    _logger.error('Order: %s error in update call' % reply)
            except:
                error.append(order)
                _logger.error('Order: %s not updated' % order.name)

    @api.multi
    def wp_wf_set_to_state(self, state):
        """ Update status to state passed (utility called from WF button)
        """
        user = self.env['res.users'].browse(self.env.uid)
        data = {
            'status': state,
        }
        error = []
        previous_connector = False
        for order in self:
            connector = order.connector_id
            if connector != previous_connector:
                previous_connector = connector
                wcapi = connector.get_connector()
            try:
                reply = wcapi.put('orders/%s' % order.wp_id, data)
                if reply.ok:
                    order.write({'wp_status': state})
                    self.message_post(
                        body=_('Change Wordpress status %s [User: %s]') % (
                            state,
                            user.name,
                        ))
                else:
                    message = 'Order: %s error in update call' % reply
                    self.message_post(body=message)
                    _logger.error(message)
            except:
                error.append(order)
                message = 'Order: %s not updated' % order.name
                _logger.error(message)
                self.message_post(body=message)

    @api.multi
    def wp_wf_processing(self):
        """ Update status to processing, real state is sent to sped
        """
        return self.wp_wf_set_to_state('sent-to-gsped')

    @api.multi
    def wp_wf_completed(self):
        """ Update status to completed
        """
        # TODO change event name (complete is wrong state)
        self.wp_wf_set_to_state('delivered')
        return True

    @api.multi
    def wp_wf_cancelled(self):
        """ Update status to cancelled
        """
        self.wp_wf_set_to_state('cancelled')
        return True

    @api.multi
    def wp_wf_refunded(self):
        """ Update status to refunded
        """
        return self.wp_wf_set_to_state('refunded')

    @api.multi
    def wp_wf_failed(self):
        """ Update status to failed
        """
        return self.wp_wf_set_to_state('failed')

    @api.multi
    def shipments_get_tracking_result(self):
        """ Future function to check delivery
        """
        return True

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    wp_id = fields.Integer('Wp ID')
    manage_delivery = fields.Boolean(
        'Manage delivery', help='This order manage delivery in ODOO')
    connector_id = fields.Many2one('wp.connector', 'Connector')
    soap_last_error = fields.Text('SOAP Last Error')
    wp_date_created = fields.Datetime('Wp date created')
    wp_date_modified = fields.Datetime('Wp date modified')
    wp_date_completed = fields.Datetime('Wp date completed')
    wp_customer_note = fields.Text('WP customer note')
    wp_status = fields.Selection(
        string='Order status', default='pending',
        selection=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('on-hold', 'On hold'),
            ('completed', 'Completed'),
            ('delivered', 'Delivered'),
            ('cancelled', 'Cancelled'),
            ('refunded', 'Refunded'),
            ('failed', 'Failed'),
            # ('trash', 'Trash'),
            ('sent-to-gsped', 'Sent to GSped')
            ])
