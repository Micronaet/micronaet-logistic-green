# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import os
import sys
import io
import xlsxwriter
import pdb
import logging
import subprocess
import base64
import shutil
import zeep
from odoo import models, fields, api
from odoo import exceptions
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class CarrierConnectionSoap(models.Model):
    """ Model name: Carrier Soap Connection
    """
    _name = 'carrier.connection.soap'
    _description = 'Carrier connection SOAP'
    _order = 'name'

    # -------------------------------------------------------------------------
    #                                  METHODS:
    # -------------------------------------------------------------------------
    # Connection:
    @api.multi
    def get_connection(self):
        """ Get Service connection to make calls:
        """
        self.ensure_one()

        client = zeep.Client(self.wsdl_root)
        return client.service

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    name = fields.Char('Name', size=64, required=True)
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True)

    wsdl_root = fields.Char(
        'WSDL root', size=140, required=True,
        default='https://www.onlinembe.it/wsdl/OnlineMbeSOAP.wsdl')
    # namespace
    username = fields.Char('Username', size=64, required=True)
    passphrase = fields.Char('Passphrase', size=64, required=True)

    system = fields.Char(
        'System', size=10, required=True, default='IT',
        help='Old way to manage marketplace country')
    internal_reference = fields.Char(
        'Internal reference', size=10, default='MI030-lg',
        help='Code assigned to every call and returned, used as ID')
    customer_id = fields.Integer(
        'Customer ID', required=True, help='Code found in web management')
    store_id = fields.Char(
        'Store ID', size=4, required=True, help='Code used for some calls')

    # Not used for now:
    sam_id = fields.Char('SAM ID', size=4, help='')
    department_id = fields.Char('Department ID', size=4, help='')


class CarrierSupplier(models.Model):
    """ Model name: Parcels supplier
    """

    _inherit = 'carrier.supplier'

    soap_connection_id = fields.Many2one(
        comodel_name='carrier.connection.soap',
        string='SOAP Connection')


