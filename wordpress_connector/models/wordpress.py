# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import logging
import woocommerce
from odoo import models, fields, api, exceptions
import pdb

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
                query_string_auth=True,
                )
        except:
            _logger.error('Cannot connect to Wordpress!!')

    @api.model
    def get_publish_parameters(self, empty=False):
        """ Return publish dict used for publish block setup and preload
            If need empty record for setup in procedure pass empty = True
        """
        if empty:
            force = False  # every field is False
        else:
            force = True  # every field depend on parameter
        parameters = {
            'block': {
                'product': self.publish_product_block,
                'variant': self.publish_variant_block,
                },
            'publish': {
                'text': force and self.publish_text,
                'numeric': force and self.publish_numeric,
                'variant': force and self.publish_variant,
                'stock': force and self.publish_stock,
                'price': force and self.publish_price,
                'category': force and self.publish_category,
                'tag': force and self.publish_tag,
                'attribute': force and self.publish_attribute,
                'default': force and self.publish_default,
                'image': force and self.publish_image,
                'linked': force and self.publish_linked,
                },
            'preload': {
                'attribute': force and self.update_attribute,
                'category': force and self.update_category,
                'tag': force and self.update_tag,
                },
            }

        # Log setup of parameters:
        log_text = ''
        for mode in sorted(parameters):
            log_text += '\nList publish parameters for %s:\n' % mode
            for field in parameters[mode]:
                if parameters[mode][field]:
                    log_text += '  %s = %s\n' % (
                        field,
                        parameters[mode][field],
                    )

        _logger.info(log_text)
        return parameters

    # -------------------------------------------------------------------------
    # Button:
    # -------------------------------------------------------------------------
    @api.multi
    def button_load_tags(self):
        """ Load all tags from website
        """
        if self.mode == 'in':
            return self.env['wp.tag'].load_tags(connector=self)
        else:
            return self.env['wp.tag'].publish_tags(connector=self)

    @api.multi
    def button_load_attributes(self):
        """ Load all tags from website
        """
        if self.mode == 'in':
            return self.env['wp.attribute'].load_attributes(connector=self)
        else:
            pass  # TODO

    @api.multi
    def button_load_category(self):
        """ Load all category from website
        """
        if self.mode == 'in':
            return self.env['product.category'].load_category(connector=self)
        else:
            pass  # TODO

    @api.multi
    def button_load_product_template_structure(self):
        """ Load all product from website
        """
        if self.mode == 'in':
            return self.env['product.template'].\
                load_product_template_structure(connector=self)
        else:
            # TODO Manage export out data
            raise exceptions.Warning('Output not managed for now only input!')

    # -------------------------------------------------------------------------
    #                               COLUMNS:
    # -------------------------------------------------------------------------
    name = fields.Char(string='Name', required=True, size=50)
    company_id = fields.Many2one('res.company', 'Company', required=True)
    mode = fields.Selection([
        ('out', 'ODOO > WP'),
        ('in', 'WP > ODOO'),
        ], 'Mode', required=True, default='in',
        help='Tags, Attributes, Terms, Category, Products direction for sync'
             '(Order always vs ODOO)'
    )

    url = fields.Char('WP URL', size=180, required=True)
    key = fields.Char('WP consumer key', size=180, required=True)
    secret = fields.Char('WP consumer secret', size=180, required=True)

    api = fields.Boolean('WP API', default=True)
    version = fields.Char(
        'WP Version', size=10, default='wc/v3', required=True)

    image_path = fields.Char('Image path', size=180)
    image_extension = fields.Char('Image extension', size=5)
    timeout = fields.Integer('Timeout', default=600)

    # Publish setup:
    publish_product_block = fields.Integer('Publish product block', default=50)
    publish_variant_block = fields.Integer('Publish variant block', default=30)

    publish_text = fields.Boolean('Text data', default=True)
    publish_numeric = fields.Boolean('Numeric data', default=True)
    publish_variant = fields.Boolean('Product variant', default=True)
    publish_stock = fields.Boolean('Stock status', default=True)
    publish_price = fields.Boolean('Price', default=True)
    publish_category = fields.Boolean('Category', default=True)
    publish_tag = fields.Boolean('Tags', default=True)
    publish_attribute = fields.Boolean('Attributes', default=True)
    publish_default = fields.Boolean('Default attribute', default=True)
    publish_image = fields.Boolean('Image', default=True)
    publish_linked = fields.Boolean('Linked document', default=True)

    # Preload setup:
    update_attribute = fields.Boolean(
        'Update attribute and terms', default=True,
        help='Before import product update attribute and terms')
    update_category = fields.Boolean(
        'Update category', default=True, help='Before import category')
    update_tag = fields.Boolean(
        'Update tag', default=True, help='Before import product update tags')

    # album_ids = fields.Many2many(
    #    'product.image.album',
    #    'connector_album_rel', 'server_id', 'album_id', 'Album')


class WPConnectorProductRel(models.Model):
    """ Model name: Wordpress Connector product rel
    """
    _name = 'wp.connector.product.rel'
    _description = 'Wordpress Connector Product'
    _order = 'template_id'

    template_id = fields.Many2one(
        comodel_name='product.template',
        string='Template',
    )
    connector_id = fields.Many2one(
        comodel_name='wp.connector',
        string='Connector',
        required=True,
    )
    sku = fields.Char(
        string='Sku',
        readonly=True,
    )
    # TODO lang management here!
    wp_id = fields.Integer(
        string='WP ID',
        readonly=True,
    )


