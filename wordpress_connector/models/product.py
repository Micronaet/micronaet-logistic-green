# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import os
import sys
import logging
import base64
import pdb
from urllib.request import urlretrieve
from urllib.parse import quote
from odoo import models, fields, api, exceptions

_logger = logging.getLogger(__name__)


class WpProductAttribute(models.Model):
    """ Attribute linked to product (with terms)
    """
    _name = 'wp.product.attribute'
    _description = 'Product attributes'
    _rec_name = 'attribute_id'

    # Columns:
    product_id = fields.Many2one('product.template', 'Product')
    attribute_id = fields.Many2one('wp.attribute', 'Attribute')
    show_product_page = fields.Boolean(
        'Show', help='Show in product page')
    used_in_variant = fields.Boolean(
        'Variant', help='Used in product variant setup')
    position = fields.Integer('Seq.')

    term_ids = fields.Many2many(
        comodel_name='wp.attribute.term',
        string='Terms available',
        column1='attribute_id',
        column2='term_id',
        domain="[('attribute_id', '=', attribute_id)]",
    )


class ProductTemplate(models.Model):
    """ Model name: Product Template
    """
    _inherit = 'product.template'

    # -------------------------------------------------------------------------
    #                               UTILITY:
    # -------------------------------------------------------------------------
    @api.model
    def clean_code(self, sku):
        """ Split and Clean code extracting from original sky
        """
        sku = (sku or '').strip()

        if len(sku) == 13 and sku.isdigit():
            ean13 = sku
        else:
            ean13 = ''

        sku_part = sku.split('-')
        code = sku_part[0]
        supplier = ''
        child = ''
        if len(sku_part) > 1:
            supplier = sku_part[1].upper()
            if len(supplier) > 2:
                if supplier[2:3].isalpha():
                    child = supplier[2:]
                    supplier = supplier[:2]
                else:
                    child = supplier[3:]
                    supplier = supplier[:3]
            else:
                child = supplier[3:]
                supplier = supplier[:3]

        if child:
            try:
                code = '%s_%02d' % (
                    code,
                    ord(child) - 64,
                )
            except:
                code = 'ERR'
        return sku, code, supplier, child, ean13

    @api.multi
    def update_product_supplier(self):
        """ Integration of supplier, taken from sku extra code
        """
        self.ensure_one()

        # Pool used:
        partner_pool = self.env['res.partner']
        supplinfo_pool = self.env['product.supplierinfo']

        if self.seller_ids:
            return True  # TODO check if it's present!

        # ---------------------------------------------------------------------
        # Update supplier for product:
        # ---------------------------------------------------------------------
        sku = self.sku_in
        sku, code, supplier, child, ean13 = self.clean_code(sku)
        if not sku or not supplier:
            _logger.error('Supplier not update, missed sku or supplier [%s]!' %
                          self.name)
            return False

        suppliers = partner_pool.search([
            ('ref', '=', supplier),
            ])
        if not suppliers:
            _logger.error('Supplier [%s] not found for product: %s!' % (
                supplier,
                self.name))
            return False

        supplinfo_pool.create({
            'name': suppliers[0].id,
            'product_tmpl_id': self.id,
            'min_qty': 1,
            'price': 0.0,  # TODO add supplier price
        })

    @api.model
    def get_sku(self, record):
        """ """
        return record['sku'] or 'id_%s' % record['id']

    @api.model
    def get_odoo_sku(self, record):
        """ """
        return record.sku_out or record.sku_in or ('id_%s' % record.id)

    @api.model
    def publish_product_template(self, connector):
        """ Publish all product on out WP
        """
        # ---------------------------------------------------------------------
        # Wordpress Read current situation:
        # ---------------------------------------------------------------------
        wordpress = {'sku': {}, 'id': []}  # Use to get WP record by ID / name
        # Populate 2 database for sync operation:
        all_products = connector.wordpress_read_all(
            'products', per_page=50)
        _logger.info('Worpress current product: # %s' % len(all_products))
        for record in all_products:
            wordpress['sku'][self.get_sku(record)] = record['id']
            wordpress['id'].append(record['id'])

        # Publish operation:
        batch_data = {
            'create': [],
            'update': [],
            }

        products = self.search([('wp_connector_out_id', '=', connector.id)])
        products = products[0:4]  # TODO Demo
        pdb.set_trace()

        created_products = {}  # Used for link wp create ID to ODOO
        for product in products:  # Attribute name must be unique
            product_sku = self.get_odoo_sku(product)
            data = {
                'sku': product_sku,
                'name': product.name,
                # TODO:
            }
            wp_id = product.wp_id_out

            # if no ID check also name for error during creation
            if wp_id not in wordpress['id']:  # Update tag name (if necessary)
                wp_id = 0

            if not wp_id and product_sku in wordpress['sku']:
                wp_id = wordpress['sku'][product_sku]
                products.write({'wp_id_out': wp_id})  # Update for next time

            if wp_id in wordpress['id']:  # Update tag name (if necessary)
                wordpress['id'].remove(wp_id)
                data['id'] = wp_id
                batch_data['update'].append(data)
            else:
                batch_data['create'].append(data)
                created_products[product_sku] = product
        batch_data['delete'] = wordpress['id']

        # ---------------------------------------------------------------------
        # Call Wordpress (block of N records)
        # ---------------------------------------------------------------------
        wp_reply = connector.wordpress_batch_operation(
            batch_data, 'products/batch', max_block=100)

        # ---------------------------------------------------------------------
        # Update ODOO with created ID:
        # ---------------------------------------------------------------------
        for record in wp_reply.get('create', []):
            if 'sku' not in record:
                _logger.error('Product not created: %s' % (record, ))
                continue
            product_sku = record['sku']
            product = created_products.get(product_sku)
            if not product:  # Never happen!
                pdb.set_trace()
                _logger.error(
                    'Product %s in WP but no ref. in odoo' % product_sku)

            # Update ODOO with new ID
            try:
                product.write({'wp_id_out': record['id']})
            except:
                _logger.error('Error update odoo %s with WP %s' % (
                    product.id, record['id']))
        _logger.info('Product created # %s' % len(wp_reply.get('create', [])))

        return self.publish_product_variant(connector)

    @api.model
    def publish_product_variant(self, connector):
        """ Publish product variant from Wordpress
        """
        # Loop on every attribute sync (before)
        connector_out_id = connector.id
        masters = self.search([
            ('wp_connector_out_id', '=', connector_out_id),
            ('wp_master', '=', True),
        ])
        masters = masters[0:2]  # TODO Demo
        for master in masters:
            wp_master_id = master.wp_id_out

            # -----------------------------------------------------------------
            # Wordpress Read current situation:
            # -----------------------------------------------------------------
            wordpress = {'sku': {}, 'id': []}  # Use to get WP record ID/name
            # Populate 2 database for sync operation:
            all_variants = connector.wordpress_read_all(
                'products/products/%s/variations' % wp_master_id, per_page=50)
            _logger.info('Worpress current variants: # %s' % len(all_variants))
            for record in all_variants:
                wordpress['sku'][self.get_sku(record)] = record['id']
                wordpress['id'].append(record['id'])

            # Publish operation:
            batch_data = {
                'create': [],
                'update': [],
                }

            created_terms = {}  # Used for link wp create ID to ODOO
            # Attribute name must be unique
            for variation in master.wp_slave_ids:
                variation_sku = self.get_odoo_sku(variation)
                data = {
                    'sku': variation_sku,
                    # 'description': term.description,
                    # 'slug': 'pa_%s' % connector.slugify(attribute_name),
                    # 'menu_order',
                    # TODO
                }
                wp_id = variation.wp_id_out

                # if no ID check also name for error during creation
                if wp_id not in wordpress['id']:  # Check if exist
                    wp_id = 0

                if not wp_id and variation_sku in wordpress['sku']:
                    wp_id = wordpress['sku'][variation_sku]
                    variation.write({'wp_id_out': wp_id})  # For next time

                if wp_id in wordpress['id']:  # Update tag name (if necessary)
                    wordpress['id'].remove(wp_id)
                    data['id'] = wp_id
                    batch_data['update'].append(data)
                else:
                    batch_data['create'].append(data)
                    created_terms[variation_sku] = variation
            batch_data['delete'] = wordpress['id']

            # -----------------------------------------------------------------
            # Call Wordpress (block of N records)
            # -----------------------------------------------------------------
            # TODO update attribute for variation:

            wp_reply = connector.wordpress_batch_operation(
                batch_data,
                'products/%s/variations/batch' % wp_master_id,
                max_block=100)

            # TODO update default variation for product (if need)

            # -----------------------------------------------------------------
            # Update ODOO with created ID:
            # -----------------------------------------------------------------
            for record in wp_reply.get('create', []):
                if 'sku' not in record:
                    _logger.error('Variation not created: %s' % (record, ))
                    continue
                variation_sku = record['sku']
                variation = created_terms.get(variation_sku)
                if not variation:  # Never happen!
                    pdb.set_trace()
                    _logger.error(
                        'Variation %s in WP but no ref. odoo' % variation_sku)

                # Update ODOO with new ID
                try:
                    variation.write({'wp_id_out': record['id']})
                except:
                    _logger.error('Error update odoo %s with WP %s' % (
                        variation.id, record['id']))
            _logger.info('Variation created # %s' % len(
                wp_reply.get('create', [])))
        return True

    @api.model
    def load_product_template_structure(self, connector):
        """ Load product template from Wordpress
            (procedure launch from connector button for now)
        """
        # Company parameters:
        if self.env.user.company_id.wp_connector_in_id != connector:
            raise exceptions.Warning(
                'Cannot import connector that is different from company in '
                'parameter')

        # Connector parameters:
        image_path = connector.image_path
        connector_id = connector.id
        parameters = connector.get_publish_parameters()

        # Wordpress parameters:
        wcapi = connector.get_connector()
        # Product:
        params = {
            'per_page': parameters['block']['product'],
            'page': 1,
        }
        # Variation:
        variation_param = {
            'per_page': parameters['block']['variant'],
            'page': 1,
        }

        # ---------------------------------------------------------------------
        # Preload:
        # ---------------------------------------------------------------------
        # NOTE: No preload parameters for get (only for publish):
        # Tag:
        tag_list = {}
        for tag in self.env['wp.tag'].search([
                ('connector_id', '=', connector_id),
                ]):
            tag_list[tag.name] = tag.id

        # Category:
        category_list = {}
        for category in self.env['product.category'].search([
                ('connector_id', '=', connector_id),
                ('wp_id', '!=', False),
                ]):
            category_list[category.wp_id] = category.id

        attribute_list = {}
        for attribute in self.env['wp.attribute'].search([
                ('connector_id', '=', connector_id),
                ]):
            attribute_list[attribute.wp_id] = [
                attribute.id,
                {item.name: item.id for item in attribute.term_ids},
                ]

        # Load and save in a file:
        image_list = []

        # Linked relation:
        product_connection = {
            'wp_linked_ids': [],
            'wp_up_sell_ids': [],
            'wp_cross_sell_ids': [],
            }
        pdb.set_trace()
        while True:
            reply = wcapi.get('products', params=params)
            _logger.info('Page %s, Record: %s' % (
                params['page'], params['page'] * params['per_page']))
            params['page'] += 1

            # Loop stop check:
            if not reply.ok:
                _logger.error('Error getting product list %s' % (reply, ))
                break
            records = reply.json()
            if not records:
                break

            # Loop all master product:
            for record in records:
                # Extract data from record:
                wp_id_in = record['id']
                real_sku = record['sku']
                name = record['name']
                # slug = record['slug']
                # stock_status = record['stock_status']

                images = record['images']
                variations = record['variations']

                related_ids = record['related_ids']
                up_sell_ids = record['upsell_ids']
                cross_sell_ids = record['cross_sell_ids']

                tags = record['tags']
                categories = record['categories']

                attributes = record['attributes']
                default_attributes = record['default_attributes']

                # Clean sku for default_code
                sku, default_code, supplier, child, barcode = \
                    self.clean_code(real_sku)

                # ODOO search:
                # TODO save original sku?
                products = self.search([
                    # TODO sku is not saved in default_code!!! 0001-02 >> 0001
                    # ('connector_id', '=', connector_id),  # Used Company IN
                    '|',
                    ('wp_id_in', '=', wp_id_in),
                    ('default_code', '=', sku),
                    ])
                create_mode = False if products else True
                if len(products) > 1:
                    _logger.error('Multi ID or SKU present: %s' % sku)
                    pdb.set_trace()
                    # TODO use only first?
                    # products = product[0]

                # -------------------------------------------------------------
                # Prepare data (use publish setup):
                # -------------------------------------------------------------
                data = {
                    # 'connector_id': connector_id,  # Not used
                    # 'wp_sku': sku,
                    'wp_published': True,  # TODO remove from here
                    'wp_id_in': wp_id_in,
                    'default_code': sku,
                    'sku_in': sku,

                    'wp_type': record['type'],
                    'wp_status': record['status'],
                }

                if create_mode or parameters['publish']['text']:
                    data.update({
                        'name': name,
                        'description_sale': record['description'],
                    })

                if create_mode or parameters['publish']['numeric']:
                    data.update({
                        'weight': record['weight'],
                    })

                if create_mode or parameters['publish']['price']:
                    data.update({
                        'lst_price': record['regular_price'],
                    })

                if barcode:
                    data['barcode'] = barcode

                if variations:
                    data['wp_master'] = True
                else:
                    data['wp_master'] = False

                # Relation / Complex fields:
                if (create_mode or parameters['publish']['tag']) and tags:
                    data['wp_tag_ids'] = [(6, 0, [])]
                    for tag in tags:
                        if tag['name'] in tag_list:
                            data['wp_tag_ids'][0][2].append(
                                tag_list[tag['name']])

                if (create_mode or parameters['publish']['category']) and \
                        categories:
                    data['wp_category_ids'] = [(6, 0, [])]
                    for category in categories:
                        data['wp_category_ids'][0][2].append(
                            category_list[category['id']])

                if create_mode:
                    _logger.info(
                        'Create product %s [%s]' % (default_code, sku))
                    products = self.create(data)
                else:
                    _logger.info(
                        'Update product %s [%s]' % (default_code, sku))
                    products.write(data)
                product_id = products[0].id
                products.update_product_supplier()

                # -------------------------------------------------------------
                # Complex fields:
                # -------------------------------------------------------------
                # Attributes:
                if (create_mode or parameters['publish']['attribute']) and \
                        attributes:
                    wp_attribute_ids = []
                    products.write({'wp_attribute_ids': [(5, 0, 0)]})
                    for attribute in attributes:
                        attribute_odoo_id, attribute_odoo_terms = \
                            attribute_list[attribute['id']]

                        current_term_ids = [attribute_odoo_terms[option]
                                            for option in attribute['options']
                                            if option in attribute_odoo_terms]
                        wp_attribute_ids.append((0, 0, {
                            'attribute_id': attribute_odoo_id,
                            'term_ids': [(6, 0, current_term_ids)],
                            'show_product_page': attribute['visible'],
                            'used_in_variant': attribute['variation'],
                            'position': attribute['position']
                            }))
                    products.write({'wp_attribute_ids': wp_attribute_ids})

                if parameters['publish']['image']:
                    image_list.append((product_id, images))

                if parameters['publish']['linked']:
                    if related_ids:
                        product_connection['wp_linked_ids'].append(
                            (products[0], related_ids))

                    if up_sell_ids:
                        product_connection['wp_up_sell_ids'].append(
                            (products[0], up_sell_ids))

                    if cross_sell_ids:
                        product_connection['wp_cross_sell_ids'].append(
                            (products[0], cross_sell_ids))

                # -------------------------------------------------------------
                #                        VARIATIONS
                # -------------------------------------------------------------
                if parameters['publish']['linked'] and variations:
                    variation_param['page'] = 1
                    while True:
                        var_reply = wcapi.get(
                            'products/%s/variations' % wp_id_in,
                            params=variation_param,
                            )
                        variation_param['page'] += 1

                        if not var_reply.ok:
                            _logger.error(
                                'Error getting category list', var_reply)
                            break
                        variants = var_reply.json()
                        if not variants:
                            break

                        for variant in variants:
                            variant_id = variant['id']
                            variant_sku = variant['sku']
                            variant_images = variant['image']
                            variant_attributes = variant['attributes']
                            # stock_status = variant['stock_status']
                            # product_type = variant['type']
                            # status = variant['status']

                            if parameters['publish']['image'] and \
                                    variant_images:
                                # Usually one:
                                image_list.append(
                                    (variant.id, [variant_images]))

                            variant_data = {
                                # 'connector_id': connector_id,
                                # 'wp_sku': variant_sku,
                                'wp_type': 'variable',
                                'wp_published': True,
                                'name': name,
                                'wp_id_in': variant['id'],
                                'sku_in': variant_sku,
                                'default_code': variant_sku,
                                'lst_price': variant['regular_price'],
                                'description_sale': variant['description'],
                                'weight': variant['weight'],
                                'wp_master_id': product_id,
                                }

                            # TODO Publish block also here!

                            odoo_variants = self.search([
                                '|',
                                ('wp_id_in', '=', variant_id),  # never overlap
                                ('default_code', '=', variant_sku),
                                ])

                            if odoo_variants:
                                if len(odoo_variants) > 1:
                                    _logger.error('Double variant found %s' % (
                                        variant_sku,
                                    ))
                                    pdb.set_trace()
                                    odoo_variants = odoo_variants[0]

                                odoo_variants.write(variant_data)
                                _logger.info(
                                    '   >> Update %s variants' % variant_sku)
                            else:
                                odoo_variants = self.create(variant_data)
                                _logger.info(
                                    '   >> Create %s variants' % variant_sku)
                            odoo_variants.update_product_supplier()

                            # -------------------------------------------------
                            # Update Variant attributes:
                            # -------------------------------------------------
                            print(products.default_code, '\n\n\n\n')
                            # Delete all previous:
                            odoo_variants.write(
                                {'wp_attribute_ids': [(5, 0, 0)]})

                            wp_attribute_ids = []
                            for item in variant_attributes:
                                attribute_odoo_id, attribute_odoo_terms = \
                                    attribute_list[item['id']]
                                wp_attribute_ids.append((0, 0, {
                                    'attribute_id': attribute_odoo_id,
                                    'term_ids': [
                                        (6, 0, [attribute_odoo_terms[
                                            item['option']]])],
                                }))
                            odoo_variants.write(
                                {'wp_attribute_ids': wp_attribute_ids})
            break  # TODO Test mode:

        # ---------------------------------------------------------------------
        # Image download:
        # ---------------------------------------------------------------------
        if parameters['publish']['image']:
            _logger.warning('Updating %s images' % len(image_list))
            for reference_id, images in image_list:
                counter = -1
                for image in images:
                    counter += 1
                    image_src = quote(
                        image['src'].encode('utf8'), ':/')
                    # TODO change with new syntax:
                    filename = '%s.%03d.jpg' % (
                        reference_id,
                        counter,
                    )

                    fullname = os.path.join(image_path, filename)
                    if not os.path.isfile(fullname):
                        urlretrieve(image_src, fullname)
                        _logger.info(
                            '  >> Get image saved as %s' % filename)

        # ---------------------------------------------------------------------
        # Related download:
        # ---------------------------------------------------------------------
        if parameters['publish']['linked']:
            for field in product_connection:
                _logger.warning('Updating %s related # %s' % (
                    field,
                    len(product_connection[field]),
                    ))
                for product, item_ids in product_connection[field]:
                    related_products = self.search([
                        # TODO change with new syntax:
                        ('wp_id_in', 'in', item_ids),
                        ])
                    if related_products:
                        product.write({
                            field: [(6, 0, related_products.mapped('id'))]
                            })

    # -------------------------------------------------------------------------
    #                                FIELD FUNCTION:
    # -------------------------------------------------------------------------
    @api.multi
    def _get_wp_image_file(self):
        """ Return image loading from file:
        """
        connector = self[0].wp_connector_in_id
        path = connector.image_path
        extension = connector.image_extension or 'jpg'

        for product in self:
            if not path:
                product.wp_image = False
                _logger.error('Missed path, check connector parameter')
                continue
            filename = os.path.join(
                path,
                #  Default image is .000
                '{}.000.{}'.format(
                    product.id,
                    extension,
                    ),
                )
            try:
                f_data = open(filename, 'rb')
                product.wp_image = base64.encodebytes(f_data.read())
                f_data.close()
                _logger.info('Image present: {}'.format(filename))
            except:
                product.wp_image = False
                _logger.error('Image not present: {}'.format(filename))

    # -------------------------------------------------------------------------
    #                            Compute function:
    # -------------------------------------------------------------------------
    # wp_id
    @api.multi
    @api.depends(
        'company_id.wp_connector_in_id', 'company_id.wp_connector_out_id',
        # 'wp_connector_rel_ids.wp_id',
    )
    def _get_wp_id_in_and_out(self):
        """ Compute ID from sub element and setup in company
        """
        _logger.warning('Reading related field and update in template...')
        for template in self:
            connector_in_id = template.wp_connector_in_id
            connector_out_id = template.wp_connector_out_id
            wp_id_in = wp_id_out = False
            sku_in = sku_out = False

            for line in template.wp_connector_rel_ids:
                wp_id = line.wp_id
                sku = line.sku
                if line.connector_id == connector_in_id:
                    wp_id_in = wp_id
                    sku_in = sku
                if line.connector_id == connector_out_id:
                    wp_id_out = wp_id
                    sku_out = sku

            # Update multi fields:
            template.wp_id_in = wp_id_in
            template.wp_id_out = wp_id_out
            template.sku_in = sku_in
            template.sku_out = sku_out

        _logger.warning('Field updated in template!')

    # -------------------------------------------------------------------------
    #                          Save inverse part:
    # -------------------------------------------------------------------------
    # Inverse function (generic for both):
    def _save_field_in_and_out(self, field, value, direction):
        """ Inverse function for create sub record (used for both fields
        """
        self.ensure_one()
        _logger.warning('Updating {} in correct connector [{}]...'.format(
            field, direction))

        rel_pool = self.env['wp.connector.product.rel']
        template = self

        if direction == 'in':
            connector_id = template.wp_connector_in_id
        else:
            connector_id = template.wp_connector_out_id

        if not connector_id:
            return _logger.error(
                'Cannot create {}}, setup the connector in company before'
                'direction [{}]'.format(field, direction))

        for line in template.wp_connector_rel_ids:
            if line.connector_id == connector_id:
                line_found = line
                break
        else:
            line_found = False

        # Insert management:
        if line_found:  # Update:
            line_found.write({
                field: value,
            })
        else:  # Create line:
            rel_pool.create({
                'template_id': template.id,
                'connector_id': connector_id.id,
                field: value,
            })

    # inverse function:
    def _save_wp_id_in(self):
        return self._save_field_in_and_out(
            'wp_id', self.wp_id_in, direction='in')

    def _save_wp_id_out(self):
        return self._save_field_in_and_out(
            'wp_id', self.wp_id_out, direction='out')

    def _save_sku_in(self):
        return self._save_field_in_and_out(
            'sku', self.sku_in, direction='in')

    def _save_sku_out(self):
        return self._save_field_in_and_out(
            'sku', self.sku_out, direction='out')

    # wp_id search
    def get_field_filter(self, operator, value, mode, field):
        """ Search function for wp_id out
        """
        rel_pool = self.env['wp.connector.product.rel']
        company_pool = self.env['res.company']
        company = company_pool.search([])[0]
        if mode == 'in':
            connector_id = company.wp_connector_in_id.id
        else:
            connector_id = company.wp_connector_out_id.id

        records = rel_pool.search([
            ('connector_id', '=', connector_id),
            (field, operator, value),
        ])
        if records:
            return [
                ('id', 'in', [record.template_id.id for record in records])
            ]
        else:
            return [('id', '=', False)]  # Nothing

    def _search_wp_id_in(self, operator, value):
        """ Search function for wp_id out
        """
        return self.get_field_filter(
            operator, value, mode='in', field='wp_id')

    def _search_wp_id_out(self, operator, value):
        """ Search function for wp_id out
        """
        return self.get_field_filter(
            operator, value, mode='out', field='wp_id')

    def _search_sku_in(self, operator, value):
        """ Search function for sku out
        """
        return self.get_field_filter(
            operator, value, mode='in', field='sku')

    def _search_sku_out(self, operator, value):
        """ Search function for sku out
        """
        return self.get_field_filter(
            operator, value, mode='out', field='sku')

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    # TODO remove: ------------------------------------------------------------
    wp_id = fields.Integer(string='Wp ID in', readonly=True)
    wp_sku = fields.Char('SKU', size=25, readonly=True)
    connector_id = fields.Many2one('wp.connector', 'Connector')
    wp_published = fields.Boolean(
        string='WP published', help='Product present on Wordpress site')
    # TODO remove: ------------------------------------------------------------

    wp_connector_rel_ids = fields.One2many(
        comodel_name='wp.connector.product.rel',
        inverse_name='template_id',
        string='Connector relation',
        )

    wp_id_in = fields.Integer(
        string='Wp ID in',
        compute='_get_wp_id_in_and_out',
        inverse='_save_wp_id_in',
        search='_search_wp_id_in',
        multi=True,
    )
    wp_id_out = fields.Integer(
        string='Wp ID out',
        compute='_get_wp_id_in_and_out',
        inverse='_save_wp_id_out',
        search='_search_wp_id_out',
        multi=True,
    )

    sku_in = fields.Char(
        size=20,
        string='SKU in',
        compute='_get_wp_id_in_and_out',
        inverse='_save_sku_in',
        search='_search_sku_out',
        multi=True,
    )

    sku_out = fields.Char(
        size=20,
        string='SKU out',
        compute='_get_wp_id_in_and_out',
        inverse='_save_sku_out',
        search='_search_sku_out',
        multi=True,
    )

    wp_connector_in_id = fields.Many2one(
        comodel_name='wp.connector',
        string='Connector IN',
        help='Connector used to import product (setup in company)',
        related='company_id.wp_connector_in_id',
        readonly=True,
    )
    wp_connector_out_id = fields.Many2one(
        comodel_name='wp.connector',
        string='Connector OUT',
        help='Connector used to export product (setup in company)',
        related='company_id.wp_connector_out_id',
        readonly=True,
    )

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

    # TODO keep here or in relation? ------------------------------------------
    wp_type = fields.Selection([
        ('simple', 'Simple product'),
        ('variable', 'Variable product'),

        ('grouped', 'Grouped product'),
        ('external', 'External product'),
        ], 'Wordpress type', default='simple')
    wp_status = fields.Selection([
        ('draft', 'draft'),
        ('pending', 'pending'),
        ('private', 'private'),
        ('publish', 'publish'),
        ], 'Wordpress Status', default='publish')
    # TODO --------------------------------------------------------------------

    # Link management:
    wp_linked_ids = fields.Many2many(
        comodel_name='product.template',
        relation='product_linked_rel',
        column1='template_id',
        column2='linked_id',
        string='Linhed product',
        )
    wp_up_sell_ids = fields.Many2many(
        comodel_name='product.template',
        relation='product_upsell_rel',
        column1='template_id',
        column2='upsell_id',
        string='Up sell product',
        )
    wp_cross_sell_ids = fields.Many2many(
        comodel_name='product.template',
        relation='product_cross_rel',
        column1='template_id',
        column2='crossed_id',
        string='Cross sell product',
        )

    # 2many fields:
    wp_category_ids = fields.Many2many(
        comodel_name='product.category',
        string='Category')

    wp_tag_ids = fields.Many2many(
        comodel_name='wp.tag',
        string='Tags')

    wp_image = fields.Binary(
         compute='_get_wp_image_file',
         help='Load image from folder for connector', string='WP Image')

    # -------------------------------------------------------------------------
    # Fields for web:
    # -------------------------------------------------------------------------
    # Tassonomy:
    wp_vulgar_name = fields.Char(string='Vulgar name', size=50)
    wp_scientific_name = fields.Char(string='Scientific name', size=50)
    wp_family = fields.Char(
        string='Family', size=50,
        help='Relation family, used ID.ID for link Tag Wiki of Wordpress')
    wp_genre = fields.Char(
        string='Genre', size=50,
        help='Relation genre, used ID.ID for link Tag Wiki of Wordpress')
    # marchio collezione
    wp_specie = fields.Char(string='Species', size=50)
    wp_variety = fields.Char(string='Variety', size=50)
    wp_origin = fields.Char(string='Origin', size=50)
    wp_ancestor = fields.Char(string='Ancestors', size=50)
    wp_description = fields.Char(string='Description', size=50)
    # FOTO

    # -------------------------------------------------------------------------
    # Sale characteristic:
    wp_jar_id = fields.Many2one(
        comodel_name='wp.attribute.term',
        string='Jar / Packaging',
        domain="[('attribute_id.filter', '=', 'vaso')]",
        help='Show attribute terms with filter: vaso',
    )
    # Prezzo
    wp_sale_width = fields.Char(string='Sale width', size=20)
    wp_sale_height = fields.Char(string='Sale height', size=20)
    wp_sale_trunk = fields.Char(string='Sale trunk', size=50)
    wp_graph_holder = fields.Char(string='Graph holder', size=50)
    wp_color = fields.Char(string='Color', size=50)
    wp_finish = fields.Char(string='Finish', size=50)

    # -------------------------------------------------------------------------
    # Botanic / Tech:
    wp_botanic_group = fields.Char(string='Botanic group', size=50)
    wp_bearing_id = fields.Many2one(
        comodel_name='wp.attribute.term',
        string='Bearing',
        domain="[('attribute_id.filter', '=', 'portamento')]",
        help='Show attribute terms with filter: portamento',
    )
    wp_flower_dimension = fields.Char(string='Flower dimension', size=20)
    wp_scent_id = fields.Many2one(
        comodel_name='wp.attribute.term',
        string='Scent',
        domain="[('attribute_id.filter', '=', 'profumo')]",
        help='Show attribute terms with filter: profumo',
    )
    wp_scent_note = fields.Char(string='Scent note', size=50)
    wp_leaf_type_id = fields.Many2one(
        comodel_name='wp.attribute.term',
        string='Leaf type',
        domain="[('attribute_id.filter', '=', 'tipologia_foglia')]",
        help='Show attribute terms with filter: tipologia_foglia',
    )
    wp_leaf_color_id = fields.Many2one(
        comodel_name='wp.attribute.term',
        string='Leaf color',
        domain="[('attribute_id.filter', '=', 'colore_foglia')]",
        help='Show attribute terms with filter: colore_foglia',
    )
    wp_leaf_persistence = fields.Char(string='Leaf persistence', size=50)
    wp_flowering_type = fields.Char(string='Flowering type', size=50)
    wp_flowering_color_id = fields.Many2one(
        comodel_name='wp.attribute.term',
        string='Flowering color',
        domain="[('attribute_id.filter', '=', 'colore_fioritura')]",
        help='Show attribute terms with filter: colore_fioritura',
    )
    wp_flowering_period = fields.Char(string='Flowering period', size=50)
    wp_flowering_height = fields.Char(string='Flowering height', size=50)
    wp_time_transplant = fields.Char(string='Time transplant', size=50)
    wp_time_sowing = fields.Char(string='Time sowing', size=50)
    wp_time_roundup = fields.Char(string='Time round up', size=50)
    wp_dimension_width = fields.Char(string='Dimension width', size=30)
    wp_dimension_height_id = fields.Many2one(
        comodel_name='wp.attribute.term',
        string='Dimension height',
        domain="[('attribute_id.filter', '=', 'altezza')]",
        help='Show attribute terms with filter: altezza',
    )
    wp_exposition_id = fields.Many2one(
        comodel_name='wp.attribute.term',
        string='Exposition',
        domain="[('attribute_id.filter', '=', 'esposizione')]",
        help='Show attribute terms with filter: esposizione',
    )
    wp_frost_resistance = fields.Char(string='Frost resistance', size=50)
    # wp_frost_resistance_id = fields.Many2one(
    #    comodel_name='wp.attribute.term',
    #    string='Frost resistance',
    #    domain="[('attribute_id.filter', '=', 'gelo')]",
    #    help = 'Show attribute terms with filter: gelo',
    # )
    wp_rusticity = fields.Char(string='Rusticity', size=50)
    wp_use_id = fields.Many2one(
        comodel_name='wp.attribute.term',
        string='Use',
        domain="[('attribute_id.filter', '=', 'utilizzo')]",
        help='Show attribute terms with filter: utilizzo',
    )
    wp_biologic = fields.Char(string='Pet friendly / Biologic', size=50)
    wp_adversity = fields.Char(string='Adversity', size=50)

    # -------------------------------------------------------------------------
    # Care and cultivation
    wp_pruning = fields.Char(
        string='Pruning', size=50,
        help='Relation pruning, used ID.ID for link Tag Wiki of Wordpress',
    )
    wp_care = fields.Char(
        string='Care and cultivation', size=50,
        help='Relation cultivation, used ID.ID for link Tag Wiki of Wordpress'
    )
    wp_propagation = fields.Char(
        string='Propagation', size=50,
        help='Relation propagation, used ID.ID for link Tag Wiki of Wordpress'
    )
    wp_disease = fields.Char(
        string='Parasite and disease', size=50,
        help='Relation disease, used ID.ID for link Tag Wiki of Wordpress'
    )


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

    wp_attribute_ids = fields.One2many(
        comodel_name='wp.product.attribute',
        inverse_name='product_id',
        string='Attributes')


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

    wp_connector_in_id = fields.Many2one(
        comodel_name='wp.connector',
        string='Connector IN',
        help='Connector used for import product')
    wp_connector_out_id = fields.Many2one(
        comodel_name='wp.connector',
        string='Connector OUT',
        help='Connector used for export product',
    )
