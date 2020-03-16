# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import os
import logging
import base64
import woocommerce
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class WPConnector(models.Model):
    """ Model name: Wordpress Connector
    """
    _name = 'wp.connector'
    _description = 'Wordpress Connector'
    _order = 'company_id'

    # -------------------------------------------------------------------------
    # Utility:
    # -------------------------------------------------------------------------
    @api.model
    def get_connector(self):
        """ Connect with Word Press API management
        """
        connector = self[0]
        _logger.info('>>> Connecting: %s%s API: %s, timeout=%s' % (
            connector.url,
            connector.version,
            connector.api,
            connector.timeout,
            ))
        try:
            return woocommerce.API(
                url=connector.url,
                consumer_key=connector.key,
                consumer_secret=connector.secret,
                wp_api=connector.api,
                version=connector.version,
                timeout=connector.timeout,
                )
        except:
            _logger.error('Cannot connect to Wordpress!!')

    # -------------------------------------------------------------------------
    # Button:
    # -------------------------------------------------------------------------
    @api.multi
    def button_load_tags(self):
        """ Load all tags from website
        """
        return self.env['wp.tag'].load_tags(connector=self)

    @api.multi
    def button_load_attributes(self):
        """ Load all tags from website
        """
        return self.env['wp.attribute'].load_attributes(connector=self)

    # -------------------------------------------------------------------------
    #                               COLUMNS:
    # -------------------------------------------------------------------------
    name = fields.Char(string='Name', required=True, size=50)
    company_id = fields.Many2one('res.company', 'Company', required=True)

    url = fields.Char('WP URL', size=180, required=True)
    key = fields.Char('WP consumer key', size=180, required=True)
    secret = fields.Char('WP consumer secret', size=180, required=True)

    api = fields.Boolean('WP API', default=True)
    version = fields.Char(
        'WP Version', size=10, default='wc/v3', required=True)

    image_path = fields.Char('Image path', size=180)
    image_extension = fields.Char('Image extension', size=5)
    timeout = fields.Integer('Timeout', default=600)

    # album_ids = fields.Many2many(
    #    'product.image.album',
    #    'connector_album_rel', 'server_id', 'album_id', 'Album')


class ProductCategory(models.Model):
    """ Model name: Wordpress > Product Category
    """
    _inherit = 'product.category'

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    wp_id = fields.Integer(string='Wp ID', readonly=True)
    connector_id = fields.Many2one('wp.connector', 'Connector')
    # TODO Image


class WPTag(models.Model):
    """ Model name: Wordpress Tag
    """
    _name = 'wp.tag'
    _description = 'Wordpress Tags'
    _order = 'name'

    @api.model
    def load_tags(self, connector):
        """ Load tags from Wordpress
        """
        # Load current tags:
        tags = self.search([
            ('connector_id', '=', connector.id),
            ])
        # tags.write({'removed': True})
        tags_db = {}
        for tag in tags:
            tags_db[tag.name] = tag.id

        wcapi = connector.get_connector()
        start_page = 1
        params = {'per_page': 50, 'page': start_page}
        while True:
            _logger.info('Reading tags from %s [Record %s-%s]' % (
                connector.name,
                params['per_page'] * (params['page'] - 1),
                params['per_page'] * params['page'],
                ))
            reply = wcapi.get('products/tags', params=params)
            params['page'] += 1
            if not reply.ok:
                _logger.error('Error: %s' % reply.text)
                break

            records = reply.json()
            if not records:
                break
            for record in records:
                wp_id = record['id']
                name = record['name']
                description = record['description']
                if name in tags_db:  # Update?
                    pass
                else:
                    self.create({
                        'connector_id': connector.id,
                        'wp_id': wp_id,
                        'name': name,
                        'description': description
                    })

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    name = fields.Char('Tag name', size=64, required=True)
    description = fields.Char('Description', size=80)
    wp_id = fields.Integer(string='Wp ID', readonly=True)
    connector_id = fields.Many2one('wp.connector', 'Connector')
    unused = fields.Boolean('Removed', help='No more present on WP')


