# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import os
import sys
import logging
import woocommerce
import requests
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
    @api.multi
    def import_image_folder(self):
        """ Update image
        """
        return self.env['wp.image'].import_image_folder()

    @api.model
    def slugify(self, string):
        """ Slugify function
        """
        import unicodedata
        import re

        slug = unicodedata.normalize('NFKD', string)
        slug = slug.encode('ascii', 'ignore').lower()
        slug = re.sub(r'[^a-z0-9]+', '-', slug.decode('utf-8')).strip('-')
        slug = re.sub(r'[-]+', '-', slug)
        return slug

    @api.model
    def wordpress_read_all(self, endpoint, per_page=50):
        """ Read all table in Wordpress
            endpoint: url to get data
            per_page: Item per page limit
            @return: List of wordpress record
        """
        wp_records = []  # Returned list

        wcapi = self.get_connector()
        start_page = 1
        params = {'per_page': per_page, 'page': start_page}
        while True:
            _logger.info('Reading WP %s from %s [Record %s-%s]' % (
                endpoint,
                self.name,
                params['per_page'] * (params['page'] - 1),
                params['per_page'] * params['page'],
                ))
            reply = wcapi.get(endpoint, params=params)  # TODO put in a loop!!!
            params['page'] += 1
            if not reply.ok:
                _logger.error('Error: %s' % reply.text)
                break

            records = reply.json()
            # Add extra text for Wordpress problem:
            if not records or records[-1] in wp_records:
                break
            wp_records.extend(records)
            # break  # TODO remove!
        return wp_records

    """
            wp_id = record['id']
            slug = record['slug']
            name = record['name']
            images = record['images']
            regular_price = record['regular_price']
            price = record['price']
            sale_price = record['sale_price']
            weight = record['weight']
            product_type = record['type']
            if product_type != 'simple':
                pdb.set_trace()  # TODO debug problem
            description = record['description']
            stock_status = record['stock_status']
            status = record['status']
            tags = record['tags']
            attributes = record['attributes']
            categories = record['categories']
            upsell_ids = record['upsell_ids']
            cross_sell_ids = record['cross_sell_ids']
            related_ids = record['related_ids']  # Not used

            # -----------------------------------------------------------------
            # Prepare data:
            # -----------------------------------------------------------------
            # A. Fixed data:
            data = {
                'name': name,
                'wp_slug': slug,
                'wp_id_in': wp_id,
                'default_code': default_code,
                'wp_sku_in': sku,
                'lst_price': regular_price,
                'description_sale': description,
                'weight': weight,
            }

            # -----------------------------------------------------------------
            # Image download:
            # -----------------------------------------------------------------
            if image_download and image_path:
                if not sku:
                    print('   > Product %s without code!' % name)
                    continue  # No download image!

                counter = 0
                for image in images:
                    image_src = urllib.quote(image['src'].encode('utf8'), ':/')
                    # image_name = image['name']
                    # image_id = image['id']

                    urllib.urlretrieve(
                        image_src,
                        os.path.join(
                            image_path,
                            '%s.%03d.jpg' % (default_code, counter)))
                    counter += 1
            pass
        return True
        """

    @api.model
    def wordpress_batch_operation(self, batch_data, endpoint, max_block=100):
        """ Write in safe mode data on database with the limitation of batch
            operation.
            @return the list of record generated
        """
        wcapi = self.get_connector()
        wp_reply = {}
        counter = 0
        while True:
            counter += 1
            limit = max_block
            try:
                # Exit check:
                if not any(batch_data.values()):
                    _logger.warning('End of batch data, exit.')
                    break

                # Create block with limit:
                block_data = {}
                for key in batch_data:
                    if limit <= 0:
                        continue  # End max data updatable
                    block_data[key] = batch_data[key][:limit]
                    batch_data[key] = batch_data[key][limit:]

                    update_block = len(block_data[key])
                    limit -= update_block  # This block update counter
                    _logger.info('Block #%s >> %s, records: %s' % (
                        counter, key, update_block))

                # Generate return data:
                try:
                    reply = wcapi.post(endpoint, block_data).json()
                except:  # TODO Manage here post error?
                    _logger.error('Wordpress connect error: %s' % (
                        sys.exc_info(), ))
                    continue

                for key in reply:
                    if key not in wp_reply:
                        wp_reply[key] = []
                    wp_reply[key].extend(reply.get(key, []))
            except:
                _logger.error('Unmanaged error updating Wordpress:\n%s' % (
                    sys.exc_info(),
                ))
                pdb.set_trace()
        return wp_reply

    @api.model
    def get_connector(self):
        """ Connect with Word Press API management
        """
        connector = self[0]
        _logger.info('>>> Connecting: %s%s API: %s, timeout=%s' % (
            connector.url, connector.version, connector.api, connector.timeout,
            ))
        try:
            return woocommerce.API(
                url=connector.url, consumer_key=connector.key,
                consumer_secret=connector.secret, wp_api=connector.api,
                version=connector.version, timeout=connector.timeout,
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
            return self.env['wp.attribute'].publish_attributes(connector=self)

    @api.multi
    def button_load_category(self):
        """ Load all category from website
        """
        if self.mode == 'in':
            return self.env['product.category'].load_category(connector=self)
        else:
            return self.env['product.category'].publish_category(
                connector=self)

    @api.multi
    def button_load_product_template_structure(self):
        """ Load all product from website
        """
        if self.mode == 'in':
            return self.env['product.template'].\
                load_product_template_structure(connector=self)
        else:
            return self.env['product.template'].\
                publish_product_template(connector=self)

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

    # Woocommerce access:
    url = fields.Char('WP URL', size=180, required=True)
    key = fields.Char(
        'WP consumer key', size=180, required=True,
        help='Woocommerce API key')
    secret = fields.Char('WP consumer secret', size=180, required=True,
         help='Woocommerce API secret')

    # Normal API Access
    username = fields.Char(
        'WP username', size=80, help='Wordpress user access')
    password = fields.Char(
        'WP password', size=80, help='Wordpress user password')
    user_id = fields.Integer('WP user ID', help='ID for create media user')

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
    def publish_category_recursive(self, connector, wordpress, parent_ids):
        """ Recursive function for batch load category
            connector:
            parent_ids: list of parent ID
            done_ids: list of all record created (for final delete operation)
        """
        # ---------------------------------------------------------------------
        # Load current category level:
        # ---------------------------------------------------------------------
        if parent_ids:
            category_block = self.search([
                    ('connector_id', '=', connector.id),
                    ('parent_id', 'in', parent_ids),
                    ])
        else:
            category_block = self.search([
                    ('connector_id', '=', connector.id),
                    ('parent_id', '=', False),
                    ])

        if not category_block:
            return False  # End of recursion

        # ---------------------------------------------------------------------
        # Prepare Batch data for this level
        # ---------------------------------------------------------------------
        created_in_wp = {}  # New record created in this block
        batch_data = {'update': [], 'create': [], 'delete': []}
        parent_ids = []  # For next call recursion
        for category in category_block:
            try:
                parent_ids.append(category.id)  # For next recursion
                category_name = category.name
                wp_id = category.wp_id
                parent_wp_id = category.parent_id.wp_id or 0

                data = {
                    'name': category_name,
                    'parent': parent_wp_id,
                    'description': category.wp_description,
                    'menu_order': category.wp_sequence,
                }

                if not wp_id:  # Try to relink category:
                    wp_id = wordpress['name'].get(
                        (parent_wp_id, category_name))
                    category.write({'wp_id': wp_id})  # Update for next time

                if wp_id in wordpress['id']:  # Update tag name (if necessary)
                    wordpress['id'].remove(wp_id)
                    data['id'] = wp_id
                    batch_data['update'].append(data)
                else:
                    batch_data['create'].append(data)
                    created_in_wp[parent_wp_id, category_name] = category
            except:
                _logger.error('Error with wordpress:\n%s' % (
                    sys.exc_info(), ))
                continue

        # ---------------------------------------------------------------------
        # Write batch data in block on Wordpress:
        # ---------------------------------------------------------------------
        wp_reply = connector.wordpress_batch_operation(
            batch_data, 'products/categories/batch', max_block=100)

        # ---------------------------------------------------------------------
        # Update ODOO with created ID:
        # ---------------------------------------------------------------------
        for record in wp_reply.get('create', []):
            category_name = record['name']
            parent_id = record['parent']
            wp_id = record['id']

            category = created_in_wp.get((parent_id, category_name))
            if not category:  # Never happen!
                pdb.set_trace()
                _logger.error(
                    'Tag %s in WP but no ref. in odoo' % category_name)

            # Update ODOO with new ID
            try:
                category.write({'wp_id': wp_id})
            except:
                _logger.error('Error update odoo %s with WP %s' % (
                    category.id, wp_id))
        _logger.info('Category created # %s' % len(wp_reply.get('create', [])))
        return self.publish_category_recursive(
            connector, wordpress, parent_ids)

    @api.model
    def publish_category(self, connector):
        """ Publish category batch data
        """
        # ---------------------------------------------------------------------
        # Wordpress Read current situation:
        # ---------------------------------------------------------------------
        wordpress = {'name': {}, 'id': []}  # Use to get WP record by ID / name

        # Populate 2 database for sync operation:
        all_category = connector.wordpress_read_all(
            'products/categories', per_page=50)
        _logger.info('Worpress current category: # %s' % len(all_category))
        for record in all_category:
            key = (record['parent'], record['name'])
            wordpress['name'][key] = record['id']
            wordpress['id'].append(record['id'])

        self.publish_category_recursive(connector, wordpress, False)
        wp_delete_ids = wordpress['id']
        if not wp_delete_ids:
            _logger.info('No deletion on WP')
            return True

        try:
            wp_reply = connector.wordpress_batch_operation(
                {'delete': wp_delete_ids},
                'products/categories/batch',
                max_block=100)
            # TODO check reply?
            _logger.info('Delete reply: %s' % (wp_reply, ))
        except:
            _logger.error('Delete reply: %s' % (wp_reply, ))
        _logger.info('#%s deletion on WP' % len(wp_delete_ids))
        return True

    @api.model
    def load_category(self, connector):
        """ Load category from Wordpress
        """
        # Load current category:
        connector_id = connector.id
        cache_category = {}  # From WP to ODOO (only this connector)
        for category in self.search([('connector_id', '=', connector_id)]):
            cache_category[category.wp_id] = category
            # Used for parent_wp_id wp_id

        # ---------------------------------------------------------------------
        # Load category from WP
        # ---------------------------------------------------------------------
        # TODO change with: wordpress_read_all(self, endpoint, per_page=50)
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

            _logger.info('Create category: %s [%s]' % (name, parent_wp_id))
            if parent_wp_id and parent_wp_id not in cache_category:
                _logger.error('Parent not yet created for category: %s' % name)
                continue  # Not created
            parent = cache_category.get(parent_wp_id, False)
            data = {
                'connector_id': connector.id,
                'wp_id': wp_id,
                'name': name,
                'wp_description': description,
                'parent_id': False if not parent else parent.id,
                'wp_sequence': sequence,
            }
            if wp_id in cache_category:
                cache_category[wp_id].write(data)
            else:  # Create (and cache element)
                cache_category[wp_id] = self.create(data)

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
    def get_odoo_wp_data(self, connector, mode='in'):
        """ Prepare data for sync operation
            tags = ODOO tag records
            records_db = WP tag records
        """
        if mode == 'in':
            connector_field = 'connector_id'
        else:  # out
            connector_field = 'connector_out_id'

        # Load current tags:
        tags = self.search([
            (connector_field, '=', connector.id),
            ])

        wp_records = connector.wordpress_read_all('products/tags')
        return tags, wp_records

    @api.model
    def publish_tags(self, connector):
        """ Publish tags from Wordpress (out)
        """
        # ---------------------------------------------------------------------
        # Prepare batch call:
        # ---------------------------------------------------------------------
        tags, wp_records = self.get_odoo_wp_data(connector, mode='out')

        batch_data = {
            'create': [],
            'update': [],
            }
        wordpress = {
            'id': [record['id'] for record in wp_records],
            'name': [record['name'] for record in wp_records],
        }
        created_tags = {}  # Used for link wp create ID to ODOO
        for tag in tags:  # Tag name must be unique
            tag_name = tag.name
            data = {
                'name': tag_name,
                }
            wp_id = tag.wp_out_id

            # if no ID check also name for error during creation
            if wp_id not in wordpress['id']:  # Update tag name (if necessary)
                wp_id = 0

            if not wp_id and tag_name in wordpress['name']:
                tag.write({'wp_out_id': wp_id})  # Update for next time
                # Created but not referenced in ODOO
                wp_id = wordpress['name'][tag_name]

            if wp_id in wordpress['id']:  # Update tag name (if necessary)
                wordpress['id'].remove(wp_id)
                data['id'] = wp_id
                batch_data['update'].append(data)
            else:
                batch_data['create'].append(data)
                created_tags[tag_name] = tag
        batch_data['delete'] = wordpress['id']

        # ---------------------------------------------------------------------
        # Call Wordpress (block of N records)
        # ---------------------------------------------------------------------
        wp_reply = connector.wordpress_batch_operation(
            batch_data, 'products/tags/batch', max_block=100)

        # ---------------------------------------------------------------------
        # Update ODOO with created ID:
        # ---------------------------------------------------------------------
        for record in wp_reply.get('create', []):
            tag_name = record['name']
            tag = created_tags.get(tag_name)
            if not tag:  # Never happen!
                pdb.set_trace()
                _logger.error(
                    'Tag %s in WP but no ref. in odoo' % tag_name)

            # Update ODOO with new ID
            try:
                tag.write({'wp_out_id': record['id']})
            except:
                _logger.error('Error update odoo %s with WP %s' % (
                    tag.id, record['id']))
        _logger.info('Tags created # %s' % len(wp_reply.get('create', [])))

    @api.model
    def load_tags(self, connector):
        """ Load tags from Wordpress (in)
        """
        tags, wp_records = self.get_odoo_wp_data(connector, mode='in')

        tags_db = {}
        for tag in tags:
            tags_db[tag.wp_id] = tag

        for record in wp_records:
            wp_id = record['id']
            name = record['name']
            description = record['description']
            data = {
                'connector_id': connector.id,
                'wp_id': wp_id,
                'name': name,
                'description': description
                }
            if wp_id in tags_db:
                tags_db[wp_id].write(data)
            else:
                self.create(data)

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    name = fields.Char('Tag name', size=64, required=True)
    description = fields.Char('Description', size=80)
    wp_id = fields.Integer(string='Wp ID in', readonly=True)
    wp_out_id = fields.Integer(string='Wp ID out', readonly=True)
    connector_id = fields.Many2one('wp.connector', 'Connector in')
    connector_out_id = fields.Many2one('wp.connector', 'Connector out')
    unused = fields.Boolean('Removed', help='No more present on WP')


class WPAttribute(models.Model):
    """ Model name: Wordpress Attribute
    """
    _name = 'wp.attribute'
    _description = 'Wordpress Attribute'
    _order = 'name'

    @api.model
    def publish_attributes(self, connector):
        """ Publish attributes from Wordpress
        """
        # ---------------------------------------------------------------------
        # Wordpress Read current situation:
        # ---------------------------------------------------------------------
        wordpress = {'name': {}, 'id': []}  # Use to get WP record by ID / name
        # Populate 2 database for sync operation:
        all_attributes = connector.wordpress_read_all(
            'products/attributes', per_page=50)
        _logger.info('Worpress current attributes: # %s' % len(all_attributes))
        for record in all_attributes:
            wordpress['name'][record['name']] = record['id']
            wordpress['id'].append(record['id'])

        # Publish operation:
        batch_data = {
            'create': [],
            'update': [],
            }

        attributes = self.search([('connector_out_id', '=', connector.id)])

        created_attributes = {}  # Used for link wp create ID to ODOO
        for attribute in attributes:  # Attribute name must be unique
            attribute_name = attribute.name
            data = {
                'name': attribute_name,
                # 'slug': 'pa_%s' % connector.slugify(attribute_name),
                # 'type': 'select',
                # 'order_by': 'menu_order',
                # 'has_archives': False,
            }
            wp_id = attribute.wp_out_id

            # if no ID check also name for error during creation
            if wp_id not in wordpress['id']:  # Update tag name (if necessary)
                wp_id = 0

            if not wp_id and attribute_name in wordpress['name']:
                wp_id = wordpress['name'][attribute_name]
                attribute.write({'wp_out_id': wp_id})  # Update for next time

            if wp_id in wordpress['id']:  # Update tag name (if necessary)
                wordpress['id'].remove(wp_id)
                data['id'] = wp_id
                batch_data['update'].append(data)
            else:
                batch_data['create'].append(data)
                created_attributes[attribute_name] = attribute
        # TODO uncomment: batch_data['delete'] = wordpress['id']

        # ---------------------------------------------------------------------
        # Call Wordpress (block of N records)
        # ---------------------------------------------------------------------
        wp_reply = connector.wordpress_batch_operation(
            batch_data, 'products/attributes/batch', max_block=100)

        # ---------------------------------------------------------------------
        # Update ODOO with created ID:
        # ---------------------------------------------------------------------
        for record in wp_reply.get('create', []):
            if 'name' not in record:
                _logger.error('Attribute not created: %s' % (record, ))
                continue
            attribute_name = record['name']
            attribute = created_attributes.get(attribute_name)
            if not attribute:  # Never happen!
                pdb.set_trace()
                _logger.error(
                    'Attribute %s in WP but no ref. in odoo' % attribute_name)

            # Update ODOO with new ID
            try:
                attribute.write({'wp_out_id': record['id']})
            except:
                _logger.error('Error update odoo %s with WP %s' % (
                    attribute.id, record['id']))
        _logger.info('Tags created # %s' % len(wp_reply.get('create', [])))

        # Update terms for attributes yet sync:
        return self.publish_attribute_terms(connector)

    @api.model
    def publish_attribute_terms(self, connector):
        """ Publish attributes terms from Wordpress
            Sync before attributes with publish_attribute
        """
        # Loop on every attribute sync (before)
        connector_out_id = connector.id
        attributes = self.search([('connector_out_id', '=', connector_out_id)])
        for attribute in attributes:
            wp_attribute_id = attribute.wp_out_id

            # -----------------------------------------------------------------
            # Wordpress Read current situation:
            # -----------------------------------------------------------------
            wordpress = {'name': {}, 'id': []}  # Use to get WP record ID/name
            # Populate 2 database for sync operation:
            all_terms = connector.wordpress_read_all(
                'products/attributes/%s/terms' % wp_attribute_id, per_page=50)
            _logger.info('Worpress current terms: # %s' % len(all_terms))
            for record in all_terms:
                wordpress['name'][record['name']] = record['id']
                wordpress['id'].append(record['id'])

            # Publish operation:
            batch_data = {
                'create': [],
                'update': [],
                }

            created_terms = {}  # Used for link wp create ID to ODOO
            for term in attribute.term_ids:  # Terms name must be unique
                term_name = term.name
                data = {
                    'name': term_name,
                    'type': 'select',
                    # 'description': term.description,
                    # 'slug': 'pa_%s' % connector.slugify(attribute_name),
                    # 'menu_order',
                }
                wp_id = term.wp_out_id

                # if no ID check also name for error during creation
                if wp_id not in wordpress['id']:  # Check if exist
                    wp_id = 0

                if not wp_id and term_name in wordpress['name']:
                    wp_id = wordpress['name'][term_name]
                    term.write({'wp_out_id': wp_id})  # For next time

                if wp_id in wordpress['id']:  # Update tag name (if necessary)
                    wordpress['id'].remove(wp_id)
                    data['id'] = wp_id
                    batch_data['update'].append(data)
                else:
                    batch_data['create'].append(data)
                    created_terms[term_name] = term
            batch_data['delete'] = wordpress['id']

            # -----------------------------------------------------------------
            # Call Wordpress (block of N records)
            # -----------------------------------------------------------------
            wp_reply = connector.wordpress_batch_operation(
                batch_data,
                'products/attributes/%s/terms/batch' % wp_attribute_id,
                max_block=100)

            # -----------------------------------------------------------------
            # Update ODOO with created ID:
            # -----------------------------------------------------------------
            for record in wp_reply.get('create', []):
                if 'name' not in record:
                    _logger.error('Term not created: %s' % (record, ))
                    continue
                term_name = record['name']
                term = created_terms.get(term_name)
                if not term:  # Never happen!
                    pdb.set_trace()
                    _logger.error(
                        'Tag %s in WP but no ref. in odoo' % term_name)

                # Update ODOO with new ID
                try:
                    term.write({'wp_out_id': record['id']})
                except:
                    _logger.error('Error update odoo %s with WP %s' % (
                        term.id, record['id']))
            _logger.info('Term created # %s' % len(wp_reply.get('create', [])))
        return True

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
            wp_id = attribute.wp_id
            attributes_db[wp_id] = attribute
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
                data = {
                    'connector_id': connector.id,
                    'wp_id': wp_id,
                    'name': name,
                    }
                if wp_id in attributes_db:
                    _logger.info('Update: %s' % name)
                    attributes_db[wp_id].write(data)
                    attribute_id = attributes_db[wp_id].id
                else:
                    _logger.info('Create: %s' % name)
                    attribute_id = self.create(data).id

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
    connector_id = fields.Many2one('wp.connector', 'Connector in')
    connector_out_id = fields.Many2one('wp.connector', 'Connector out')
    wp_id = fields.Integer(string='Wp ID in', readonly=True)
    wp_out_id = fields.Integer(string='Wp ID out', readonly=True)
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
    wp_out_id = fields.Integer(string='Wp ID out', readonly=True)
    attribute_id = fields.Many2one('wp.attribute', 'Attribute')
    connector_id = fields.Many2one(
        'wp.connector', 'Connector',
        related='attribute_id.connector_id')
    # connector_out_id = fields.Many2one(
    #     'wp.connector', 'Connector',
    #     related='attribute_id.connector_out_id')


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


class WPConnector(models.Model):
    """ Model name: Wordpress Connector
    """
    _name = 'wp.image'
    _description = 'Wordpress Image'
    _order = 'name'

    @api.multi
    def update_this_wordpress_media(self):
        """ Update this
        """
        self.with_context(update_this_id=self.id).update_wordpress_media()

    @api.model
    def update_wordpress_media(self):
        """ Update worpress image (use check for get list)
        """
        update_this_id = self.env.context.get('update_this_id')
        if update_this_id:  # Update forced:
            images = self.browse(update_this_id)
        else:  # Update all marked:
            images = self.search([('update', '=', True)])

        product_ids = []  # Product list to update
        for image in images:
            wp_id = image.wp_id
            product_id = image.product_id.id
            product_ids.append(product_id)
            connector = image.connector_id

            root_url = connector.url
            username = connector.username
            password = connector.password
            author_id = connector.user_id
            auth = (username, password)
            url = '%s/wp-json/wp/v2/media' % root_url

            # -----------------------------------------------------------------
            # Delete old:
            # -----------------------------------------------------------------
            if wp_id:  # Delete previous:
                delete_url = '%s/wp-json/wp/v2/media/%s' % (root_url, wp_id)
                params = {
                    'force': True,
                }
                reply = requests.delete(
                    delete_url,
                    # headers=headers
                    params=params,
                    auth=auth,
                )
                _logger.info(reply.text)

            # -----------------------------------------------------------------
            # Load new:
            # -----------------------------------------------------------------
            fullname = image.fullname

            headers = {
                'Content-Type': 'image/jpg',
                'Content-Disposition': 'attachment; filename="%s"' % fullname,
            }

            params = {
                'lang': 'it',
                'title': image.name,
                'status': 'publish',
                'author': author_id,
                'alt_text': image.product_id.name,
                'caption': image.product_id.name,
                'description': image.product_id.wp_description or '',
            }

            # Open file in different ways:
            file_handler = open(fullname, 'rb')  # handler
            image_data = file_handler.read()  # binary data

            reply = requests.post(
                url,
                headers=headers,
                params=params,
                data=image_data,
                auth=auth,
            )
            try:
                reply_json = reply.json()
                wp_id = reply_json['id']
                image_url = reply_json['source_url']
            except:  # Error reply
                _logger.error(reply.text)
                continue

            image.write({
                'update': False,
                'wp_id': wp_id,
                'wp_url': image_url,
            })

        # ---------------------------------------------------------------------
        # Update product selected in the images
        # ---------------------------------------------------------------------
        # TODO
        return True

    @api.multi
    def import_image_folder(self):
        """ Load image folder in connector param from all out connector
        """
        connector_pool = self.env['wp.connector']
        product_pool = self.env['product.template']

        connectors = connector_pool.search([('mode', '=', 'out')])
        if not connectors:
            _logger.error('No connector for out wordpress')
            return False
        for connector in connectors:
            connector_id = connector.id
            image_path = connector.image_path

            for root, folders, files in os.walk(image_path):
                for filename in files:
                    fullname = os.path.join(root, filename)

                    images = self.search([
                        ('name', '=', filename),
                        ('connector_id', '=', connector_id),
                    ])
                    reply = self.extract_data(filename)
                    if not reply:
                        _logger.error('Format file error: %s' % fullname)
                        return

                    product_id, version, extension = reply
                    modify_time = str(os.stat(fullname).st_mtime)
                    if images:  # only one!
                        # Check timestamp
                        if images[0].timestamp != modify_time:
                            data = {
                                'update': True,
                                'timestamp': modify_time,
                            }
                            try:
                                images.write(data)
                            except:
                                _logger.error(
                                    'No product ID for upd. %s' % fullname)

                    else:
                        data = {
                            'update': True,
                            'name': filename,
                            'product_id': product_id,
                            'version': version,
                            'connector_id': connector_id,
                            'timestamp': modify_time,
                            'wp_id': False,
                            'wp_url': False,
                        }
                        template = product_pool.search([
                            ('id', '=', product_id)])
                        if template:
                            self.create(data)
                            _logger.info('Product linked %s' % fullname)
                        else:
                            _logger.error('No product ID for %s' % fullname)
                break  # Only this
        return self.update_wordpress_media()

    @api.model
    def extract_data(self, filename):
        """ Extract data from filename
        """
        file_part = filename.split('.')
        if len(file_part) != 3:
            return False
        else:
            # template id, version, extension:
            return int(file_part[0]), file_part[1], file_part[2]

    @api.multi
    def _get_fullname(self):
        """ Extract fullname from connector and filename
        """
        for image in self:
            image.fullname = os.path.join(
                image.connector_id.image_path, image.name)

    # Columns:
    name = fields.Char(string='Name', required=True, size=80)
    fullname = fields.Char(
        string='Fullname', size=280, compute='_get_fullname')
    update = fields.Boolean('To update')

    version = fields.Char(string='Version')
    timestamp = fields.Char(string='Timestamp')
    connector_id = fields.Many2one(
        comodel_name='wp.connector',
        string='Connector')
    product_id = fields.Many2one(
        comodel_name='product.template',
        string='Product')
    wp_id = fields.Integer('WP ID')
    wp_url = fields.Char('WP Url')


class ProductTemplate(models.Model):
    """ Model name: Product template
    """
    _inherit = 'product.template'

    wp_image_ids = fields.One2many(
        comodel_name='wp.image',
        inverse_name='product_id',
        string='Wordpress image')
