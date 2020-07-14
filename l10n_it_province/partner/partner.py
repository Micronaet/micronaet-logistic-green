# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import logging
import sys
from odoo import models, fields, api
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class ResRegion(models.Model):
    _name = 'res.region'
    _description = 'Region'

    name = fields.Char(
        'Region Name', size=64, help='The full name of the region.',
        required=True)
    country_id = fields.Many2one('res.country', 'Country')


class ResProvince(models.Model):
    _name = 'res.province'
    _description = 'Province'

    name = fields.Char(
        'Province Name', size=64, help='The full name of the province.',
        required=True)
    code = fields.Char(
        'Province Code', size=2, help='The province code in two chars.',
        required=True)
    region = fields.Many2one('res.region', 'Region')


class ResCity(models.Model):
    _name = 'res.city'
    _description = 'City'

    name = fields.Char('City', size=64, required=True)
    province_id = fields.Many2one('res.province', 'Province')
    zip = fields.Char('ZIP', size=5)
    phone_prefix = fields.Char('Telephone Prefix', size=16)
    istat_code = fields.Char('ISTAT code', size=16)
    cadaster_code = fields.Char('Cadaster Code', size=16)
    web_site = fields.Char('Web Site', size=64)
    region = fields.Many2one(
        related='province_id.region', string='Region', readonly=True)


"""
class ResPartner(models.Model):
    _inherit = 'res.partner'

    _columns = {
        'province' = fields.many2one('res.province', string='Province'),
        'region' = fields.many2one('res.region', string='Region'),
    }

    def on_change_city(self, cr, uid, ids, city):
        res = {'value': {}}
        if(city):
            city_id = self.pool.get('res.city').search(
                cr, uid, [('name', '=ilike', city)])
            if city_id:
                city_obj = self.pool.get('res.city').browse(
                    cr, uid, city_id[0])
                res = {'value': {
                    'province': (
                        city_obj.province_id and city_obj.province_id.id
                        or False
                    ),
                    'region': city_obj.region and city_obj.region.id or False,
                    'zip': city_obj.zip,
                    'country_id': (
                        city_obj.region and
                        city_obj.region.country_id and
                        city_obj.region.country_id.id or False
                    ),
                    'city': city.title(),
                }
                }
        return res

    def _set_vals_city_data(self, cr, uid, vals):
        if 'city' in vals and 'province' not in vals and 'region' not in vals:
            if vals['city']:
                city_obj = self.pool.get('res.city')
                city_ids = city_obj.search(
                    cr, uid, [('name', '=ilike', vals['city'])])
                if city_ids:
                    city = city_obj.browse(cr, uid, city_ids[0])
                    if 'zip' not in vals:
                        vals['zip'] = city.zip
                    if city.province_id:
                        vals['province'] = city.province_id.id
                    if city.region:
                        vals['region'] = city.region.id
                        if city.region.country_id:
                            vals['country_id'] = city.region.country_id.id
        return vals

    def create(self, cr, uid, vals, context=None):
        vals = self._set_vals_city_data(cr, uid, vals)
        return super(res_partner, self).create(cr, uid, vals, context)

    def write(self, cr, uid, ids, vals, context=None):
        vals = self._set_vals_city_data(cr, uid, vals)
        return super(res_partner, self).write(cr, uid, ids, vals, context)
"""
