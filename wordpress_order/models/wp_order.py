# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import logging
import sys
from odoo import models, fields, api
from openerp.tools.translate import _

_logger = logging.getLogger(__name__)


class WPConnector(models.Model):
    """ Model name: Connector
    """
    _inherit = 'wp.connector'

    @api.model
    def extract_partner(self, record):
        """ Extract Partner data from order
        """

        def get_name(partner_block):
            """ Extract name from record
                partner_block: wordpress partner block
            """
            if partner_block['company']:
                return partner_block['company']
            else:
                return '%s %s' % (
                    partner_block['first_name'],
                    partner_block['last_name'],
                    )

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
        email = odoo_data['billing']['email']
        partners = partner_pool.search([
            ('email', '=', email),
            ])

        if partners:
            partner_invoice_id = partners[0].id
        else:
            partner_invoice_id = partner_pool.create(odoo_data['billing']).id

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
                #('state_id.name', '=', odoo_data['shipping']['state']),
                ])

            if destinations:
                # Not updated for now:
                # destinations.write(odoo_data['shipping'])
                partner_shipping_id = destinations[0].id
            else:
                partner_shipping_id = partner_pool.create(
                    odoo_data['shipping']).id

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

        wcapi = self.get_connector()

        connector_id = self.id
        start_page = 1
        end_page = 50
        params = {'per_page': 50, 'page': start_page}

        while True:
            _logger.info('Reading orders from %s [Record %s-%s]' % (
                self.name,
                params['per_page'] * (params['page'] - 1),
                params['per_page'] * params['page'],
                ))
            reply = wcapi.get('orders', params=params)
            params['page'] += 1
            if not reply.ok:  # status_code >= 300:
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

                # Date:
                date_created = record['date_created']
                date_modified = record['date_modified']
                date_completed = record['date_completed']

                sales = sale_pool.search([
                    # Wordpress Key:
                    ('connector_id', '=', connector_id),
                    ('wp_id', '=', wp_id),
                    ])

                partner_id, partner_invoice_id, partner_shipping_id = \
                    self.extract_partner(record)

                """
                {'date_completed_gmt': None,
                 'date_modified': '2020-01-27T15:16:01',
                 'shipping_lines': [
                     {'id': 242519, 'method_id': 'table_rate_shipping',
                      'taxes': [], 'total': '11.50',
                      'method_title': 'Corriere espresso', 'meta_data': [],
                      'total_tax': '0.00', 'instance_id': '0'}],
                 'status': 'pending', 
                 'created_via': 'checkout',
                 'version': '3.6.5', '_links': {'self': [{
                        'href': 'https://www.venditapianteonline.it/wp-json/wc/v3/orders/121605'}],
                        'collection': [{
                        'href': 'https://www.venditapianteonline.it/wp-json/wc/v3/orders'}]},
                 'currency': 'EUR', 
                 'order_key': 'wc_order_J7VSecMlSkF3Z',
                 'shipping_total': '11.50', 'date_completed': None,
                 'cart_tax': '0.00',
                 'customer_user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.102 Safari/537.36 Edge/18.18362',
                 'discount_tax': '0.00', 'date_paid': None,
                 'shipping_tax': '0.00',
                 'prices_include_tax': True, 'date_paid_gmt': None,
                 'customer_ip_address': '5.89.6.17',
                 'date_created_gmt': '2020-01-27T14:16:01', 'id': 121605,
                 'customer_id': 0, 'date_modified_gmt': '2020-01-27T14:16:01',
                 'payment_method_title': 'Paga con il tuo account Amazon',
                 'transaction_id': 'P02-5649172-2284784',
                 'discount_total': '0.00', 
                 'total_tax': '0.00', 
                 'number': '121605', 
                 'coupon_lines': [],
                 'cart_hash': 'e5c2a0e6b0e51b7edfd439faff26307c',
                 'date_created': '2020-01-27T15:16:01', 
                 'total': '40.50',
                 'refunds': [], 'tax_lines': [], 'fee_lines': [],
                 'payment_method': 'amazon_payments_advanced', 
                 }
                """
                order_data = {
                    'connector_id': connector_id,
                    'wp_id': wp_id,
                    'name': number,
                    'date_order': date_created,
                    'partner_id': partner_id,
                    'partner_shipping_id': partner_shipping_id,
                    'partner_invoice_id': partner_invoice_id,
                    'wp_status': status,
                    'wp_date_created': date_created,
                    'wp_date_modified': date_modified,
                    'wp_date_completed': date_completed,
                    }
                created = False
                if sales:
                    _logger.warning(
                        'Yet present order: %s (not updated)' % number)
                    # TODO Update (or state update only)
                    # sales.write(order_data)
                    order = sales[0]
                else:  # Create
                    created = True
                    try:
                        order = sale_pool.create(order_data)
                    except:
                        _logger.error('Problem create: %s order [%s]\n%s' % (
                            number, order_data, sys.exc_info()))
                        continue
                    order_id = order.id

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
                        {'id': 3759628, 'key': '_shipping_phone', 'value': '3292132098'},
                        {'id': 3759642, 'key': 'amazon_reference_id', 'value': 'P02-5649172-2284784'},
                        {'id': 3759644, 'key': 'amazon_order_language', 'value': 'it-IT'},
                        {'id': 3759645, 'key': 'is_vat_exempt', 'value': 'no'}
                        ],
                    """
                    # Check order if present:
                    shipping_line = False
                    origin_line_found = {}
                    if not created:
                        #  Check previous line present:
                        for origin_line in order.order_line:
                            product = origin_line.product_id
                            if product.default_code == 'shipping':
                                shipping_line = origin_line
                            else:  # Product line:
                                origin_line_found[origin_line.wp_line_id] = \
                                        origin_line

                    for line in record['line_items']:
                        wp_line_id = line['id']
                        sku = line['sku']
                        price = line['price']
                        qty = line['quantity']
                        name = line['name']
                        products = product_pool.search([
                            ('default_code', '=', sku),
                            ])
                        if products:
                            product_id = products[0].id
                        else:
                            # Create product not present!:
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

                        # Check if line is present:
                        if wp_line_id in origin_line_found:
                            line.write(line_data)
                            del(origin_line_found[wp_line_id])
                        else:
                            line_pool.create(line_data)

                    if origin_line_found:
                        # Sale order line to remove:
                        # TODO remove
                        _logger.warning('Remove line no more present')
                        origin_line_found.unlink()

                    # ---------------------------------------------------------
                    # Shipping product line:
                    # ---------------------------------------------------------
                    if shipping_total:
                        if shipping_line:
                            # A. Update shipping line total:
                            shipping_line.write({
                                'price_unit': shipping_total,
                                })
                        else:
                            # -------------------------------------------------
                            # Search shipping product:
                            # -------------------------------------------------
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
            if end_page and params['page'] >= end_page:
                 break  # TODO remove (for testing)
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
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    wp_id = fields.Integer(string='Wp ID')
    connector_id = fields.Many2one(
        comodel_name='wp.connector',
        string='Connector')
    wp_date_created = fields.Datetime(string='Wp date created')
    wp_date_modified = fields.Datetime(string='Wp date modified')
    wp_date_completed = fields.Datetime(string='Wp date completed')

    wp_status = fields.Selection(
        string='Order status', default='pending',
        selection=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('on-hold', 'On hold'),
            ('delivered', 'Delivered'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
            ('refunded', 'Refunded'),
            ('failed', 'Failed'),
            ('trash', 'Trash'),
            ('sent-to-gsped', 'Sent to GSped')
            ])