class WPAttribute(models.Model):
    """ Model name: Wordpress Attribute
    """
    _name = 'wp.attribute'
    _description = 'Wordpress Attribute'
    _order = 'name'

    @api.model
    def load_attributes(self, connector):
        """ Load attributes from Wordpress
        """
        term_pool = self.env['wp.attribute.term']

        # ---------------------------------------------------------------------
        # Load current attribute:
        # ---------------------------------------------------------------------
        attributes = self.search([
            ('connector_id', '=', connector.id),
            ])
        attributes_db = {}
        terms_db = {}
        for attribute in attributes:
            attributes_db[attribute.name] = attribute.id
            wp_id = attribute.wp_id
            for term in attribute.term_ids:
                terms_db[(wp_id, term.name)] = term.id

        wcapi = connector.get_connector()
        params = {'per_page': 100, 'page': 1}
        while True:
            _logger.info('Reading attribute from %s [Record %s-%s]' % (
                connector.name,
                params['per_page'] * (params['page'] - 1),
                params['per_page'] * params['page'],
                ))
            reply = wcapi.get('products/attributes', params=params)
            params['page'] += 1
            if not reply.ok:
                _logger.error('Error: %s' % reply.text)
                break

            records = reply.json()
            if not records:
                break
            for record in records:
                wp_id = record['id']
                name = record['name']
                if name in attributes_db:  # TODO Update?
                    _logger.info('Update: %s' % name)
                    attribute_id = attributes[name]
                else:
                    _logger.info('Create: %s' % name)
                    attribute_id = self.create({
                        'connector_id': connector.id,
                        'wp_id': wp_id,
                        'name': name,
                    }).id

                # -------------------------------------------------------------
                # Add terms for attributes:
                # -------------------------------------------------------------
                term_params = {'per_page': 100, 'page': 1}
                while True:
                    term_reply = wcapi.get(
                        'products/attributes/%s/terms' % wp_id,
                        params=term_params)
                    term_params['page'] += 1
                    if not term_reply.ok:
                        _logger.error('Error in terms: %s' % term_reply.text)
                        break

                    term_records = term_reply.json()
                    if not term_records:
                        break
                    for term in term_records:
                        term_name = term['name']
                        if (wp_id, term_name) not in terms_db:
                            term_pool.create({
                                'attribute_id': attribute_id,
                                'name': term_name,
                                'wp_id': term['id'],
                            })
                        _logger.info(' -- > %s' % term_name)
            break  # TODO problem with page to browse
    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    name = fields.Char('Name', size=64, required=True)
    connector_id = fields.Many2one('wp.connector', 'Connector')
    wp_id = fields.Integer(string='Wp ID', readonly=True)
    # is_variation = fields.Boolean('Is variation')
    # is_visible = fields.Boolean('Is visible')
    unused = fields.Boolean('Removed', help='No more present on WP')
    # order_by: menu_order
    # type: select
    # TODO Image?


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
    attribute_id = fields.Many2one('wp.attribute', 'Attribute')
    connector_id = fields.Many2one(
        'wp.connector', 'Connector',
        related='attribute_id.connector_id')


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


class ProductTemplate(models.Model):
    """ Model name: Product Template
    """
    _inherit = 'product.template'

    # -------------------------------------------------------------------------
    #                                FIELD FUNCTION:
    # -------------------------------------------------------------------------
    @api.multi
    def _get_wp_image_file(self):
        """ Return image loading from file:
        """
        connector = self[0].company_id.wp_connector_ids[0]
        path = connector.image_path
        extension = connector.image_extension or 'png'

        for product in self:
            if not path:
                product.wp_image = False
                _logger.info('Missed path, check connector parameter')
                continue
            default_code = (product.default_code or '').replace(' ', '&nbsp;')
            filename = os.path.join(
                path,
                #  Default image is .000
                '%s.000.%s' % (
                    product.wp_id,  # default_code,
                    extension,
                    ),
                )
            try:
                f_data = open(filename, 'rb')
                product.wp_image = base64.encodebytes(f_data.read())
                f_data.close()
            except:
                product.wp_image = False

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    wp_id = fields.Integer(string='Wp ID', readonly=True)
    wp_sku = fields.Char('SKU', size=25, readonly=True)
    connector_id = fields.Many2one('wp.connector', 'Connector')
    wp_published = fields.Boolean(
        string='WP published', help='Product present on Wordpress site')

    # Master slave management:
    wp_master = fields.Boolean(
        string='Is master', help='Wordpress master product')
    wp_master_id = fields.Many2one(
        comodel_name='product.template',
        string='Master')
    wp_default_id = fields.Many2one(
        comodel_name='product.template',
        domain="[('wp_master_id', '=', active_id)]",
        string='Default')
    # TODO many2many field needed:
    wp_variation_term_id = fields.Many2one(
        comodel_name='wp.attribute.term',
        string='Variation terms',
        help='Term used for this variation'
        )

    # Link management:
    # wp_up_sell_ids = fields.Many2many(
    #    comodel_name='product.template',
    #    string='Up sell product')
    # wp_cross_sell_ids = fields.Many2many(
    #    comodel_name='product.template',
    #    string='Cross sell product')

    # Tags:
    wp_tag_ids = fields.Many2many('wp.tag', 'Tags')

    wp_image = fields.Binary(
         compute=_get_wp_image_file,
         help='Load image from folder for connector', string='WP Image')


class ProductTemplateRelation(models.Model):
    """ Model name: Product Template
    """
    _inherit = 'product.template'

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    wp_slave_ids = fields.One2many(
        comodel_name='product.template',
        inverse_name='wp_master_id',
        string='Slave')


class ResCompany(models.Model):
    """ Model name: Company
    """
    _inherit = 'res.company'

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    wp_connector_ids = fields.One2many(
        comodel_name='wp.connector',
        inverse_name='company_id',
        string='Connector')
