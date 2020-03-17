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

    @api.multi
    def button_load_category(self):
        """ Load all category from website
        """
        return self.env['product.category'].load_category(connector=self)

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

    @api.model
    def load_category(self, connector):
        """ Load category from Wordpress
        """
        # Load current category:
        categories = self.search([
            ('connector_id', '=', connector.id),
            ])
        categories_db = {}
        parent_wp2odoo = {}  # Convert ID
        for category in categories:
            parent_wp_id = category.parent_id.wp_id or False
            categories_db[(
                parent_wp_id, category.name)] = category.id
            if parent_wp_id not in parent_wp2odoo:
                parent_wp2odoo[parent_wp_id] = category.parent_id.id

        wcapi = connector.get_connector()
        params = {
            'per_page': 50,
            'page': 1,
            'order': 'asc',
            'orderby': 'id',
            }

        wp_category = {}
        while True:
            _logger.info('Reading category from %s [Record %s-%s]' % (
                connector.name,
                params['per_page'] * (params['page'] - 1),
                params['per_page'] * params['page'],
                ))
            reply = wcapi.get('products/categories', params=params)
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
                parent_wp_id = record['parent'] or False
                sequence = record['menu_order']  # TODO
                image = record['image']  # TODO
                key = (parent_wp_id, name)
                print('Category ID: %s > Parent [%s] Name [%s]' % (
                    wp_id, parent_wp_id, name,
                    ))
                if key in categories_db:  # Update?
                    pass
                    # else:
                    # parent_odoo_id = parent_wp2odoo.get(parent_wp_id, False)
                    # wp_category[key] = {
                    #     'connector_id': connector.id,
                    #     'wp_id': wp_id,
                    #     'name': name,
                    #     'description': description,
                    #     }

        # for key in sorted(wp_category):
        #     parent_wp_id, name = key
        #     data = wp_category[key]
        #     data['parent_id'] = parent_wp2odoo.get(parent_wp_id)
        #     self.create(data)
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