class SaleOrder(models.Model):
    """ Model name: Sale order
    """
    _inherit = 'sale.order'

    # -------------------------------------------------------------------------
    #                            UTILITY:
    # -------------------------------------------------------------------------
    @api.multi
    def carrier_print_label(self):
        """ Print label via CUPS
        """
        # TODO mode = 'label_01'
        path = self.get_folder_root_path('tracking')
        label_path = self.get_folder_root_path('label', root_path=path)
        filename = '%s.1.PDF' % self.id
        fullname = os.path.join(label_path, filename)
        return self.send_report_to_cups_printer(fullname)

    @api.multi
    def order_form_detail(self):
        """
        """
        # model_pool = self.env['ir.model.data']
        # tree_view_id = model_pool.get_object_reference(
        #    'logistic_management', 'view_sale_order_line_logistic_tree')[1]
        # form_view_id = model_pool.get_object_reference(
        #    'carrier_mbe_soap', 'view_sale_order_line_logistic_form')[1]
        tree_view_id = form_view_id = False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Order details'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_id': self.id,
            'res_model': 'sale.order',
            'view_id': tree_view_id,
            'views': [(form_view_id, 'form'), (tree_view_id, 'tree')],
            'domain': [],
            'context': self.env.context,
            'target': 'current',
            'nodestroy': False,
        }

    # Check utility:
    @api.multi
    def check_reply_status(self, reply):
        """ Get Service connection to make calls:
            :return Error text if present
        """
        self.ensure_one()
        # Status token (OK, ERROR)

        error = ''
        if reply['Status'] == 'ERROR':
            # Error[{'id', 'Description'}]
            error = '%s' % (reply['Errors'], )  # TODO better!
            _logger.error(error)
        return error

    # Format Utility:
    def check_size(self, text, size, dotted=False):
        """ Clean text for SOAP call
        """
        text = text or ''
        if dotted:
            if len(text) > (size - 3):
                return '%s...' % text[:size - 3]
        else:
            if len(text) > size:
                return text[:size]
        return text

    # Create block utility (for container)
    @api.multi
    def get_request_container(
            self, credentials=True, internal=True, customer=True, system=False,
            store=False):
        """ Get Service connection to make calls, parameters are passed as
            boolean switch:
        """
        self.ensure_one()
        connection = self.carrier_supplier_id.soap_connection_id
        data = {}
        if credentials:
            data['Credentials'] = {
                'Username': connection.username,
                'Passphrase': connection.passphrase,
            }
        if internal:
            data['InternalReferenceID'] = connection.internal_reference
        if customer:
            data['CustomerID'] = connection.customer_id
        if system:
            if type(system) == bool:
                field_name = 'System'
            else:
                field_name = 'SystemType'
            data[field_name] = connection.system
        if store:
            data['StoreID'] = connection.store_id
        return data

    @api.multi
    def get_recipient_container(self):
        """ Return dict for Partner container
        """
        order = self
        partner = order.partner_shipping_id or order.partner_id
        return {
            'Name': 'TEST' or partner.name,  # 35
            'CompanyName': 'TEST',  # 35
            'Nickname': 'TEST',  # 100
            'Address': partner.street or '',  # 100
            'Address2': partner.street2 or '',  # 35
            'Address3': '',  # 35
            'Phone': partner.phone or '',  # 50
            'ZipCode': partner.zip or '',  # 12
            'City': partner.city or '',  # 50
            'State': partner.state_id.code or '',  # 2
            'Country': partner.country_id.code or '',  # 2
            'Email': partner.email or '',  # 75
            'SubzoneId': '',  # integer
            'SubzoneDesc': '',
        }

    @api.multi
    def get_shipment_container(self):
        """ Return dict for order shipment
        """
        order = self
        # TODO crossed field (bad solution)
        note = eval('order.carrier_note or order.wp_customer_note')
        data = {
            'ShipperType': order.shipper_type,
            'Description': order.check_size(
                order.carrier_description, 100, dotted=True),
            'MethodPayment': order.carrier_pay_mode,
            'Service': order.carrier_mode_id.account_ref or '',
            'Courier': order.courier_supplier_id.account_ref or '',
            'CourierService': order.courier_mode_id.account_ref or '',
            'PackageType': order.package_type,
            'Referring': order.name,  # * 30
            'InternalNotes': 'ORDINE DA CANCELLARE',  # TODO * string
            'Notes': note,
            'LabelFormat': 'NEW',  # * token (OLD, NEW)
            'Items': order.get_items_parcel_block(),

            # TODO Option not used for now:
            'Insurance': False,  # boolean
            'COD': False,  # boolean
            # 'CODValue': '',  # * decimal
            # 'InsuranceValue': '',  # * decimal
            # 'CourierAccount': '',  # * string
            # 'Value': '',  # * decimal
            # 'ShipmentCurrency': '',  # * string
            # 'SaturdayDelivery': '',  # * boolean
            # 'SignatureRequired': '',  # * boolean
            # 'ShipmentOrigin': '',  # * string
            # 'ShipmentSource': '',  # * int
            # 'MBESafeValue': '',  # * boolean
            # 'MBESafeValueValue': '',  # * decimal
            # 'MBESafeValueDescription': '',  # * string 100
        }

        # Products* ProductsType
        #    Product ProductType
        #        SKUCode string
        #        Description string
        #        Quantity decimal

        # ProformaInvoice* ProformaInvoiceType
        #        ProformaDetail ProformaDetailType
        #            Amount int
        #            Currency string 10
        #            Value decimal
        #            Unit string 5
        #            Description string 35
        return data

    @api.multi
    def get_shipment_parameters_container(self):
        """ Return dict for order shipment (for quotation)
        """
        order = self
        partner = order.partner_shipping_id or order.partner_id
        data = {
            'DestinationInfo': {
                'ZipCode': partner.zip or '',  # 12
                'City': partner.city or '',  # * 50,
                'State': partner.state_id.code or '',  # * 2
                'Country': partner.country_id.code or '',  # 2
                'idSubzone': '',  # * int
                },
            'ShipType': order.ship_type or '',
            'PackageType': order.package_type or '',
            # order.carrier_mode_id.account_ref
            'Service': '',  # Empty for now * string
            'Courier': '',  # Empty for now * string
            'CourierService': '',  # Empty for now * string
            # 'COD': '',  # * boolean
            # 'CODValue': '',  # * decimal
            # 'CODPaymentMethod': '',  # * token CASH CHECK
            # 'Insurance': '',  # * boolean
            # 'InsuranceValue': '',  # * decimal
            # 'SaturdayDelivery': '',  # * boolean
            # 'SignatureRequired': '',  # * boolean
            # 'MBESafeValue': '',  # * boolean
            # 'MBESafeValueValue': '',  # * decimal

            'Items': order.get_items_parcel_block(),
        }
        return data

    @api.multi
    def get_items_parcel_block(self):
        """ Return parcels block
        """
        order = self
        data = {'Item': []}
        for parcel in order.parcel_ids:
            data['Item'].append({
                'Weight': parcel.real_weight,
                'Dimensions': {
                    'Lenght': parcel.length,  # TODO typo but written wrong
                    'Height': parcel.height,
                    'Width': parcel.width,
                }
            })
        return data

    @api.multi
    def update_with_courier_data(self, reply):
        """ Update with courier data
        """
        order = self
        tracking = reply['ShipmentsFullInfo']['ShipmentFullInfo'][0][
            'TrackingInfo']

        # Save tracking label
        self.save_order_label(tracking, mode='tracking')

        # tracking['MasterTrackingMBE']
        courier_tracking = tracking['CourierMasterTrk']
        self.write({
            'carrier_track_id': courier_tracking,
        })

    @api.multi
    def update_with_quotation(self, reply):
        """ Update order courier fields with reply SOAP
        """
        order = self
        carrier_mode_search = order.carrier_mode_id.account_ref
        supplier_pool = self.env['carrier.supplier']
        service_pool = self.env['carrier.supplier.mode']
        data = {}

        # Choose better quotation:
        quotations = reply['ShippingOptions']['ShippingOption']
        _logger.warning('Quotation founds: %s [Mode search: %s]' % (
            len(quotations),
            carrier_mode_search or 'disabled',
        ))
        pdb.set_trace()
        for quotation in quotations:
            try:
                # Check carrier if selected in request:
                carrier_code = quotation['Service']
                if carrier_mode_search and carrier_mode_search != carrier_code:
                    continue

                # Check and save best quotation:
                if not data or (quotation['NetShipmentTotalPrice'] <
                                data['NetShipmentTotalPrice']):
                    data = quotation
            except:
                _logger.error('Error on quotation: %s' % (sys.exc_info(), ))

        # Update order with better quotation:
        if data:
            try:
                # -------------------------------------------------------------
                # A. Courier:
                # -------------------------------------------------------------
                courier_code = data['Courier']
                courier_name = data['CourierDesc']
                suppliers = supplier_pool.search([
                    ('account_ref', '=', courier_code),
                    ('mode', '=', 'courier'),
                ])
                if suppliers:
                    supplier_id = suppliers[0].id
                else:
                    supplier_id = supplier_pool.create({
                        'account_ref': courier_code,
                        'name': courier_name,
                        'mode': 'courier',
                    }).id

                # -------------------------------------------------------------
                # B. Courier service:
                # -------------------------------------------------------------
                service_code = data['CourierService']
                service_name = data['CourierServiceDesc']
                services = service_pool.search([
                    ('account_ref', '=', service_code),
                    ('supplier_id', '=', supplier_id),
                ])
                if services:
                    service_id = services[0].id
                else:
                    supplier_id = service_pool.create({
                        'account_ref': service_code,
                        'name': service_name,
                        'supplier_id': supplier_id,
                    }).id

                # -------------------------------------------------------------
                # C. Carrier service:
                # -------------------------------------------------------------
                carrier_id = order.carrier_supplier_id.id
                carrier_code = data['Service']
                carrier_name = data['ServiceDesc']
                carriers = service_pool.search([
                    ('account_ref', '=', carrier_code),
                    ('supplier_id', '=', carrier_id),
                ])
                if carriers:
                    carrier_mode_id = carriers[0].id
                else:
                    carrier_mode_id = service_pool.create({
                        'account_ref': carrier_code,
                        'name': carrier_name,
                        'supplier_id': carrier_id,
                    }).id

                order.write({
                    'carrier_cost': data['NetShipmentPrice'],
                    'carrier_cost_total': data['NetShipmentTotalPrice'],
                    'has_cod': data['CODAvailable'],
                    'has_insurance': data['InsuranceAvailable'],
                    'has_safe_value': data['MBESafeValueAvailable'],
                    'courier_supplier_id': supplier_id,
                    'courier_mode_id': service_id,
                    'carrier_mode_id': carrier_mode_id,
                })

                # 'IdSubzone': 125,
                # 'SubzoneDesc': 'Italia-Zona A',

                return ''
            except:
                data = {}  # Used for new check

        if not data:  # Or previous update error
            # Reset data:
            order.write({
                'carrier_cost': 0.0,
                'carrier_mode_id': False,
                'courier_supplier_id': False,
                'courier_mode_id': False,
            })
            return 'Error updating data on order (clean quotation)'
        return ''

    # -------------------------------------------------------------------------
    # Override methods
    # -------------------------------------------------------------------------
    @api.multi
    def carrier_get_better_option(self):
        """ Get better options
        """
        if not self.carrier_supplier_id:
            raise exceptions.Warning('Need Carrier name to connect!')
        if not self.parcel_ids:
            raise exceptions.Warning(
                'Need almost one parcel line to get quotation!')
        return self.shipment_options_request()

    @api.multi
    def set_carrier_ok_yes(self):
        """ Override method for send carrier request
        """
        order = self
        # Get options:
        # error = order.shipment_options_request()

        error = order.shipment_request()
        if error:
            return order.write_log_chatter_message(error)
        return super(SaleOrder, self).set_carrier_ok_yes()

    @api.multi
    def set_carrier_ok_no(self):
        """ Override method for send carrier request
        """
        order = self
        error = order.delete_shipments_request()
        if error:
            return order.write_log_chatter_message(error)
        # raise exceptions.ValidationError('Not valid message')
        return super(SaleOrder, self).set_carrier_ok_no()

    # Button event:
    @api.multi
    def set_carrier_confirmed(self):
        """ Carrier confirmed for shipment
        """
        order = self
        error = order.close_shipments_request()
        if error:
            return order.write_log_chatter_message(error)
        return True

    @api.multi
    def get_folder_root_path(self, mode, root_path=None):
        """
        """
        if root_path is None:
            root_path = os.path.expanduser(
                '~/.local/share/Odoo/filestore/%s/data' % self.env.cr.dbname
                )
        path = os.path.join(root_path, mode)
        os.system('mkdir -p %s' % path)
        return path

    # Utility:
    @api.multi
    def save_order_label(self, reply, mode='label'):
        """ Save order label
        """
        order = self
        path = order.get_folder_root_path(mode)
        if mode == 'tracking':
            label_path = order.get_folder_root_path('label', root_path=path)
            parcel_path = order.get_folder_root_path('parcel', root_path=path)

        counter = 0
        if mode in ('label', 'tracking'):
            label_list = reply['Labels']['Label']
        else:
            label_list = [reply['Pdf']]

        for label in label_list:
            if mode in ('label', 'tracking'):
                counter += 1
                label_stream = label['Stream']
                label_type = label['Type']
                filename = '%s.%s.%s' % (
                    order.id, counter, label_type)
                fullname = os.path.join(path, filename)
            else:
                label_stream = label
                fullname = os.path.join(path, '%s.PDF' % (
                    order.id))

            with open(fullname, 'wb') as label_file:
                label_file.write(label_stream)

            # Split label for Courier PDF:
            if mode == 'tracking':
                fullname_label = os.path.join(label_path, filename)
                fullname_parcel = os.path.join(parcel_path, filename)

                # Get number of pages:
                output = subprocess.check_output([
                    'pdftk', fullname, 'dump_data'])
                total_pages = int(
                    ('%s' % output).split('NumberOfPages: ')[-1].split(
                        '\\')[0])

                # Split label:
                half_page = int(total_pages / 2)
                subprocess.check_output([
                    'pdftk', fullname,
                    'cat', '1-%s' % half_page,
                    'output',
                    fullname_label,
                ])

                # Split parcel label
                output = subprocess.check_output([
                    'pdftk', fullname,
                    'cat', '%s-%s' % (half_page + 1, total_pages),
                    'output',
                    fullname_parcel,
                ])

    @api.multi
    def update_order_with_soap_reply(self, reply):
        """ Update order data with SOAP reply (error checked in different call)
        """
        order = self
        master_tracking_id = reply['MasterTrackingMBE']
        system_reference_id = reply['SystemReferenceID']

        try:
            courier_track_id = reply['CourierMasterTrk']
            if courier_track_id == master_tracking_id:
                courier_track_id = False
                # Download label
            else:
                # TODO if raise error no label!
                order.save_order_label(reply, 'tracking')

        except:
            courier_track_id = False

        # Label if not Courier is not used:
        # order.save_order_label(reply, 'label')

        # InternalReferenceID 100
        # TrackingMBE* : {'TrackingMBE': ['RL28102279']

        order.write({
            'carrier_soap_state': 'pending',
            'master_tracking_id': master_tracking_id,
            'system_reference_id': system_reference_id,
            'carrier_track_id': courier_track_id,
        })

    # -------------------------------------------------------------------------
    #                            API CALLS:
    # -------------------------------------------------------------------------
    @api.multi
    def close_shipments_request(self):
        """ 2. CloseShipmentsRequest: Close shipment request
        """
        order = self

        soap_connection = order.carrier_supplier_id.soap_connection_id
        service = soap_connection.get_connection()
        master_tracking_id = order.master_tracking_id
        if not master_tracking_id:
            error = _('No master track ID so no confirmation!')
            _logger.error(error)
            return error

        # Prepare data:
        data = order.get_request_container(system='SystemType')
        data['MasterTrackingsMBE'] = master_tracking_id

        reply = service.CloseShipmentsRequest(data)
        error = order.check_reply_status(reply)
        if error:
            error = 'Error confirming: Track: %s\n%s' % (
                master_tracking_id,
                error,
            )
        else:
            order.write({
                # TODO carrier_track_id
                'carrier_soap_state': 'sent',  # TODO need another status?
            })

            order.save_order_label(reply, 'manifest')
            # TODO Write?
            # 'ShipmentClosed': 1,
            # 'TotalPackages': 2,
        return error

    @api.multi
    def delete_shipments_request(self):
        """ 4. API Delete Shipment Request: Delete shipment request
        """
        order = self
        error = ''
        soap_connection = order.carrier_supplier_id.soap_connection_id
        service = soap_connection.get_connection()

        master_tracking_id = order.master_tracking_id
        if master_tracking_id:
            # SOAP insert call:
            data = order.get_request_container(system='SystemType')
            data['MasterTrackingsMBE'] = master_tracking_id  # Also with Loop
            reply = service.DeleteShipmentsRequest(data)

            error = order.check_reply_status(reply)
            if error:
                error = 'Error deleting: Track: %s\n%s' % (
                    master_tracking_id,
                    error,
                )
        else:
            _logger.error('Order %s has no master tracking, cannot delete!' %
                          order.name)

        # Check carrier_track_id for permit delete:
        if not error:
            order.write({
                'carrier_soap_state': 'draft',
                'master_tracking_id': False,
                'system_reference_id': False,
                'carrier_track_id': False,
            })
        return error

    @api.multi
    def shipment_request(self):
        """ 15. API Shipment Request: Insert new carrier request
        """
        self.ensure_one()
        order = self
        # soap_pool = self.env['carrier.connection.soap']

        soap_connection = order.carrier_supplier_id.soap_connection_id
        if not soap_connection:
            return 'Order %s has carrier without SOAP ref.!' % order.name
        if order.state not in 'draft':
            return 'Order %s not in draft mode so no published!' % order.name
        if order.carrier_soap_id:
            return 'Order %s has SOAP ID %s cannot publish!' % (
                    order.name, order.carrier_soap_id)

        # Write description if not present:
        if not order.carrier_description:
            order.set_default_carrier_description()

        # -----------------------------------------------------------------
        # SOAP insert call:
        # -----------------------------------------------------------------
        service = soap_connection.get_connection()

        data = order.get_request_container(customer=False, system=True)
        data.update({
            'Recipient': order.get_recipient_container(),
            'Shipment': order.get_shipment_container(),
        })

        reply = service.ShipmentRequest(data)
        error = order.check_reply_status(reply)

        _logger.warning('\n%s\n\n%s\n' % (data, reply))

        if error:
            return error
        order.update_order_with_soap_reply(reply)

    master_tracking_id = fields.Char('Master Tracking', size=20)
    system_reference_id = fields.Char('System reference ID', size=20)
    carrier_soap_id = fields.Integer(
        string='Carrier SOAP ID')
    carrier_soap_state = fields.Selection(
        string='Carrier state', default='draft',
        selection=[
            ('draft', 'Draft'),
            ('pending', 'Pending'),
            ('sent', 'Sent'),
            ('delivered', 'Delivered'),  # Closed
        ])
    delivery_soap_state = fields.Selection(
        string='Delivery state', default='WAITING_DELIVERY',
        selection=[
            ('WAITING_DELIVERY', 'Waiting'),
            ('PARTIALLY_DELIVERED', 'Partially delivered'),
            ('DELIVERED', 'Delivered'),
            ('EXCEPTION', 'Exception'),
            ('NOT_AVAILABLE', 'Not available'),
        ])

    @api.multi
    def shipments_list_request_detail_source(self):
        """ 16. Read data from Request
                Function has 2 ways of call: single order, get period list
        """
        self.ensure_one()
        order = self  # TODO loop?

        soap_connection = order.carrier_supplier_id.soap_connection_id
        if not soap_connection:
            return 'Order %s has carrier without SOAP ref.!' % order.name
        if order.carrier_soap_id:
            return 'Order %s has SOAP ID %s cannot check!' % (
                    order.name, order.carrier_soap_id)
        if not order.master_tracking_id:
            return 'Order %s without master track ID %s cannot check!' % (
                    order.name, order.carrier_soap_id)

        service = soap_connection.get_connection()
        data = order.get_request_container(
            customer=True, system=True, store=True,
        )
        # DateFrom *
        # DateTo *
        # MBESafeValue * boolean
        # WithCourierWaybill * boolean
        # PendingExportToSAM * boolean

        data['MBEMasterTrackings'] = order.master_tracking_id  # unbounded!
        reply = service.ShipmentsListRequest(RequestContainer=data)
        error = order.check_reply_status(reply)
        if not error:
            # Update SOAP data for real call
            order.update_with_courier_data(reply)
        return error

    @api.multi
    def shipment_options_request(self):
        """ 17. API ShippingOptionsRequest: Get better quotation
        """
        self.ensure_one()
        order = self

        soap_connection = order.carrier_supplier_id.soap_connection_id
        if not soap_connection:
            return 'Order %s has carrier without SOAP ref.!' % order.name
        if order.state not in 'draft':
            return 'Order %s not in draft mode so no published!' % order.name
        if order.carrier_soap_id:
            return 'Order %s has SOAP ID %s cannot publish!' % (
                    order.name, order.carrier_soap_id)

        # -----------------------------------------------------------------
        # SOAP insert call:
        # -----------------------------------------------------------------
        service = soap_connection.get_connection()
        data = order.get_request_container(
            customer=False, system=True)

        data['ShippingParameters'] = order.get_shipment_parameters_container()

        reply = service.ShippingOptionsRequest(data)
        _logger.warning('\n%s\n\n%s\n' % (data, reply))
        error = order.check_reply_status(reply)
        if not error:
            # Update SOAP data for real call
            order.update_with_quotation(reply)
        return error

    master_tracking_id = fields.Char('Master Tracking', size=20)
    system_reference_id = fields.Char('System reference ID', size=20)
    carrier_soap_id = fields.Integer(
        string='Carrier SOAP ID')
    carrier_soap_state = fields.Selection(
        string='Carrier state', default='draft',
        selection=[
            ('draft', 'Draft'),
            ('pending', 'Pending'),
            ('sent', 'Sent'),
            ('delivered', 'Delivered'),  # Closed
        ])
    shipper_type = fields.Selection(
        string='Shipper type', default='COURIERLDV', required=True,
        selection=[
            ('COURIERLDV', 'Courier LDV'),
            ('MBE', 'MBE'),
        ])

    ship_type = fields.Selection(
        string='Ship type', default='EXPORT', required=True,
        selection=[
            ('EXPORT', 'Export'),
            ('IMPORT', 'Import'),
            ('RETURN', 'Return'),
        ])
    package_type = fields.Selection(
        string='Package type', default='GENERIC', required=True,
        selection=[
            ('GENERIC', 'Generic'),
            ('ENVELOPE', 'Envelope'),
            ('DOCUMENTS', 'Documents'),
        ])
