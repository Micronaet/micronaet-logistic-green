# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import pdb
import logging
from odoo import fields, models, api
from odoo import _

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    """ Model name: Sale order integration
    """
    _inherit = 'sale.order'

    @api.multi
    def wp_wf_processing(self):
        """ Override procedure also for manage Logistic status
        """
        # Call Logistic procedure when confirmed payment
        super(SaleOrder, self).workflow_draft_to_confirmed()

        # Call original wordpress procedure overridden here (after all)
        super(SaleOrder, self).wp_wf_processing()