class ProductCategory(models.Model):
    """ Model name: Wordpress > Product Category
    """
    _inherit = 'product.category'
    _order = 'wp_sequence'  # Force sort

    @api.model
    def load_category(self, connector):
        """ Load category from Wordpress
        """
        # Load current category:
        connector_id = connector.id
        cache_category = {}  # From WP to ODOO
        pdb.set_trace()
        for category in self.search([('connector_id', '=', connector_id)]):
            cache_category[category.wp_id] = category
            # Used for parent_wp_id wp_id

        # ---------------------------------------------------------------------
        # Load category from WP
        # ---------------------------------------------------------------------
        wp_category = {}
        wcapi = connector.get_connector()
        params = {
            'per_page': 50,
            'page': 1,
            # 'order': 'asc',
            # 'orderby': 'id',
            }
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
                wp_category[record['id']] = record
        _logger.info('Category found # %s' % len(wp_category))
        pdb.set_trace()

        # ---------------------------------------------------------------------
        # Sort and create / update ODOO
        # ---------------------------------------------------------------------
        for wp_id in sorted(wp_category, key=lambda x: (
                wp_category[x]['parent'],
                wp_category[x]['id'])):
            record = wp_category[wp_id]
            name = record['name']
            description = record['description']
            parent_wp_id = record['parent'] or False
            sequence = record['menu_order']
            image = record['image']  # TODO

            if parent_wp_id and parent_wp_id not in cache_category:
                _logger.error('Parent not yet created for category: %s' % name)
                continue  # Not created
            parent = cache_category.get(parent_wp_id, False)
            if wp_id not in cache_category:  # Create (and cache element)
                cache_category[wp_id] = self.create({
                    'connector_id': connector.id,
                    'wp_id': wp_id,
                    'name': name,
                    'wp_description': description,
                    'parent_id': False if not parent else parent.id,
                    'wp_sequence': sequence,
                })

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    wp_id = fields.Integer(string='Wp ID', readonly=True)
    connector_id = fields.Many2one('wp.connector', 'Connector')
    wp_description = fields.Char('WP Description')
    wp_sequence = fields.Integer('Wp Sequence')
    # TODO Image


class ProductCategoryRelations(models.Model):
    """ Model name: Wordpress > Product Category
    """
    _inherit = 'product.category'

    wp_child_ids = fields.One2many(
        comodel_name='product.category',
        inverse_name='parent_id',
        string='WP Child')


class WPTag(models.Model):
    """ Model name: Wordpress Tag
    """
    _name = 'wp.tag'
    _description = 'Wordpress Tags'
    _order = 'name'

    @api.model
    def get_odoo_wp_data(self, connector):
        """ Prepare data for sync operation
            tags = ODOO tag records
            records_db = WP tag records
        """
        # Load current tags:
        tags = self.search([
            ('connector_id', '=', connector.id),
            ])

        wp_records = []
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
            wp_records.extend(records)
        return tags, wp_records

    @api.model
    def publish_tags(self, connector):
        """ Publish tags from Wordpress (out)
        """
        tags, wp_records = self.get_odoo_wp_data(connector)
        wcapi = connector.get_connector()

        command_data = {
            'create': [],
            'update': [],
            }
        pdb.set_trace()
        wp_ids = [record.id for record in wp_records]
        created_tags = {}  # Used for link wp create ID to ODOO
        for tag in tags:
            key = tag.name
            data = {
                'name': key,
                }
            wp_id = tag.wp_id
            if wp_id in wp_ids:  # Update tag name (if necessary)
                wp_ids.remove(wp_id)
                data['id'] = wp_id
                command_data['update'].append(data)
            else:
                command_data['create'].append(data)
                created_tags[key] = tag
        command_data['delete'] = wp_ids

        # Call Wordpress
        pdb.set_trace()
        try:
            reply = wcapi.post('products/tags/batch', command_data).json()
            # Update created ID:
            for record in reply.get('create', []):
                key = record['name']
                tag = created_tags.get(key)
                if not tag:
                    _logger.error('Tag %s in WP but no ref. in odoo' % key)
                # Update ODOO with new ID
                wp_id = record['wp_id']
                tag.write({
                    'wp_out_id': wp_id,
                    })
        except:
            _logger.error('Error updating Tags in Wordpress')

    @api.model
    def load_tags(self, connector):
        """ Load tags from Wordpress (in)
        """
        tags, wp_records = self.get_odoo_wp_data(connector)
        # tags.write({'removed': True})

        tags_db = {}
        for tag in tags:
            tags_db[tag.name] = tag.id

        for record in wp_records:
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
    wp_id = fields.Integer(string='Wp ID in', readonly=True)
    # wp_out_id = fields.Integer(string='Wp ID out', readonly=True)
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
                    attribute_id = attributes_db[name]
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
    wp_id = fields.Integer(string='Wp ID in', readonly=True)
    # wp_out_id = fields.Integer(string='Wp ID out', readonly=True)
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
    wp_id = fields.Integer(string='Wp ID in', readonly=True)
    # wp_out_id = fields.Integer(string='Wp ID out', readonly=True)
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
