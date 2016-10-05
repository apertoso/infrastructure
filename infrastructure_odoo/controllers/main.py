# -*- coding: utf-8 -*-
import json

from openerp.addons.website.models.website import unslug

from openerp import http
from openerp.http import request


class InfrastuctureOdooController(http.Controller):
    @http.route('/infrastructure_odoo/<instance>/<key>',
                auth='public', type="http", methods=['GET', 'POST'],
                csrf=False)
    def infrastructure_odoo(self, instance, key, **post):
        (instance_name, instance_id) = unslug(instance)
        odoo_instance = request.env['odoo.instance'].sudo().search(
            [('id', '=', instance_id),
             ('key', '=', key)],
            limit=1)

        if not odoo_instance:
            return request.not_found('Instance data not found')
        method = request.httprequest.method
        if method == 'GET':
            res = odoo_instance.get_instance_data()
        elif method == 'POST':
            # Get post vars
            docker_image = post.get('docker_image', None)
            docker_image_tag = post.get('docker_image_tag', None)
            build_status = post.get('build_status', None)
            if not all((docker_image, docker_image_tag, build_status)):
                return request.not_found('Parameters missing')
            docker_image_tag_obj = request.env['docker.image.tag'].sudo()
            docker_image_tag_obj.set_docker_image_state(
                docker_image, docker_image_tag, build_status
            )
            res = {'result': 'OK'}
        else:
            return request.not_found('Method not found')

        return request.make_response(
            json.dumps(
                res,
                sort_keys=True,
                indent=4,
                separators=(', ', ': ')
            ),
            headers=[('Content-Type', 'application/json')],
        )
