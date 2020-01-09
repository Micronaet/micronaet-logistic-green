#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).


import logging
import woocommerce
from odoo import api, fields, models
from odoo.tools.translate import _
from slugify import slugify

_logger = logging.getLogger(__name__)


class ConnectorServer(models.Model):
    """ Model name: ConnectorServer
    """
    _inherit = 'connector.server'

    # -------------------------------------------------------------------------
    # Utility:
    # -------------------------------------------------------------------------
    @api.model
    def get_lang_slug(self, name, lang):
        """ Slug problem with lang
        """
        slug = slugify(name)
        return slug + ('' if lang == 'it' else '-en')

    @api.multi
    def get_wp_connector(self):
        """ Connect with Word Press API management
        """
        timeout = 400  # TODO parametrize

        connector = self[0]
        if not connector.wordpress:
            _logger.info('Not Wordpress connector')

        _logger.info('>>> Connecting: %s%s API: %s, timeout=%s' % (
            connector.wp_url,
            connector.wp_version,
            connector.wp_api,
            timeout,
            ))
        try:
            return woocommerce.API(
                url=connector.wp_url,
                consumer_key=connector.wp_key,
                consumer_secret=connector.wp_secret,
                wp_api=connector.wp_api,
                version=connector.wp_version,
                timeout=timeout,
                )
        except:
            _logger.error('Cannot connect to Wordpress!!')

    wordpress = fields.Boolean(
        'Wordpress', help='Wordpress web server')
    wp_all_category = fields.Boolean(
        'All category',
        help='Public all product with category and parent also',
        default=True)
    wp_url = fields.Char('WP URL', size=180)
    wp_key = fields.Char('WP consumer key', size=180)
    wp_secret = fields.Char('WP consumer secret', size=180)

    wp_api = fields.Boolean('WP API', default=True)
    wp_version = fields.Char('WP Version', size=10, default='wc/v3')

    # album_ids = fields.Many2many(
    #    'product.image.album',
    #    'connector_album_rel', 'server_id', 'album_id', 'Album')
    wp_category = fields.Selection([
        ('out', 'ODOO Original WP replicated'),
        ('in', 'WP Original ODOO replicated'),
        ], 'Category management', required=True, default='out')


class ProductProduct(models.Model):
    """ Model name: ProductProduct
    """

    _inherit = 'product.product'

    """
    def auto_package_assign(self, cr, uid, ids, context=None):
        # Auto assign code
        
        package_pool = self.env['product.product.web.package']
        for product in self.browse(cr, uid, ids, context=context):
            default_code = product.default_code or ''
            if not default_code:
                _logger.error('No default code, no package assigned!')
                continue

            # -----------------------------------------------------------------
            # Search:
            # -----------------------------------------------------------------
            # Mode 6:
            search_code = '%-6s' % default_code[:6]
            package_ids = package_pool.search(cr, uid, [
                ('name', 'ilike', search_code),
                ], context=context)
            if package_ids:
                self.write(cr, uid, [product.id], {
                    'model_package_id': package_ids[0],
                    }, context=context)

                _logger.warning('Code 6 "%s" found #%s !' % (
                    search_code, len(package_ids)))
                continue

            # Mode 3:
            search_code = default_code[:3]
            package_ids = package_pool.search(cr, uid, [
                ('name', 'ilike', search_code),
                ], context=context)
            if package_ids:
                self.write(cr, uid, [product.id], {
                    'model_package_id': package_ids[0],
                    }, context=context)
                _logger.warning(
                    'Auto assign package: Code 3 "%s" found #%s !' % (
                        search_code, len(package_ids)))
            else:
                _logger.error(
                    'Auto assign package: Code not found %s !' % default_code)
        return True"""

    # 'wp_id': fields.integer('Worpress ID'),
    # 'wp_lang_id': fields.integer('Worpress translate ID'),
    emotional_short_description = fields.Text(
        'Emotional short', translate=True)
    emotional_description = fields.Text(
        'Emotional long', translate=True)
    model_package_id = fields.Many2one(
        'product.product.web.package', 'Package')


