# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import os
import logging
import base64
import pdb
from urllib.request import urlretrieve
from urllib.parse import quote
from odoo import models, fields, api

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
        sku = self.wp_sku
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
    def load_product_template_structure(self, connector):
        """ Load product template from Wordpress
        """
        # Parameters:
        image_path = connector.image_path
        connector_id = connector.id
        parameters = connector.get_publish_parameters()

        wcapi = connector.get_connector()
        params = {
            'per_page': parameters['block']['product'],
            'page': 1,
        }
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
                wp_in_id = record['id']
                sku = record['sku']
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
                split_code = self.clean_code(sku)
                sku, default_code, supplier, child, barcode = split_code

                # ODOO search:
                products = self.search([
                    ('connector_id', '=', connector_id),
                    ('wp_in_id', '=', wp_in_id),
                    ])
                create_mode = False if products else True

                # -------------------------------------------------------------
                # Prepare data (use publish setup):
                # -------------------------------------------------------------
                data = {
                    'connector_id': connector_id,
                    'wp_published': True,
                    'wp_in_id': wp_in_id,
                    'default_code': sku,
                    'wp_sku': sku,
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
                                            for option in attribute['options']]
                        wp_attribute_ids.append((0, 0, {
                            'attribute_id': attribute_odoo_id,
                            'term_ids': [(6, 0, current_term_ids)],
                            'show_product_page': attribute['visible'],
                            'used_in_variant': attribute['variation'],
                            'position': attribute['position']
                            }))
                    products.write({'wp_attribute_ids': wp_attribute_ids})

                if parameters['publish']['image']:
                    image_list.append((wp_in_id, images))

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
                            'products/%s/variations' % wp_in_id,
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
                                    (variant_id, [variant_images]))

                            variant_data = {
                                'connector_id': connector_id,
                                'wp_type': 'variable',
                                'wp_published': True,
                                'name': name,
                                'wp_in_id': variant['id'],
                                'default_code': variant_sku,
                                'wp_sku': variant_sku,
                                'lst_price': variant['regular_price'],
                                'description_sale': variant['description'],
                                'weight': variant['weight'],
                                'wp_master_id': product_id,
                                }

                            # TODO Publish block also here!

                            odoo_variants = self.search([
                                ('wp_in_id', '=', variant_id),  # never overlap
                                ])

                            if odoo_variants:
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
            # break  # TODO Test mode:

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
                        ('wp_in_id', 'in', item_ids),
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
                    product.wp_in_id,  # default_code,
                    extension,
                    ),
                )
            if os.path.isfile(filename):
                _logger.info('Image yet present: %s' % filename)
                continue

            try:
                f_data = open(filename, 'rb')
                product.wp_image = base64.encodebytes(f_data.read())
                f_data.close()
            except:
                product.wp_image = False

    # -------------------------------------------------------------------------
    # Compute function:
    # -------------------------------------------------------------------------
    @api.depends(
        'company_id.wp_connector_in_id', 'company_id.wp_connector_out_id',
        # 'wp_connector_rel_ids.wp_id',
    )
    def _get_wp_id_in_and_out(self):
        """ Compute ID from sub element and setup in company
        """
        _logger.warning('WP id updating...')
        for template in self:
            connector_in_id = template.wp_connector_in_id
            connector_out_id = template.wp_connector_out_id
            wp_in_id = wp_out_id = False
            sku_in = sku_out = False
            for line in template.wp_connector_rel_ids:
                if line.connector_id == connector_in_id:
                    wp_in_id = line.wp_id
                    sku_in = line.sku
                if line.connector_id == connector_out_id:
                    wp_out_id = line.wp_id
                    sku_out = line.sku

            template.wp_in_id = wp_in_id
            template.wp_in_id = wp_out_id
            template.sku_in = sku_in
            template.sku_out = sku_out

        _logger.warning('WP id updated!')

    # Inverse function (generic for both):
    def _save_wp_id_in_and_out(self, mode='wp', direction='in'):
        """ Inverse function for create sub record (used for both fields
        """
        self.ensure_one()
        _logger.warning('Updating WP ID in correct connector...')

        rel_pool = self.env['wp.connector.product.rel']
        template = self

        if direction == 'in':
            connector_id = template.wp_connector_in_id
            sku = template.sku_in
            wp_id = template.wp_in_id
        else:
            connector_id = template.wp_connector_out_id
            sku = template.sku_out
            wp_id = template.wp_out_id

        if not connector_id:
            return _logger.error(
                'Cannot create wp ID, setup the connector in company before'
                'direction [%s]'.format(direction))

        for line in template.wp_connector_rel_ids:
            if line.connector_id == connector_id:
                line_found = line
                break
        else:
            line_found = False

        # Mode management:
        if mode == 'wp':
            field = 'wp_id'
            value = wp_id
        else:
            field = 'sku'
            value = sku

        # Insert managemenet:
        if line_found:  # Update:
            line_found.write({
                field: value,
            })
        else:  # Create line:
            # template.wp_out_id = wp_out_id
            rel_pool.create({
                'template_id': template.id,
                'connector_id': connector_id.id,
                field: value,
            })

    def _save_wp_id_in(self):
        return self._save_wp_id_in_and_out(mode='wp', direction='in')

    def _save_wp_id_out(self):
        return self._save_wp_id_in_and_out(mode='wp', direction='out')

    def _save_sku_in(self):
        return self._save_wp_id_in_and_out(mode='sku', direction='in')

    def _save_sku_out(self):
        return self._save_wp_id_in_and_out(mode='sku', direction='out')

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

    wp_in_id = fields.Integer(
        string='Wp ID in',
        compute='_get_wp_id_in_and_out',
        inverse='_save_wp_id_in',
        multi=True,
        store=True,
    )
    wp_out_id = fields.Integer(
        string='Wp ID out',
        compute='_get_wp_id_in_and_out',
        inverse='_save_wp_id_out',
        multi=True,
        store=True,
    )
    sku_in = fields.Char(
        string='SKU out',
        compute='_get_wp_id_in_and_out',
        size=20,
        inverse='_save_sku_in',
        multi=True,
        store=True,
    )
    sku_out = fields.Char(
        string='SKU out',
        compute='_get_wp_id_in_and_out',
        size=20,
        inverse='_save_sku_out',
        multi=True,
        store=True,
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
