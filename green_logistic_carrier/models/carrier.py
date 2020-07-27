#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import os
import sys
import re
import logging
import pdb
from odoo import fields, models, api
from odoo import _
from odoo import exceptions

_logger = logging.getLogger(__name__)


class CarrierSupplier(models.Model):
    """ Model name: Parcels supplier
    """

    _name = 'carrier.supplier'
    _description = 'Parcel supplier'
    _rec_name = 'name'

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    name = fields.Char('Name')
    account_ref = fields.Char('Account ref.')
    mode = fields.Selection(
        string='Mode',
        selection=[
            ('carrier', 'Carrier'),
            ('courier', 'Courier'),
        ], required=True, default='carrier')


class CarrierSupplierMode(models.Model):
    """ Model name: Parcels supplier mode of delivery
    """

    _name = 'carrier.supplier.mode'
    _description = 'Carrier mode'
    _rec_name = 'name'

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    name = fields.Char('Name', required=True)
    account_ref = fields.Char('Account ref.')
    supplier_id = fields.Many2one('carrier.supplier', 'Carrier', required=True)


class CarrierParcelTemplate(models.Model):
    """ Model name: Parcels template
    """

    _name = 'carrier.parcel.template'
    _description = 'Parcel template'
    _rec_name = 'name'

    @api.multi
    def _get_volumetric_weight(self):
        """ Compute volumetric weight, return value
        """
        for template in self:
            template.weight = (
                template.length * template.width * template.height / 5000.0)

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    name = fields.Char('Name')
    no_label = fields.Boolean('No label')
    carrier_supplier_id = fields.Many2one('carrier.supplier', 'Carrier')
    length = fields.Float('Length', digits=(16, 2), required=True)
    width = fields.Float('Width', digits=(16, 2), required=True)
    height = fields.Float('Height', digits=(16, 2), required=True)
    dimension_uom_id = fields.Many2one('product.uom', 'Product UOM')

    weight = fields.Float(
        'Weight volumetric', digits=(16, 2), compute='_get_volumetric_weight',
        help='Volumetric weight (H x L x P / 5000)', readonly=True)
    weight_uom_id = fields.Many2one('product.uom', 'Product UOM')


class SaleOrderParcel(models.Model):
    """ Model name: Parcels for sale order
    """

    _name = 'sale.order.parcel'
    _description = 'Sale order parcel'
    _rec_name = 'weight'

    @api.multi
    def _get_volumetric_weight(self):
        """ Compute volumetric weight, return value
        """
        for line in self:
            weight = (  # Volumetric:
                line.length * line.width * line.height / 5000.0)
            real_weight = line.real_weight
            if weight > real_weight:
                used_weight = weight
            else:
                used_weight = real_weight
            line.weight = weight  # volumetric
            line.used_weight = used_weight

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    order_id = fields.Many2one('sale.order', 'Order')

    # Dimension:
    length = fields.Float('Length', digits=(16, 2), required=True)
    width = fields.Float('Width', digits=(16, 2), required=True)
    height = fields.Float('Height', digits=(16, 2), required=True)
    dimension_uom_id = fields.Many2one('product.uom', 'Product UOM')

    # Weight:
    real_weight = fields.Float(
        'Real weight', digits=(16, 2),
        )
    weight = fields.Float(
        'Volumetric weight', digits=(16, 2), compute='_get_volumetric_weight',
        readonly=True,
    )
    used_weight = fields.Float(
        'Used weight', digits=(16, 2), compute='_get_volumetric_weight',
        readonly=True,
    )
    weight_uom_id = fields.Many2one('product.uom', 'Product UOM')
    no_label = fields.Boolean('No label')