class ProductImageFile(models.Model):
    """ Model name: ProductImageFile
    """

    _inherit = 'product.image.file'

    dropbox_link = fields.Char('Dropbox link', size=100)


class ProductProductWebCategory(models.Model):
    """ Model name: ProductProductWebPackage
    """

    _name = 'product.product.web.category'
    _description = 'Category template'
    _order = 'name'

    # -------------------------------------------------------------------------
    # Button event:
    # -------------------------------------------------------------------------
    @api.multi
    def update_product_category(self):
        """ Update product category for all selected item of this connector
        """
        line_pool = self.env['product.product.web.server']

        current = self[0]
        category_ids = [item.id for item in current.category_ids]

        lines = line_pool.search([
            ('connector_id', '=', current.connection_id.id),
            ('product_id.default_code', '=ilike', '%s%%' % current.name)
            ])

        if lines:
            lines.write({
                'wordpress_categ_ids': [(6, 0, category_ids)],
                })

            _logger.info('Updated %s records' % len(lines))
        return True

    connection_id = fields.Many2one(
        'connector.server', 'Server',
        required=True)
    name = fields.Char(
        'Codice padre', size=20, required=True),
    category_ids = fields.Many2many(
        'product.public.category', 'template_web_category_rel',
        'product_id', 'category_id',
        'Category', required=True)

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'Duplicated name!'),
        ]


class ProductProductWebPackage(models.Model):
    """ Model name: ProductProductWebPackage
    """

    _name = 'product.product.web.package'
    _description = 'Package data'
    _order = 'name'

    # -------------------------------------------------------------------------
    # Button:
    # -------------------------------------------------------------------------
    @api.multi
    def auto_package_assign(self):
        """ Auto assign code
        """
        model_package_id = self[0].id
        current = self[0]

        product_pool = self.env['product.product']
        products = product_pool.search([
            ('default_code', '=ilike', '%s%%' % current.name),
            ])
        _logger.warning('Updating %s product...' % len(products))
        return products.write({
            'model_package_id': model_package_id,
            })

    name = fields.Char('Codice padre', size=10, required=True),

    pcs_box = fields.Integer('pcs / box'),
    pcs_pallet = fields.Integer('pcs / pallet'),

    net_weight = fields.Integer('Peso netto (gr)'),
    gross_weight = fields.Integer('Peso lordo (gr)'),

    box_width = fields.Integer('Box: larg.'),
    box_depth = fields.Integer('Box: prof..'),
    box_height = fields.Integer('Box: alt.'),

    pallet_dimension = fields.Char('Dim. Pallet', size=30),

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'Duplicated name!'),
        ]


