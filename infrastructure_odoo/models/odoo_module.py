# -*- coding: utf-8 -*-
from openerp import fields, models

ODOO_VERSIONS = [
    ('7.0', '7.0'),
    ('8.0', '8.0'),
    ('9.0', '9.0'),
    ('10.0', '10.0'),
]


class OdooModule(models.Model):
    _name = 'odoo.module'
    name = fields.Char('Name')
    branch_id = fields.Many2one(
        comodel_name='git.branch',
        string='branch',
    )
    active = fields.Boolean('active', default=True)
