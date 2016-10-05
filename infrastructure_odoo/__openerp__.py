# -*- coding: utf-8 -*-

{
    'name': 'Infrastructure odoo',
    'version': '9.0.1.0.0',
    'category': '',
    'description': """ Infrastructure data for odoo containers""",
    'author': 'Apertoso',
    'website': '',
    'depends': [
        'base', 'mail'
    ],
    'data': [
        'data/ir_config_parameter.xml',
        'security/groups.xml',
        'security/ir.model.access.csv',
        'wizard/wizard_import_git.xml',
        'wizard/wizard_create_copy.xml',
        'views/odoo_instance_view.xml',

    ],
    'installable': True,

}
