# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import os
import logging
import base64
import urllib
from odoo import models, fields, api
from PIL import Image

_logger = logging.getLogger(__name__)


class ProductImageAlbum(models.Model):
    """ Model name: ProductImageAlbum
    """
    _name = 'product.image.album'
    _description = 'Image album'

    # -------------------------------------------------------------------------
    # Button event:
    # -------------------------------------------------------------------------
    @api.multi
    def clean_not_present(self):
        """ Delete image that no more present in list
        """
        image_pool = self.env['product.image.file']
        images = image_pool.search([
            ('album_id', '=', self[0]),
            ('status', '=', 'removed'),
        ])
        return images.unlink()

    # -------------------------------------------------------------------------
    # Columns:
    # -------------------------------------------------------------------------
    code = fields.Char(
        'Code', size=10, required=True,
        help='Used for setup configuration parameters')
    name = fields.Char(
        'Name', size=64, required=True)
    path = fields.Char(
        'Folder path', size=128, required=True,
        help='Path folder, ex.: /home/admin/photo')
    parent_format = fields.Char(
        'Parent format', size=60,
        help='Parent code list for product composition, ex.: 3|5')
    extension_image = fields.Char(
        'Extension', size=10, required=True,
        help="Without dot, for ex.: jpg")
    fields.Integer('Max width in px.')
    fields.Integer('Max height in px.')
    empty_image = fields.Char(
        'Empty image', size=64,
        help='Complete name + ext. of empty image, ex.: 0.jpg')
    upper_code = fields.Boolean(
        'Upper code',
        help='Name is code in upper case: abc10 >> ABC10.png')
    has_variant = fields.Boolean(
        'Has variants',
        help='ex. for code P1010 variant 001: P1010-001.jpg')
    schedule_load = fields.Boolean(
        'Schedule load', default=True,
        help="""If checked will load with schedule operation else still 
            have only the images present in this moment""")
    force_reload = fields.Boolean(
        'Force reload',
        help="""Force reload will regenerate all images
            (used when change dimension etc.)""")


