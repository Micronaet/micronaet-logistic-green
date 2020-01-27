# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class WPConnector(models.Model):
    """ Model name: Connector
    """
    _inherit = 'wp.connector'

    @api.model
    def extract_partner(self, record):
        """ Extract Partner data from order
        """
        partner_pool = self.env['res.partner']
        country_pool = self.env['res.country']

        shipping = record['shipping']
        invoice = record['billing']

        # Email:
        email = invoice['email'].lower()
        partners = partner_pool.search([
            ('email', '=', email),
            # ('connector_id', '=', connector_id),
            ])

        # Name:
        if invoice['company']:
            name = invoice['company']
        else:
            name = '%s %s' % (
                invoice['first_name'],
                invoice['last_name'],
                )

        # Country:
        country_code = invoice['country']
        countries = country_pool.search([
            ('code', '=', country_code),
            ])
        if countries:
            country_id = countries[0].id
        else:
            country_id = False

        partner_data = {
            'name': name,
            'country_id': country_id,
            'street': invoice['address_1'],
            'street2': invoice['address_2'],
            'city': invoice['city'],
            'zip': invoice['postcode'],
            'email': email,
            'phone': invoice['phone'],
            # 'property_account_position_id': 1,
            'company': True,
            }

        if partners:
            partner_id = partners[0].id
        else:
            partner_id = partner_pool.create(partner_data).id
        partner_invoice_id = partner_id

        """
        'shipping': {'company': '', 'first_name': 'Marco',
                     'country': 'IT', 'city': 'rodengo saiano',
                     'last_name': 'Borboni',
                     'address_1': 'via corneto 12', 'address_2': '',
                     'state': 'Brescia', 'postcode': '25050'},

                    'state': 'Brescia', 'phone': '3292132098',
                    'postcode': '25050'}, 'customer_note': '',
        """
        # TODO shipping:
        partner_shipping_id = partner_id
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
        params = {'per_page': 30, 'page': 0, }
        call = 'orders'
        while True:
            params['page'] += 1
            reply = wcapi.get(call, params=params)
            if reply.status_code >= 300:
                _logger.error('Error: %s' % reply.text)
                break

            records = reply.json()
            if not records:
                break
            for record in records:
                wp_id = record['id']
                number = record['number']
                sales = sale_pool.search([
                    ('connector_id', '=', connector_id),
                    ('name', '=', number),
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
                 'status': 'pending', 'created_via': 'checkout',
                 'version': '3.6.5', '_links': {'self': [{
                        'href': 'https://www.venditapianteonline.it/wp-json/wc/v3/orders/121605'}],
                        'collection': [{
                        'href': 'https://www.venditapianteonline.it/wp-json/wc/v3/orders'}]},
                 'currency': 'EUR', 'order_key': 'wc_order_J7VSecMlSkF3Z',
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
                 'total_tax': '0.00', 'number': '121605', 'coupon_lines': [],
                 'cart_hash': 'e5c2a0e6b0e51b7edfd439faff26307c',
                 'date_created': '2020-01-27T15:16:01', 'total': '40.50',
                 'refunds': [], 'tax_lines': [], 'fee_lines': [],
                 'payment_method': 'amazon_payments_advanced', 'parent_id': 0}
                """
                if sales:
                    _logger.warning('Yet present order: %s' % number)
                else:  # Create
                    order_id = sale_pool.create({
                        'wp_id': wp_id,
                        'name': number,
                        'partner_id': partner_id,
                        }).id

                    # Create line:
                    """
                    'line_items': [
                    {'id': 242518, 'product_id': 17315, 'total': '29.00',
                    'variation_id': 0, 'total_tax': '0.00', 'tax_class': '',
                    'meta_data': [],
                    'name': 'Limone caviale verde – Finger lime (Microcitrus australasica) [Pianta di 2 anni - Vaso Ø20cm]',
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
                        line_pool.create(line_data)

                    _logger.warning('Create  order: %s' % number)
            break  # XXX remove
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
    wp_status = fields.Selection(
        string='Order status', default='pending',
        selection=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('on-hold', 'On hold'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
            ('refunded', 'Refunded'),
            ('failed', 'Failed'),
            ('trash', 'Trash'),
            ])
