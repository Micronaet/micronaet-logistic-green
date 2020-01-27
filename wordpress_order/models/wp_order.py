# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


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


