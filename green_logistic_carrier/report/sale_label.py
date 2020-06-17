#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import os
import sys
import re
import logging
from odoo import fields, models, api
from odoo import _

_logger = logging.getLogger(__name__)


# Override label depend on parcels:
class ReportSaleOrderPassportLabel(models.AbstractModel):
    """ Passport report for label
    """
    _inherit = 'report.plant_passport.report_sale_passport_label'

    # -------------------------------------------------------------------------
    # Parser function:
    # -------------------------------------------------------------------------
    @api.model
    def get_labels_for_report(self, order):
        """ Format label for report
        """
        labels_country = []
        labels_category = []
        total = sum(
            [1 for parcel in order.parcel_ids if not parcel.no_label]) or 1
        for line in order.order_line:
            product = line.product_id
            if not product.passport_manage:
                continue

            category = (product.passport_category_id.name or '').title()
            if category:
                if category not in labels_category:
                    labels_category.append(category)
            else:
                _logger.error('Category not present in %s' % product.name)
                continue

            country = product.passport_country_id.code or ''
            if country:
                if country not in labels_country:
                    labels_country.append(country)
            else:
                _logger.error('Country not present in %s' % product.name)

        label_block = []
        for i in range(total):
            label_block.append(
                (', '.join(labels_country), ', '.join(labels_category)))
        print(label_block)
        return label_block
