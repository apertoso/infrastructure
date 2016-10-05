# -*- coding: utf-8 -*-
from openerp import fields, models, api


class WizardCreateCopy(models.TransientModel):
    _name = "wizard.create.copy"
    _description = "Create copy wizard"
    name = fields.Char(string="New name",
                       required=True, )
    parent_instance_id = fields.Many2one('odoo.instance', 'Parent instance')
    type = fields.Selection(string="Type",
                            selection=[('devel', 'Development'),
                                       ('test', 'Test'),
                                       ('prod', 'Production')],
                            required=True, )

    @api.model
    def default_get(self, fields_list):
        res = super(WizardCreateCopy, self).default_get(fields_list)
        odoo_instance_obj = self.env['odoo.instance']
        instance_rec = odoo_instance_obj.browse(self._context.get('active_id'))
        res['parent_instance_id'] = instance_rec.id
        res['name'] = instance_rec.name
        res['type'] = 'devel'
        return res

    @api.multi
    def create_copy(self):
        def _get_parent_docker_image():
            # get the parent docker image
            pdi = self.parent_instance_id.docker_image_id
            if not pdi:
                # search if allready exists
                pdi = docker_image_obj.search([('name', '=', pdi.name)],
                                              limit=1)
                if not pdi:
                    # create the parent docker instance
                    dock_image_vals = {'name': self.parent_instance_id.name}
                    pdi = docker_image_obj.create(dock_image_vals)
            return pdi

        def _get_parent_docker_image_tag_latest(parent_dock_image_id):
            # check to see if it exists
            search_crit = [('docker_image_id', '=', parent_dock_image_id.id),
                           ('name', '=', 'latest')]
            image_tag_id = docker_image_tag_obj.search(search_crit)
            # if it doesn't exist yet Create it
            if not image_tag_id:
                create_vals = {'name': 'latest',
                               'docker_image_id': parent_dock_image_id.id,
                               }
                image_tag_id = docker_image_tag_obj.create(create_vals)
            return image_tag_id

        odoo_instance_obj = self.env['odoo.instance']
        docker_image_obj = self.env['docker.image']
        docker_image_tag_obj = self.env['docker.image.tag']

        parent_dock_image_id = _get_parent_docker_image()

        image_tag_id = _get_parent_docker_image_tag_latest(
            parent_dock_image_id)

        vals = {'name': self.name,
                'state': self.type,
                'parent_ids': [(6, 0, [self.parent_instance_id.id])],
                'docker_image_id': parent_dock_image_id.id,
                'docker_image_tag_id': image_tag_id.id,
                'user_id': self._uid
                }

        res = self.parent_instance_id.copy(vals)

        return {
            'name': odoo_instance_obj._description,
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'odoo.instance',
            'type': 'ir.actions.act_window',
            'res_id': res.id,
            'target': 'current',
        }
