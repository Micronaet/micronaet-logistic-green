# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import os
import sys
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
    # Utility:
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
            data['InternalReferenceID'] = self.internal_reference
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
    def get_shipment_container(self, order):
        """ Return dict for order shipment
        """
        # TODO complete fields:
        data = {
            'ShipperType': 'MBE',  # string (COURIERLDV, MBE)
            'Description': self.check_size(
                order.carrier_description, 100, dotted=True),
            'COD': False,  # boolean
            # 'CODValue': '',  # * decimal
            'MethodPayment': 'CASH',  # * string (CASH, CHECK)
            'Insurance': False,  # boolean
            # 'InsuranceValue': '',  # * decimal
            # 'Service': '',  # * string
            # 'Courier': '',  # * string
            # 'CourierService': '',  # * string
            # 'CourierAccount': '',  # * string
            'PackageType': '',  # token (ENVELOPE, DOCUMENTS, GENERIC)
            # 'Value': '',  # * decimal
            # 'ShipmentCurrency': '',  # * string
            'Referring': order.name,  # * string 30
            'InternalNotes': 'ORDINE DA CANCELLARE',  # * string
            'Notes': 'ORDINE DA CANCELLARE',  # * string
            # 'SaturdayDelivery': '',  # * boolean
            # 'SignatureRequired': '',  # * boolean
            # 'ShipmentOrigin': '',  # * string
            # 'ShipmentSource': '',  # * int
            # 'MBESafeValue': '',  # * boolean
            # 'MBESafeValueValue': '',  # * decimal
            # 'MBESafeValueDescription': '',  # * string 100
            # 'LabelFormat': '',  # * token (OLD, NEW)
            'Items': [],
        }
        for parcel in order.parcel_ids:
            data['Items'].append(
                {'Item': {
                    'Weight': parcel.real_weight,
                    'Dimension': {
                        'Length': parcel.length,
                        'Height': parcel.height,
                        'Width': parcel.width,
                    }}})

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
        return data

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
    # Override methods
    # -------------------------------------------------------------------------
    @api.multi
    def set_carrier_ok_yes(self):
        """ Override method for send carrier request
        """
        error = self.shipment_request()
        if error:
            return self.write_log_chatter_message(error)
        return super(SaleOrder, self).set_carrier_ok_yes()

    @api.multi
    def set_carrier_ok_no(self):
        """ Override method for send carrier request
        """
        error = self.delete_shipments_request()
        if error:
            return self.write_log_chatter_message(error)
        return super(SaleOrder, self).set_carrier_ok_no()

    @api.multi
    def save_order_label(self, order, reply):
        """ Save order label
        """
        # Labels* LabelsType
        #    Label LabelType
        #        Stream B64
        #        Type 4
        import pdb; pdb.set_trace()
        path = os.path.expanduser(
            '~/.local/share/Odoo/filestore/%s' % self.cr.dbname)
        filename = os.path.join(path, '%s.pdf' % order.id)
        for label in reply['Labels']:
            label = label['Label']
            label_b64 = label['Stream']
            label_type = label['Type']
            with open(filename, 'wb') as label_file:
                label_file.write(label_b64)
            # TODO save label linked to order


    @api.multi
    def update_order_with_soap_reply(self, order, reply):
        """ Update order data with SOAP reply (error checked in different call)
        """
        master_tracking_id = reply['MasterTrackingMBE']
        system_reference_id = reply['SystemReferenceID']
        self.save_order_label(order, reply)
        # InternalReferenceID 100
        # TrackingMBE* : {'TrackingMBE': ['RL28102279']

        order.write({
            'carrier_soap_state': 'pending',
            'master_tracking_id': master_tracking_id,
            'system_reference_id': system_reference_id,
            # TODO carrier_track_id
        })

    # -------------------------------------------------------------------------
    # API CALLS:
    # -------------------------------------------------------------------------
    @api.multi
    def delete_shipments_request(self):
        """ 4. API Delete Shipment Request: Delete shipment request
        """
        order = self
        soap_pool = self.env['carrier.connection.soap']
        service = soap_pool.get_connection()

        master_tracking_id = order.master_tracking_id
        if not master_tracking_id:
            error = ('Order %s has no master tracking, cannot delete!' %
                order.name)
            return error

        # -----------------------------------------------------------------
        # SOAP insert call:
        # -----------------------------------------------------------------
        data = soap_pool.get_request_container(system=True)
        data['MasterTrackingMBE'] = master_tracking_id  # Loopable
        service.DeleteShipmentsRequest(data)
        order.write({
            # TODO carrier_track_id
            'carrier_soap_state': 'draft',
            'master_tracking_id': False,
            'system_reference_id': False,
        })

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

        # -----------------------------------------------------------------
        # SOAP insert call:
        # -----------------------------------------------------------------
        service = soap_connection.get_connection()
        data = soap_connection.get_request_container(system=True)

        # TODO create data dict
        data['Recipient'] = soap_connection.get_recipient_container(
            order.partner_id)
        import pdb; pdb.set_trace()
        data['Shipment'] = soap_connection.get_shipment_container(order)

        reply = service.ShipmentRequest(data)
        error = soap_connection.check_reply_status(reply)
        if error:
            return error
        self.update_order_with_soap_reply(order, reply)

    master_tracking_id = fields.Integer('Master Tracking')
    system_reference_id = fields.Integer('System reference ID')
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
