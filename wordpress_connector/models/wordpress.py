# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import xlsxwriter
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class WPAttribute(models.Model):
    """ Model name: Wordpress Attribute
    """
    _name = 'wp.attribute'
    _description = 'Wordpress Attribute'
    _order = 'name'

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    name = fields.Char('Name', size=64, required=True)
    wp_id = fields.Integer(string='Wp ID', readonly=True)
    description = fields.Text('Description')
    is_variation = fields.Boolean('Is variation')
    # Image?


class WPAttributeTerm(models.Model):
    """ Model name: Wordpress Attribute Term
    """
    _name = 'wp.attribute.term'
    _description = 'Wordpress attribute term'
    _order = 'name'

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    name = fields.Char('Name', size=64, required=True)
    wp_id = fields.Integer(string='Wp ID', readonly=True)
    attribute_id = fields.Many2one(
        comodel_name='wp.attribute',
        string='Attribute',
        )


class WPAttributeRelations(models.Model):
    """ Model name: Wordpress Attribute
    """
    _inherit = 'wp.attribute'

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    term_ids = fields.One2many(
        comodel_name='wp.attribute.term',
        inverse_name='attribute_id',
        string='Terms',
        )


class ProductProduct(models.Model):
    """ Model name: Product
    """
    _inherit = 'product.product'

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    wp_master = fields.Boolean(
        string='Wp_master', help='Wordpress master product')
    wp_master_id = fields.Many2one(
        comodel_name='product.product',
        string='Master')
    wp_default_id = fields.Many2one(
        comodel_name='product.product',
        domain="[('wp_master_id', '=', active_id)]",
        string='Default')
    wp_variation_term_id = fields.Many2one(
        comodel_name='wp.attribute.term',
        string='Variation terms',
        help='Term used for this variation'
        )


class ProductProductRelation(models.Model):
    """ Model name: Product
    """
    _inherit = 'product.product'

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    wp_slave_ids = fields.One2many(
        comodel_name='product.product',
        inverse_name='wp_master_id',
        string='Slave')
