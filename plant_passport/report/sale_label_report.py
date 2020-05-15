# Copyright 2019  Micronaet SRL (<https://micronaet.com>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import logging
from odoo import fields, api, models

_logger = logging.getLogger(__name__)


class ReportSaleOrderPassportLabel(models.AbstractModel):
    """ Passport report for label
    """
    _name = 'report.plant_passport.report_sale_passport_label'

    # -------------------------------------------------------------------------
    # Override
    # -------------------------------------------------------------------------
    @api.model
    def get_report_values(self, docids, data=None):
        """ Render report invoice parser:
            Note: ex render_html(self, docids, data)
        """
        # Correct here not presence of docids:
        if not docids:
            docids = self.env.context.get('active_ids')
        model_name = 'sale.order'
        docs = self.env[model_name].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': model_name,
            'docs': docs,
            'data': data,

            # Parser functions:
            # 'show_the_block': self.show_the_block,
        }

    # -------------------------------------------------------------------------
    # Parser function:
    # -------------------------------------------------------------------------
    # @api.model
    # def show_the_block(self, block, data=None):
    #     """ Check if the block need to be showed
    #     """
    #     if data is None:
    #         data = {}
    #     return not block.hide_block