class ProductImageFile(models.Model):
    """ Model name: ProductImageFile
    """
    _name = 'product.image.file'
    _description = 'Image file'
    _rec_name = 'filename'
    _order = 'filename'

    @api.model
    def get_default_code(self, filename):
        """ Function that extract default_code from filename)
        """
        # TODO test upper and test extension
        block = filename.split('.')
        if len(block) == 2:
            return (
                block[0].replace('_', ' '),
                False,
                block[1]
            )
        if len(block) == 3:  # variant
            return (
                block[0].replace('_', ' '),
                block[1],
                block[2],
            )
        else:
            return (
                block[0].replace('_', ' '),
                False,
                '',  # no extension when error
            )

    # -------------------------------------------------------------------------
    #                             CALCULATED ALBUM:
    # -------------------------------------------------------------------------
    @api.model
    def calculate_syncro_image_album(self, album_ids):
        """ Calculate image for the album depend on parent album, only for
            modify elements
            @return: error images not updated
        """
        # Pool used:
        album_pool = self.env['product.image.album']

        not_updated_ids = []  # record image that raise error on update
        forced_album_ids = []  # forced album list
        for album in album_pool.browse(album_ids):
            # Load file name for check write / create operations:
            album_filename = {}  # reset every album
            for image in album.image_ids:
                album_filename[image.filename] = image.id

            origin = album.album_id  # readability
            redimension_type = album.redimension_type  # XXX max for now

            # TODO for now used max
            if redimension_type != 'max':
                continue

            # TODO change view
            max_px = album.max_px or album.width or album.height or 100

            # Loop on all modified photos:
            for image in origin.image_ids:
                if album.force_reload:
                    if album.id not in forced_album_ids:
                        forced_album_ids.append(album.id)
                    if image.status not in ('modify', 'ok'):
                        continue  # jump error images
                else:
                    if image.status != 'modify':
                        continue  # jump if not modified or error

                # Files name:
                filename = image.filename
                file_in = os.path.join(
                    os.path.expanduser(origin.path), filename)
                file_out = os.path.join(
                    os.path.expanduser(album.path), filename)

                try:
                    img = Image.open(file_in)
                    width, height = img.size

                    if width > height:
                        new_width = max_px
                        new_height = max_px * height / width
                    else:
                        new_height = max_px
                        new_width = max_px * width / height

                    new_img = img.resize(
                        (new_width, new_height),
                        Image.ANTIALIAS)

                    # Filters: NEAREST, BILINEAR, BICUBIC, ANTIALIAS
                    new_img.save(file_out, 'JPEG')  # TODO change output!!!!
                    _logger.info('Resize: %s [max: %s]' % (filename, max_px))

                    # Write record:
                    data = {
                        'filename': filename,
                        'album_id': album.id,  # new album
                        'timestamp': image.timestamp,
                        'product_id': image.product_id.id,
                        'extension': image.extension,
                        'variant': image.variant,
                        'variant_code': image.variant_code,
                        'status': 'ok',
                        'width': new_width,
                        'height': new_height,
                    }
                    if filename in album_filename:
                        self.write(album_filename[filename], data)
                    else:
                        self.create(data)
                except:
                    _logger.error('Cannot create thumbnail for %s' % file_in)
                    not_updated_ids.append(image.id)
                    continue

        # Reset force check after recalculation
        if forced_album_ids:
            album_pool.write(forced_album_ids, {
                'force_reload': False,
                })
            _logger.warning(
                'Forced album done, reset check # %s' % len(forced_album_ids))
        return not_updated_ids

    # -------------------------------------------------------------------------
    #                             FOLDER IMAGE ALBUM:
    # -------------------------------------------------------------------------
    @api.model
    def load_syncro_image_album(self, album_ids):
        """ Import image folder for proxy (folder non calculated
        """
        # Pool used:
        album_pool = self.env['product.image.album']
        product_pool = self.env['product.product']

        exist_ids = []  # for all albums
        for album in album_pool.browse(album_ids):
            # Parameters:
            path = os.path.expanduser(album.path)
            extension_image = album.extension_image

            # TODO manage upper case or lower case and variant!
            # upper_code = album.upper_code
            # has_variant = album.has_variant

            # Load file current loaded in album folder:
            old_filenames = {}
            for old_file in album.image_ids:
                old_filenames[old_file.filename] = (
                    old_file.id, old_file.timestamp)

            # Read all files in folder:
            for root, directories, files in os.walk(path):
                for filename in files:
                    if filename.startswith('._'):
                        _logger.warning('Jump temp file: %s' % filename)
                        continue

                    fullname = os.path.join(root, filename)
                    timestamp = '%s' % os.path.getmtime(fullname)
                    default_code, variant, extension = self.get_default_code(
                        filename)

                    product_ids = product_pool.search([
                        ('default_code', '=', default_code),
                    ])
                    if product_ids:
                        if len(product_ids) > 1:
                            _logger.error('More than one product code: %s' % (
                                default_code))
                        product_id = product_ids[0]
                    else:
                        product_id = False

                    data = {
                        'filename': filename,
                        'album_id': album.id,
                        'timestamp': timestamp,
                        'product_id': product_id,
                        'extension': extension,
                        # Used?:
                        # 'width': fields.integer('Width px.'),
                        # 'height': fields.integer('Height px.'),
                    }
                    if variant:
                        data['variant'] = True
                        data['variant_code'] = variant

                    # Status case:
                    if extension != extension_image:
                        data['status'] = 'format'
                    elif not product_id:
                        data['status'] = 'product'
                    # TODO set ok in calculated albums

                    # check file modified in not calculated album:
                    if not album.calculated and filename in old_filenames:
                        # Check timestamp for update
                        item_id = old_filenames[filename][0]

                        # Note: Keep error if present:
                        if 'status' not in data and \
                                timestamp != old_filenames[filename][1]:
                            data['status'] = 'modify'

                        self.write(item_id, data)

                    else:  # Create (default modify)
                        item_id = self.create(data)
                    # if item_id:
                    exist_ids.append(item_id)  # after will force exist

        # Mark image no more present (for all albums):
        not_exist_ids = self.search([
            ('id', 'not in', exist_ids),  # record not updated
            ('album_id', 'in', album_ids),  # only album checked
        ])
        if not_exist_ids:
            self.write(not_exist_ids, {
                'status': 'removed',
                })
        return True

    # -------------------------------------------------------------------------
    #                            Scheduled action:
    # -------------------------------------------------------------------------
    @api.model
    def syncro_image_album(self):
        """ Import image for album marked (not calculated)
        """
        # Pool used:
        album_pool = self.env['product.image.album']

        # ---------------------------------------
        # Load all image in album not calculated:
        # ---------------------------------------
        album_ids = album_pool.search([
            ('calculated', '=', False),
            ('schedule_load', '=', True),
            ])
        if album_ids:
            self.load_syncro_image_album(album_ids)

        # ---------------------------------
        # Resize child image in album:
        # ---------------------------------
        # A. Resize child calculated album:
        album_ids = album_pool.search([
            ('calculated', '=', True),
            ('schedule_load', '=', True),
            ])

        if album_ids:
            # Recalculate images:
            not_updated_ids = self.calculate_syncro_image_album(album_ids)
        else:
            not_updated_ids = []

        # Set all images as ok not modify (except error convert):
        modify_ids = self.search([
            ('status', '=', 'modify'),  # only modify files
            ('id', 'not in', not_updated_ids),  # only files right converted
            ])
        if modify_ids:
            self.write(modify_ids, {
                'status': 'ok',
                })
        return True

    filename = fields.Char('Filename', size=60, required=True)
    album_id = fields.Many2one('product.image.album', 'Album')
    timestamp = fields.Char('Timestamp', size=30)
    variant = fields.Boolean('Variant',
        help='File format CODE-XXX.jpg where XXX is variant block')
    variant_code = fields.Char('Variant code', size=5)
    product_id = fields.Many2one('product.product', 'Product')

    # Used?:
    width = fields.Integer('Width px.')
    height = fields.Integer('Height px.')
    extension = fields.Char(
        'Extension', size=10, help='Without dot, for ex.: jpg')
    status = fields.Selection([
        ('ok', 'OK'),
        ('modify', 'File modify'),
        ('removed', 'File removed'),
        ('format', 'Wrong format'),
        ('product', 'No product'),
    ], 'Status', default='modify')
    # TODO file image binary


