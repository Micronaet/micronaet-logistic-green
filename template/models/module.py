# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import xlsxwriter
import logging
import base64
import shutil
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class Model(models.Model):
    """ Model name: Model
    """
    _name = 'model'
    _description = 'Model'
    _order = 'name'

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    name = fields.Char('Name', size=64, required=True)

