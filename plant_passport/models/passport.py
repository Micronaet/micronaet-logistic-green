# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import xlrd
import logging
import base64
from odoo import models, fields, api, exceptions
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class PasswordPlantCategory(models.Model):
    """ Passport category for product / plant that is marked to use it
    """
    _name = 'passport.plant.category'
    _description = 'Passport plant category'

    name = fields.Char('Botanic genre')
    note = fields.Text('Note')


class ResCompany(models.Model):
    """ Company parameters
    """
    _inherit = 'res.company'

    passport_code = fields.Char('Passport code')
    passport_logo = fields.Binary('Passport logo')


class ProductTemplate(models.Model):
    """ Add extra fields for passport
    """
    _inherit = 'product.template'

    passport_manage = fields.Boolean('Passport manage')
    passport_country_id = fields.Many2one(
        comodel_name='res.country',
        string='Passport country',
    )
    passport_category_id = fields.Many2one(
        comodel_name='passport.plant.category',
        string='Passport category',
    )
    passport_treatment = fields.Char(
        'Treatment')
    passport_company_code = fields.Char(
        string='Company code',
        related='company_id.passport_code',
        readonly=True,
    )
