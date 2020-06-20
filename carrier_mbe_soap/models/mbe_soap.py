# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import io
import xlsxwriter
import logging
import base64
import shutil
import zeep
from odoo import models, fields, api

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

    @api.multi
    def check_reply_status(self, reply):
        """ Get Service connection to make calls:
        """
        self.ensure_one()
        # Status token (OK, ERROR)

        if reply['Status'] == 'ERROR':
            _logger.error('%s' % (reply['Errors'], ))  # TODO better!
            # Error[{'id', 'Description'}]
            return False
        return True

    # Create data container:
    @api.multi
    def get_request_container(
            self, credentials=True, internal=True, customer=True, system=False,
            store=False):
        """ Get Service connection to make calls, parameters are passed as
            boolean switch:
        """
        self.ensure_one()
        data = {}
        if credentials:
            data['Credentials'] = {
                'Username': self.username,
                'Passphrase': self.passphrase,
            }
        if internal:
            data['InternalReferenceID'] = self.internal_reference_id
        if customer:
            data['CustomerID'] = self.customer_id
        if system:
            data['System'] = self.system
        if store:
            data['StoreID'] = self.store_id
        return data

    @api.multi
    def get_recipient_container(self, partner):
        """ Return dict for Partner container
        """
        res = {}
        # Name 35
        # CompanyName 35
        # Nickname 100
        # Address 100
        # Address2 35
        # Address3 35
        # Phone 50
        # ZipCode 12
        # City 50
        # State 2
        # Country 2
        # Email 75
        # SubzoneId int
        # SubzoneDesc No restriction?

        return res

    @api.multi
    def get_shipment_container(self, order):
        """ Return dict for order shipment
        """
        res = {}
        # ShipperType string (COURIERLDV, MBE)
        # Description string 100
        # COD boolean
        # CODValue* decimal
        # MethodPayment* string (CASH, CHECK)
        # Insurance boolean
        # InsuranceValue* decimal
        # Service* string
        # Courier* string
        # CourierService* string
        # CourierAccount* string
        # PackageType token (ENVELOPE, DOCUMENTS, GENERIC)
        # Value* decimal
        # ShipmentCurrency* string
        # Referring* string 30
        # Items ItemsType
        #    Item ItemType
        #        Weight decimal
        #        Dimensions DimensionsType
        #            Lenght decimal
        #            Height decimal
        #            Width decimal
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
        # InternalNotes* string
        # Notes* string
        # SaturdayDelivery* boolean
        # SignatureRequired* boolean
        # ShipmentOrigin* string
        # ShipmentSource* int
        # MBESafeValue* boolean
        # MBESafeValueValue* decimal
        # MBESafeValueDescription* string 100
        # LabelFormat* token (OLD, NEW)
        return res

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

    @api.multi
    def update_order_with_soap_reply(self, order, reply):
        """ Update order data with SOAP reply (error checked in different call)
        """
        # InternalReferenceID 100
        # SystemReferenceID 30
        # MasterTrackingMBE string
        # TrackingMBE*
        # Labels* LabelsType
        #    Label LabelType
        #        Stream B64
        #        Type 4
        order.write({'carrier_soap_state': 'pending'})

    # -------------------------------------------------------------------------
    # API CALLS:
    # -------------------------------------------------------------------------
    @api.multi
    def delete_shipments_request(self):
        """ 4. API Delete Shipment Request: Delete shipment request
        """
        soap_pool = self.env['carrier.connection.soap']
        service = soap_pool.get_connection()
        for order in self:
            master_tracking_id = order.master_tracking_id
            if not master_tracking_id:
                _logger.error(
                    'Order %s has no master tracking, cannot delete!' %
                    order.name)
                continue

            # -----------------------------------------------------------------
            # SOAP insert call:
            # -----------------------------------------------------------------
            data = soap_pool.get_request_container(system=True)
            data['MasterTrackingsMBE'] = master_tracking_id  # Repeatable
            service.DeleteShipmentsRequest(data)
        order.write({
            'carrier_soap_state': 'draft',
            'master_tracking_id': False,
        })

    @api.multi
    def shipment_request(self):
        """ 15. API Shipment Request: Insert new carrier request
        """
        soap_pool = self.env['carrier.connection.soap']
        service = soap_pool.get_connection()
        for order in self:
            soap_connection_id = order.soap_connection_id
            if not soap_connection_id:
                _logger.error(
                    'Order %s has carrier without SOAP ref.!' % order.name)
                continue

            if order not in 'draft':
                _logger.error(
                    'Order %s not in draft mode so no publish!' % order.name)
                continue
            if order.carrier_soap_id:
                _logger.error(
                    'Order %s has SOAP ID %s cannot publish!' % (
                        order.name, order.carrier_soap_id))
                continue

            # -----------------------------------------------------------------
            # SOAP insert call:
            # -----------------------------------------------------------------
            data = soap_pool.get_request_container(system=True)

            # TODO create data dict
            data['Recipient'] = soap_pool.get_recipient_container(
                order.partner_id)  # TODO or shipment address??
            data['Shipment'] = soap_pool.get_shipment_container(
                order)

            reply = service.ShipmentRequest(data)
            if not soap_pool.check_reply_status(reply):
                _logger.error('Error checking order: %s' % order.name)

            # TODO Check reply
            self.update_order_with_soap_reply(order, reply)

    master_tracking_id = fields.Integer('Master Tracking')
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
