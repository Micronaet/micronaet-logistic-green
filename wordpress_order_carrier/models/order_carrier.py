#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2019  Micronaet SRL (<http://www.micronaet.it>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import pdb
from odoo import fields, models, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.multi
    def shipments_get_tracking_result(self):
        """ 18. Get tracking information
        """
        self.ensure_one()
        order = self  # TODO loop?

        soap_connection = order.soap_connection_id

        if not soap_connection:
            return 'Order %s without SOAP ref.!' % order.name
        if order.carrier_soap_id:
            return 'Order %s has SOAP ID %s cannot check!' % (
                order.name, order.carrier_soap_id)
        if not order.master_tracking_id:
            return 'Order %s without master track ID %s cannot check!' % (
                order.name, order.carrier_soap_id)

        service = soap_connection.get_connection()
        pdb.set_trace()
        data = order.get_request_container(
            system=True, internal=True, customer=False, store=False)

        data['TrackingMBE'] = order.master_tracking_id
        reply = service.TrackingRequest(RequestContainer=data)
        error = order.check_reply_status(reply)
        if not error:
            # Update SOAP data for real call
            tracking_status = reply.get('TrackingStatus')
            if tracking_status != order.delivery_soap_state:
                # -------------------------------------------------------------
                #                            Changed
                # -------------------------------------------------------------
                # 1. Change only tracking status:
                order.write({
                    'delivery_soap_state': tracking_status,
                })

                # 2. Update ODOO and Wordpress:
                if tracking_status == 'DELIVERED':
                    order.update_with_courier_data('delivered')
        return error