class ProductImageAlbumCalculated(models.Model):
    """ Add fields for manage calculated folders
    """
    _inherit = 'product.image.album'

    # -------------------
    # Resize fields:
    # -------------------
    calculated = fields.Boolean(
        'Calculated', help='Folder is calculated from another images')
    check_image = fields.Boolean(
        'Used for check image',
        help='Check if this album will be insert in report for check'
             'image presence for product')
    album_id = fields.Many2one(
        'product.image.album', 'Parent album',
        domain=[('calculated', '=', False)])

    # Dimension for calculating:
    width = fields.Integer('Width in px.')
    height = fields.Integer('Height in px.')
    max_px = fields.Integer('Max px.')  # TODO
    redimension_type = fields.Selection([
        ('length', 'Max length'),
        ('width', 'Max width'),
        ('max', 'Max large (length or width)'),
        ], 'Resize type', default='max')
    image_ids = fields.One2many(
        'product.image.file', 'album_id', 'Files')


class ProductProductImage(models.Model):
    """ Add extra function and fields for manage picture for product
    """
    _inherit = 'product.product'

    # -------------------------------------------------------------------------
    #                              Utility:
    # -------------------------------------------------------------------------
    # TODO removeable?
    @api.model # TODO api.multi and remove ids
    def _get_product_image_list(self, ids, album_id):
        """ Return list of product and image for album_id passed
            context parameters:
                only_name: return only name depend if file exist:
        """
        # Read parameters:
        only_name = self.env.context.get('only_name', False)
        res = dict.fromkeys(ids, False)  # init res record

        if not album_id:
            _logger.error('album default not present in parameters!')
            return res

        # Read parameter for album passed:
        album_proxy = self.env['product.image.album'].browse(
            album_id)

        image_path = os.path.expanduser(album_proxy.path)
        # empty_image = os.path.join(image_path, album_proxy.empty_image)
        if not image_path:
            _logger.error('Path for album: %s not found!' % album_id)
            return res
        for product in self.browse(cr, uid, ids, context=context):
            code = product.default_code or ''
            if not code:
                _logger.error('Code not found: %s' % product.name)
                continue

            # Prepare code:
            if album_proxy.upper_code:
                code = code.upper()
            else:
                code = code.lower()
            code = code.replace(' ', '_')  # no space in code

            # Prepare block elements:
            parent_block = [len(code)]
            try:
                if album_proxy.parent_format:
                    for item in album_proxy.parent_format.split('|'):
                        parent_block.append(int(item))
                parent_block.sort()
                parent_block.reverse()
            except:
                _logger.error('Block element error: use only code')

            # Loop on block part:
            for width in parent_block:
                parent_code = code[:width]
                image = '%s.%s' % (
                    os.path.join(image_path, parent_code),
                    album_proxy.extension_image,
                    )
                try:
                    (filename, header) = urllib.request.urlretrieve(image)
                    f = open(filename, 'rb')
                    img = base64.encodebytes(f.read())
                    f.close()
                except:
                    _logger.warning('Image not found: %s' % image)
                    img = False
                if img:
                    if only_name:
                        res[product.id] = image
                    else:
                        res[product.id] = img
                    break  # no more elements (found first)
        return res

    # -------------------------------------------------------------------------
    #                           Function fields:
    # -------------------------------------------------------------------------
    # product_image_quotation:
    @api.depends
    def _get_product_image_quotation(self):
        """ Search album for quotation picture in config and return list:
            context parameters:
                'product_image': image code to open, ex.: QUOTATION (default)
        """
        # TODO rewrite better and decide how optimize
        # TODO add test for load image or not depend on user setting or report

        # -------------------------
        # A. Passed code for image:
        # -------------------------
        product_image = self.env.context.get('product_image')

        if not product_image:
            # --------------------
            # B. Config parameter:
            # --------------------
            config_pool = self.env['ir.config_parameter']
            config_ids = config_pool.search([
                ('key', '=', 'product.image.quotation'),
                ])

            # Read value from code:
            if config_ids:
                config_proxy = config_pool.browse(config_ids)[0]
                product_image = config_proxy.value

        # -------------------------------
        # Try to read album if present
        # (passed or config parameter)
        # -------------------------------
        album_ids = self.env['product.image.album'].search([
            ('code', '=', product_image)])
        if album_ids:
            album_id = album_ids[0]
        else:
            album_id = False

        # Read images from folder:
        return self._get_product_image_list(ids, album_id, context=None)

    # product_image_context:
    def _get_product_image_context(self, ids):
        """ Get image from context parameter
            >> album_id
        """
        # TODO manage variants?
        product_image_pool = self.pool.get('product.image.file')

        res = dict.fromkeys(ids, False)

        # TODO Manage context!
        album_id = self.env.context.get('album_id', False)
        if not album_id:
            album_code = self.env.context.get('album_code', False)
            if album_code:
                album_ids = self.pool.get('product.image.album').search([
                    ('code', '=', album_code),
                    ])
                album_id = album_ids[0]

        if not album_id:
            _logger.error('Call context image without pass album_id in ctx')
            return res

        _logger.info('Load image from album: %s product [%s]' % (
            album_id, ids))

        # TODO Load from file?

        # Read all image file in product selected
        product_ids = product_image_pool.search([
            ('album_id', '=', album_id),  # current album
            ('product_id', 'in', ids),  # only selected product
            ('status', 'in', ('ok', 'modify')),  # only correct images
            ('variant', '=', False),  # Master image
            ])

        if not product_ids:
            _logger.error('No context image, try reload database!')

        product_fullname = {}
        for item in product_image_pool.browse(product_ids):
            product_fullname[item.product_id.id] = os.path.expanduser(
                os.path.join(
                    item.album_id.path,
                    item.filename,
                ))

        for product_id in ids:
            if product_id not in product_fullname:
                continue  # no photo in database
            try:
                # TODO remove: vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv
                fullname = product_fullname[product_id]
                (filename, header) = urllib.request.urlretrieve(
                    fullname)
                # TODO remove ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                f = open(filename, 'rb')
                res[product_id] = base64.encodebytes(f.read())
                _logger.info('Load image context: %s' % fullname)
                f.close()
            except:
                _logger.error('Cannot load: %s' % fullname)
                pass  # no image
        return res

    def _compute_lines_album(self, ids):
        """ return list of album for that product
        """
        res = {}
        for product in self.browse(ids):
            res[product.id] = []
            for image in product.image_ids:
                if image.variant:
                    continue  # album are only for default image (no variant)
                album_id = image.album_id.id
                if album_id not in res[product.id]:
                    res[product.id].append(album_id)
        return res

    product_image_quotation = fields.Binary(
        'Product image quotation', compute='_get_product_image_quotation',
        method=True)
    product_image_context = fields.Binary(
        'Product image context', compute='_get_product_image_context',
        method=True,
        help='Image loaded from album passed in context album_id param.')

    #  Check image presence:
    image_ids = fields.One2many(
        'product.image.file', 'product_id', 'Product')
    album_ids = fields.Many2many(
        compute="_compute_lines_album",
        relation='product.image.album', string='Album',
        help='List of album for presence')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
