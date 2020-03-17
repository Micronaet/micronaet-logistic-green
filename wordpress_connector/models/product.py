# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import os
import logging
import base64
from urllib.request import urlretrieve
from urllib.parse import quote
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


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
            code = '%s_%02d' % (
                code,
                ord(child) - 64,
            )
        return sku, code, supplier, child, ean13

    @api.multi
    def update_product_supplier(self):
        """ Integration of supplier, taked from sku extra code
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
            _logger.error('Jump empty code (sku or supplier) [%s]!' %
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
        image_update = True
        image_path = connector.image_path
        connector_id = connector.id

        wcapi = connector.get_connector()
        params = {'per_page': 50, 'page': 1}
        variation_param = {'per_page': 20, 'page': 1}

        # load from file:
        image_list = []
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
                wp_id = record['id']
                sku = record['sku']
                name = record['name']
                images = record['images']
                variations = record['variations']
                regular_price = record['regular_price']
                related_ids = record['related_ids']
                tags = record['tags']
                weight = record['weight']
                stock_status = record['stock_status']
                product_type = record['type']
                status = record['status']
                description = record['description']
                attributes = record['attributes']
                slug = record['slug']
                categories = record['categories']

                # Clean sku for default_code
                split_code = self.clean_code(sku)
                sku, default_code, supplier, child, barcode = split_code

                # Prepare data:
                data = {
                    'connector_id': connector_id,
                    'wp_published': True,
                    'name': name,
                    'wp_id': wp_id,
                    'default_code': sku,
                    'wp_sku': sku,
                    'lst_price': regular_price,
                    'description_sale': description,
                    'weight': weight,
                    'wp_type': product_type,
                    # TODO variable, simple, grouped, external, variable
                }
                if barcode:
                    data['barcode'] = barcode
                if variations:
                    data['wp_master'] = True
                else:
                    data['wp_master'] = False

                # Update ODOO:
                products = self.search([
                    # ('connector_id', '=', connector_id),
                    ('wp_id', '=', wp_id),
                    ])

                if products:
                    _logger.info(
                        'Update product %s [%s]' % (default_code, sku))
                    products.write(data)
                else:
                    _logger.info(
                        'Create product %s [%s]' % (default_code, sku))
                    products = self.create(data)
                product_id = products[0].id
                products.update_product_supplier()

                # Image update:
                if image_update:
                    image_list.append((wp_id, images))

                # -------------------------------------------------------------
                #                        VARIATIONS
                # -------------------------------------------------------------
                if variations:
                    variation_param['page'] = 1
                    while True:
                        var_reply = wcapi.get(
                            'products/%s/variations' % wp_id,
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
                            # stock_status = variant['stock_status']
                            # product_type = variant['type']
                            # status = variant['status']

                            if image_update and variant_images:
                                # Usually one:
                                image_list.append(
                                    (variant_id, [variant_images]))

                            variant_data = {
                                'connector_id': connector_id,
                                'wp_published': True,
                                'name': name,
                                'wp_id': variant['id'],
                                'default_code': variant_sku,
                                'wp_sku': variant_sku,
                                'lst_price': variant['regular_price'],
                                'description_sale': variant['description'],
                                'weight': variant['weight'],
                                'wp_master_id': product_id,
                                # TODO attribute terms!
                                }
                            odoo_variants = self.search([
                                ('wp_id', '=', variant_id),  # never overlap
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
                    break
            break
        # ---------------------------------------------------------------------
        # Image download:
        # ---------------------------------------------------------------------
        if image_update:
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
                            '          >> Get image saved as %s' % filename)

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