class SaleOrder(models.Model):
    """ Model name: Sale order carrier data
    """

    _inherit = 'sale.order'

    # -------------------------------------------------------------------------
    # Print action:
    # -------------------------------------------------------------------------
    # Button:
    @api.multi
    def carrier_print_label(self):
        """ Print ddt
        """
        # Will be Override:
        return True

    # Utility:
    @api.model
    def send_report_to_cups_printer(self, fullname, printer_code=False):
        """ Send report to CUPS printer
            Report file
            Printer code (see printers list)
        """
        user_pool = self.env['res.users']
        printer_pool = self.env['cups.printer']
        user = user_pool.browse(self.env.uid)

        printer = False
        if printer_code:
            printer = printer_pool.search([
                ('code', '=', printer_code)])

        if not printer:
            printer = user.default_printer_id or \
                      user.company_id.default_printer_id or False
        if not printer:
            raise exceptions.Warning('No printer with code or default setup')

        if not os.path.isfile(fullname):
            raise exceptions.Warning(
                'PDF not found: %s!' % fullname)

        # -o landscape -o fit-to-page -o media=A4
        # -o page-bottom=N -o page-left=N -o page-right=N -o page-top=N
        printer_name = printer.name
        options = printer.options or ''

        # media=Custom.10x10cm
        # -o landscape -o fit-to-page -o media=Custom.2x2

        # -o fit-to-page -o media=A6
        # -o media=Custom.4x4in
        print_command = 'lp %s -d %s "%s"' % (
            options,
            printer_name,
            fullname,
        )
        self.write_log_chatter_message(
            _('Printing %s on %s ...') % (fullname, printer_name))

        try:
            os.system(print_command)
        except:
            raise exceptions.Warning('Error print PDF invoice on %s!' % (
                printer_name))
        return True

    # Utility (TODO move in main module)
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
            # subtype='mt_comment',
            # partner_ids=followers
            )

    @api.multi
    def sanitize_text(self, text):
        """ Clean HTML tag from text
        :param text: HTML text to clean
        :return: clean text
        """
        self.ensure_one()
        tag_re = re.compile(r'<[^>]+>')
        return tag_re.sub('', text)

    @api.multi
    def set_default_carrier_description(self):
        """ Update description from sale order line
        """
        carrier_description = ''
        for line in self.order_line:
            product = line.product_id
            # TODO is_expence is not present:
            if product.type == 'service':  # or product.is_expence:
                continue
            carrier_description += '(%s X) %s ' % (
                int(line.product_uom_qty),
                (line.name or product.description_sale or product.name or
                 _('Not found')),
                )

        self.carrier_description = self.sanitize_text(
            carrier_description.strip())

    @api.multi
    def load_template_parcel(self, ):
        """ Load this template
        """
        parcel_pool = self.env['sale.order.parcel']
        template = self.carrier_parcel_template_id

        return parcel_pool.create({
            'order_id': self.id,
            'length': template.length,
            'width': template.width,
            'height': template.height,
            'no_label': template.no_label,
            })

    @api.multi
    def carrier_get_better_option(self):
        """ Get better options
        """
        # Overridable function:
        return True

    @api.multi
    def set_carrier_ok_yes(self, ):
        """ Set carrier as OK
        """
        self.write_log_chatter_message(_('Carrier data is OK'))

        # Check if order needs to be passed in ready status:
        self.carrier_ok = True

        # TODO self.logistic_check_and_set_ready()
        return True

    @api.multi
    def set_carrier_ok_no(self, ):
        """ Set carrier as UNDO
        """
        self.write_log_chatter_message(
            _('Carrier data is not OK (undo operation)'))
        self.carrier_ok = False
        return True

    @api.multi
    def _get_carrier_check_address(self):
        """ Check address for delivery
        """
        # self.ensure_one()

        # Function:
        def format_error(field):
            return '<font color="red"><b> [%s] </b></font>' % field

        def get_partner_data(partner):
            """ Embedded function to check partner data
            """
            error_check = not all((
                partner.name,
                partner.street,
                partner.zip,
                partner.city,
                partner.state_id,
                partner.country_id,
                partner.phone,  # mandatory for carrier?
                # partner.property_account_position_id,
            ))

            return (
                error_check,
                '%s %s %s - %s %s [%s %s] %s - %s<br/>' % (
                    partner.name or '',
                    partner.street or format_error(_('Address')),
                    partner.street2 or '',
                    partner.zip or format_error(_('ZIP')),
                    partner.city or format_error(_('City')),
                    partner.state_id.name or format_error(_('State')),
                    partner.country_id.name or format_error(_('Country')),
                    partner.phone or format_error(_('Phone')),
                    partner.property_account_position_id.name or format_error(
                        _('Pos. fisc.')),
                    )
            )
        for order in self:
            partner = order.partner_invoice_id
            if order.fiscal_position_id != \
                    partner.property_account_position_id:
                check_fiscal = format_error(
                    _('Fiscal pos.: Order: %s, Partner %s<br/>') % (
                        order.fiscal_position_id.name,
                        partner.property_account_position_id.name,
                        ))
            else:
                check_fiscal = ''

            mask = _('%s<b>ORD.:</b> %s\n<b>INV.:</b> %s\n<b>DELIV.:</b> %s')
            error1, partner1_text = get_partner_data(order.partner_id)
            error2, partner2_text = get_partner_data(partner)
            error3, partner3_text = get_partner_data(order.partner_shipping_id)
            order.carrier_check = mask % (
                check_fiscal,
                partner1_text,
                partner2_text,
                partner3_text,
                )
            order.carrier_check_error = error1 or error2 or error3

    @api.multi
    def _get_carrier_parcel_total(self):
        """ Return total depend on type of delivery: manual or shippy
        """
        for order in self:
            if order.carrier_shippy:
                order.real_parcel_total = len(order.parcel_ids)
            else:
                order.real_parcel_total = order.carrier_manual_parcel

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    carrier_ok = fields.Boolean(
        'Carrier OK',
        help='Carrier must be confirmed when done!')

    # Carrier:
    carrier_supplier_id = fields.Many2one(
        'carrier.supplier', 'Carrier',
        domain="[('mode', '=', 'carrier')]")
    carrier_mode_id = fields.Many2one(
        'carrier.supplier.mode', 'Carrier service')

    courier_supplier_id = fields.Many2one(
        'carrier.supplier', 'Courier',
        domain="[('mode', '=', 'courier')]")
    courier_mode_id = fields.Many2one(
        'carrier.supplier.mode', 'Courier service')

    carrier_parcel_template_id = fields.Many2one(
        'carrier.parcel.template', 'Parcel template')
    carrier_check = fields.Text(
        'Carrier check', help='Check carrier address', multi=True,
        compute='_get_carrier_check_address', widget='html')
    carrier_check_error = fields.Text(
        'Carrier check', help='Check carrier address error', multi=True,
        compute='_get_carrier_check_address', widget='html')

    carrier_description = fields.Text('Carrier description')
    carrier_note = fields.Text('Carrier note')
    carrier_stock_note = fields.Text('Stock operator note')
    carrier_total = fields.Float('Goods value', digits=(16, 2))
    carrier_ensurance = fields.Float('Ensurance', digits=(16, 2))
    carrier_cash_delivery = fields.Float('Cash on delivery', digits=(16, 2))
    carrier_pay_mode = fields.Selection([
        ('CASH', 'Cash'),
        ('CHECK', 'Check'),
        ], 'Pay mode', default='CASH')
    parcel_ids = fields.One2many('sale.order.parcel', 'order_id', 'Parcels')
    real_parcel_total = fields.Integer(
        string='Colli', compute='_get_carrier_parcel_total')
    destination_country_id = fields.Many2one(
        'res.country', 'Destination',
        related='partner_shipping_id.country_id',
    )

    # Data from Carrier:
    carrier_cost = fields.Float(
        'Cost', digits=(16, 2), help='Net shipment price')
    carrier_cost_total = fields.Float(
        'Cost', digits=(16, 2), help='Net shipment total price')
    carrier_track_id = fields.Char('Track ID', size=64)
    # TODO extra data needed!

    has_cod = fields.Boolean('Has COD')  # CODAvailable
    has_insurance = fields.Boolean('Has Insurance')  # InsuranceAvailable
    has_safe_value = fields.Boolean('Has safe value')  # MBESafeValueAvailable

    carrier_delivery_date = fields.Datetime('Delivery date', readonly=True)
    carrier_delivery_sign = fields.Datetime('Delivery sign', readonly=True)

    # 'NetShipmentTotalPrice': Decimal('6.80'),  # ??
    # 'IdSubzone': 125,
    # 'SubzoneDesc': 'Italia-Zona A',
