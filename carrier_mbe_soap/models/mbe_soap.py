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

    @api.multi
    def check_reply_status(self, reply):
        """ Get Service connection to make calls:
        """
        self.ensure_one()

        if reply['Status'] == 'ERROR':
            _logger.error('%s' % (reply['Errors'], ))  # TODO better!
            # Error[{'id', 'Description'}]
            return False
        return True

    @api.multi
    def get_request_container(self):
        """ Get Service connection to make calls:
        """
        self.ensure_one()
        return {
            'Credentials': {
                'Username': self.username,
                'Passphrase': self.passphrase,
            },
            'InternalReferenceID': self.internal_reference_id,
            'CustomerID': self.customer_id,
        }

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
        'WSDL root', size=40, required=True,
        default='https://www.onlinembe.it/wsdl/OnlineMbeSOAP.wsdl')
    # namespace
    username = fields.Char('Username', size=64, required=True)
    passphrase = fields.Char('Passphrase', size=64, required=True)

    system = fields.Char('System', size=10, required=True, default='IT')
    internal_reference = fields.Char(
        'Internal reference', size=10, default='MI030-lg')
    customer_id = fields.Char('Customer ID', size=4, required=True)

    # Not used for now:
    sam_id = fields.Char('SAM ID', size=4)
    department_id = fields.Char('SAM ID', size=4)


