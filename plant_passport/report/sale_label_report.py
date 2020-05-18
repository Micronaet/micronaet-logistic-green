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
            'get_labels_for_report': self.get_labels_for_report,
        }

    # -------------------------------------------------------------------------
    # Parser function:
    # -------------------------------------------------------------------------
    @api.model
    def get_labels_for_report(self, order):
        """ Format label for report
        """
        cols = 2
        labels = {}
        for line in order.order_line:
            product = line.product_id
            if not product.passport_manage:
                continue
            category = product.passport_category_id.name or ''
            country = product.passport_country_id.code or ''
            if not category:
                _logger.error('Category not present in %s' % product.name)
                continue
            if not country:
                _logger.error('Country not present in %s' % product.name)

            if country not in labels:
                labels[country] = []

            if category not in labels[country]:
                labels[country].append(category)
        label_block = []
        keys = [key for key in labels]

        for position in range(0, len(labels), cols):
            block = [
                (keys[position], ', '.join(labels[keys[position]])),
                False,
            ]
            try:
                block[1] = (
                    keys[position + 1],
                    ', '.join(labels[keys[position + 1]]),
                )
            except:
                pass
            label_block.append(block)
        return label_block