class ProductProductWebServer(models.Model):
    """ Model name: ProductProductWebServer
    """

    _inherit = 'product.product.web.server'

    # -------------------------------------------------------------------------
    # Utility:
    # -------------------------------------------------------------------------
    @api.model
    def get_existence_for_product(self, product):
        """ Return real existence for web site
        """
        stock_quantity = int(product.mx_net_mrp_qty - product.mx_mrp_b_locked)
        # TODO manage q x pack?
        # q_x_pack = product.q_x_pack or 1
        # stock_quantity //= q_x_pack
        if stock_quantity < 0:
            return 0
        return stock_quantity

    @api.model
    def get_category_block_for_publish(self, item, lang):
        """ Get category block for data record WP
        """
        categories = []
        for category in item.wordpress_categ_ids:
            wp_id = eval('category.wp_%s_id' % lang)
            wp_parent_id = eval('category.parent_id.wp_%s_id' % lang)
            if not wp_id:
                continue
            categories.append({'id': wp_id })
            if category.connector_id.wp_all_category and category.parent_id:
                categories.append({'id': wp_parent_id})
        return categories

    # -------------------------------------------------------------------------
    # Button event:
    # -------------------------------------------------------------------------
    @api.multi
    def open_image_list_product(self):
        """
        """
        model_pool = self.env['ir.model.data']
        view_id = model_pool.get_object_reference(
            'wordpress_connector', 'view_product_product_web_server_form')[1]

        return {
            'type': 'ir.actions.act_window',
            'name': _('Image detail'),
            'view_type': 'form',
            'view_mode': 'form,form',
            'res_id': self[0].id,
            'res_model': 'product.product.web.server',
            'view_id': view_id, # False
            'views': [(view_id, 'form'), (False, 'tree')],
            'domain': [],
            'context': self.env.context,
            'target': 'new',
            'nodestroy': False,
            }

    @api.model
    def wp_clean_code(self, default_code, destination='wp'):
        """ Return default code for Wordpress
        """
        if destination == 'wp':
            return default_code.replace(' ', '&nbsp;')
        else: # odoo
            return default_code.replace('&nbsp;', ' ')

    @api.model
    def get_wp_price(self, line):
        """ Extract price depend on force, discount and VAT
        """
        product = line.product_id
        if line.force_price:
            price = line.force_price
        else:
            price = product.lst_price * (
                100.0 - line.connector_id.discount) / 100.0

        price += line.connector_id.add_vat * price / 100.0
        if price < line.connector_id.min_price:
            price = line.connector_id.min_price

        # ADD approx?
        return price

    @api.multi
    def publish_now(self):
        """ Publish now button
            Used also for more than one elements (not only button click)
            Note all product must be published on the same web server!
        """
        default_lang = 'it'
        log_excel = self.env.context.get('log_excel', False)

        first_proxy = self[0]
        if not first_proxy.connector_id.wordpress:
            _logger.warning('Not a wordpress proxy, call other')
            return super(ProductProductWebServer, self).publish_now()

        # ---------------------------------------------------------------------
        #                         WORDPRESS Publish:
        # ---------------------------------------------------------------------
        _logger.warning('Publish all on wordpress:')
        product_pool = self.env['product.product']
        server_pool = self.env['connector.server']
        # lang_pool = self.env['product.product.web.server.lang']

        wcapi = server_pool.get_wp_connector(first_proxy.connector_id)

        # Context used here:
        # TODO manage image with context
        # context_lang = self.env.context.copy()

        # Read first element only for setup parameters:
        connector = first_proxy.connector_id
        # context_lang['album_id'] = first_proxy.connector_id.album_id.id
        # context['album_id'] = first_proxy.connector_id.album_id.id

        # ---------------------------------------------------------------------
        # Publish image:
        # ---------------------------------------------------------------------
        # TODO (save link)

        # ---------------------------------------------------------------------
        # Publish product (lang management)
        # ---------------------------------------------------------------------
        translation_lang = {}

        # First lang = original, second traslate
        for odoo_lang in ('it_IT', 'en_US'):
            lang = odoo_lang[:2]  # WP lang
            context_lang['lang'] = odoo_lang  # self._lang_db

            for item in self:  # .browse(cr, uid, ids, context=context_lang):

                # Readability:
                product = item.product_id
                default_code = product.default_code or u''
                sku = default_code

                # Description:
                name = item.force_name or product.name or u''
                description = item.force_description or \
                    product.emotional_description or \
                    product.large_description or u''
                short = product.emotional_short_description or name or u''

                price = u'%s' % self.get_wp_price(item)
                # weight = u'%s' % product.weight
                status = 'publish' if item.published else 'private'
                stock_quantity = self.get_existence_for_product(product)
                wp_id = eval('item.wp_%s_id' % lang)
                wp_it_id = item.wp_it_id # Default product for language
                # fabric, type_of_material

                # -------------------------------------------------------------
                # Images block:
                # -------------------------------------------------------------
                images = []
                for image in item.wp_dropbox_images_ids:
                    dropbox_link = image.dropbox_link
                    if dropbox_link and dropbox_link.startswith('http'):
                        images.append({
                            'src': image.dropbox_link,
                            })

                # -------------------------------------------------------------
                # Category block:
                # -------------------------------------------------------------
                categories = self.get_category_block_for_publish(item, lang)

                # Text data (in lang):
                data = {
                    'name': name,
                    'description': description,
                    'short_description': short,
                    'sku': self.wp_clean_code(sku), # XXX not needed
                    'lang': lang,
                    # It doesn't update:
                    'categories': categories,
                    'wp_type': item.wp_type,
                    }
                if images:
                    data['images'] = images

                if lang == default_lang:
                    # Numeric data:
                    data.update({
                        'type': item.wp_type,
                        # 'sku': self.wp_clean_code(sku),
                        'regular_price': price,
                        # sale_price (discounted)
                        'stock_quantity': stock_quantity,
                        'status': status,
                        'catalog_visibility': 'visible',
                        # catalog  search  hidden

                        # Forced in variant:
                        # 'weight': weight,
                        # 'dimensions': {
                        #   'width': '%s' % product.width,
                        #   'length': '%s' % product.length,
                        #   'height': '%s' % product.height,
                        #   },
                        })

                else: # Other lang (only translation
                    if not wp_it_id:
                        _logger.error(
                            'Product %s without default IT [%s]' % (
                                lang, default_code))
                        continue

                    # Translation:
                    data.update({
                        'translations': {'it': wp_it_id},
                        })

                # -------------------------------------------------------------
                #                         Update:
                # -------------------------------------------------------------
                if wp_id:
                    try:
                        call = 'products/%s' % wp_id
                        reply = wcapi.put(call, data).json()

                        if log_excel != False:
                            log_excel.append(
                                ('put', call, u'%s' % (data, ),
                                    u'%s' % (reply, )))

                        if reply.get('code') in (
                                'product_invalid_sku',
                                'woocommerce_rest_product_invalid_id'):
                            pass # TODO Manage this case?
                            # wp_id = False # will be created after
                        else:
                            _logger.warning('Product %s lang %s updated!' % (
                                wp_id, lang))
                    except:
                        # TODO manage this error if present
                        _logger.error('Not updated ID %s lang %s [%s]!' % (
                            wp_id, lang, data))

                # -------------------------------------------------------------
                #                         Create:
                # -------------------------------------------------------------
                if not wp_id:
                    # Create (will update wp_id from now)
                    try:
                        call = 'products'
                        reply = wcapi.post(call, data).json()
                        if log_excel != False:
                            log_excel.append(
                                ('post', call, u'%s' % (data, ),
                                    u'%s' % (reply, )))
                    except:  # Timeout on server:
                        _logger.error('Server timeout: %s' % (data, ))
                        continue

                    try:
                        if reply.get('code') == 'product_invalid_sku':
                            wp_id = reply['data']['resource_id']
                            _logger.error(
                                'Product %s lang %s duplicated [%s]!' % (
                                    wp_id, lang, reply))

                        else:
                            wp_id = reply['id']
                            _logger.warning('Product %s lang %s created!' % (
                                wp_id, lang))
                    except:
                        raise osv.except_osv(
                            _('Error'),
                            _('Reply not managed: %s' % reply),
                            )
                        continue

                    if wp_id:
                        self.write(cr, uid, [item.id], {
                            'wp_%s_id' % lang: wp_id,
                            }, context=context)

                # Save translation of ID (for language product)
                if default_code not in translation_lang:
                    translation_lang[default_code] = {}
                translation_lang[default_code][lang] = (wp_id, name)
        return translation_lang

    # -------------------------------------------------------------------------
    # Function fields:
    # -------------------------------------------------------------------------
    def _get_album_images(self, cr, uid, ids, fields, args, context=None):
        """ Fields function for calculate
        """
        res = {}
        for current in self.browse(cr, uid, ids, context=context):
            server_album_ids = [
                item.id for item in current.connector_id.album_ids]

            res[current.id] = [
                image.id for image in current.product_id.image_ids \
                    if image.album_id.id in server_album_ids]
        return res

    def _get_product_detail_items(
            self, cr, uid, ids, fields, args, context=None):
        """ Fields function for calculate
        """
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = {}

            product = line.product_id
            model = product.model_package_id
            if model:
                res[line.id] = {
                    'pack_l': float(model.box_width),
                    'pack_h': float(model.box_height),
                    'pack_p': float(model.box_depth),

                    'weight': float(model.gross_weight) / 1000.0,
                    'weight_net': float(model.net_weight) / 1000.0,

                    'q_x_pack': float(model.pcs_box),
                    'lst_price': product.lst_price,
                    # pallet dimension
                    }
            else:
                res[line.id] = {
                    'pack_l': product.pack_l,
                    'pack_h': product.pack_h,
                    'pack_p': product.pack_p,

                    'weight': product.weight,
                    'weight_net': product.weight_net,

                    'q_x_pack': product.q_x_pack,
                    'lst_price': product.lst_price,
                    }
        return res

    wp_it_id = fields.Integer('WP it ID')
    wp_en_id = fields.Integer('WP en ID')
    wordpress_categ_ids = fields.Many2many(
        'product.public.category', 'product_wp_rel',
        'product_id', 'category_id',
        'Wordpress category')
    # wp_dropbox_images_ids = fields.One2many(
    #    'product.image.file',
    #    compute='_get_album_images',
    #    string='Album images',
    #    )
    wordpress = fields.related(
        'connector_id', 'wordpress',
        type='boolean', string='Wordpress')

    # ---------------------------------------------------------------------
    # Product related/linked fields:
    # ---------------------------------------------------------------------
    model_package_id = fields.Mqny2one(
        'product_id.model_package_id', readonly=True,
        string='Package model')

    pack_l = fields.Float(
        _get_product_detail_items, method=True, readonly=True,
        type='float', string='L. Pack', multi=True,
        )
    pack_h = fields.Float(
        _get_product_detail_items, method=True, readonly=True,
        type='float', string='H. Pack', multi=True,
        )
    pack_p = fields.Float(
        _get_product_detail_items, method=True, readonly=True,
        type='float', string='P. Pack', multi=True,
        )

    weight = fields.Float(
        _get_product_detail_items, method=True, readonly=True,
        type='float', string='Gross weight', multi=True,
        )
    weight_net = fields.Float(
        _get_product_detail_items, method=True, readonly=True,
        type='float', string='NEt weight', multi=True,
        )

    lst_price = fields.Float(
        _get_product_detail_items, method=True, readonly=True,
        type='float', string='Pricelist', multi=True,
        )

    q_x_pack = fields.Float(
        _get_product_detail_items, method=True, readonly=True,
        type='float', string='Q. x Pack', multi=True,
        )

    # ---------------------------------------------------------------------
    # Link related to product
    # ---------------------------------------------------------------------
    product_pack_l = fields.Float(
        'product_id.pack_l', string='Pack L prod.')
    product_pack_h = fields.Float(
        'product_id.pack_h', string='Pack H prod.')
    product_pack_p = fields.Float(
        'product_id.pack_p', string='Pack P prod.')

    product_weight = fields.Float(
        'product_id.weight', string='New weight prod.')
    product_weight_net = fields.Float(
        'product_id.weight_net', string='Gross weight prod.')

    product_lst_price = fields.Float(
        'product_id.lst_price', string='Pricelist')
    product_q_x_pack = fields.Float(
        'product_id.q_x_pack', string='Q x pack prodotto')
    # ---------------------------------------------------------------------

    wp_type = fields.selection([
        ('simple', 'Simple product'),
        ('grouped', 'Grouped product'),
        ('external', 'External product'),
        ('variable', 'Variable product'),
        ], 'Wordpress type')
