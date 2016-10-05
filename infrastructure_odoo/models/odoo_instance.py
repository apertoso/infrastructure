from random import choice
from string import ascii_letters, digits

import requests
from openerp.addons.website.models.website import slug

from openerp import _, models, api, fields, exceptions
from .odoo_module import ODOO_VERSIONS


class OdooInstance(models.Model):
    _name = 'odoo.instance'
    _description = "Odoo instance"
    _inherit = ['mail.thread']

    name = fields.Char(string='Name', required=True)
    user_id = fields.Many2one(
        comodel_name='res.users',
        string='Instance owner',
        help='For development and test instances, specify an '
             'owner/responsible here'
    )
    odoo_version = fields.Selection(
        selection=ODOO_VERSIONS,
        string='Odoo version'
    )
    odoo_enterprise = fields.Boolean(
        string='Odoo Enterprise'
    )
    state = fields.Selection(
        selection=[('devel', 'Development'),
                   ('test', 'Test'),
                   ('prod', 'Production')],
        string='State',
        default='devel', )

    key = fields.Char(
        string='Key',
        required=1,
        copy=False,
        default=lambda self: ''.join(
            choice(ascii_letters + digits) for i in range(24))
    )
    export_url = fields.Char(
        string='Url where data is exported',
        compute='_get_export_url',
        copy=False)

    instance_url = fields.Char(
        string='Url where odoo instance is available',
        copy=False
    )
    opw_contract = fields.Char(
        string='Odoo Enterprise Contract number',
        copy=False
    )
    # subscription_id = fields.Many2one(
    #     comodel_name='sale.subscription',
    #     string='Subscription'
    # )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Customer'
    )

    apt_package_ids = fields.Many2many(
        comodel_name='odoo.instance.apt_package',
        relation='odoo_instance_apt_rel',
        column1='instance_id',
        column2='apt_package_id',
        string='Apt packages',
    )
    pip_module_ids = fields.Many2many(
        comodel_name='odoo.instance.pip_module',
        relation='odoo_instance_pip_rel',
        column1='instance_id',
        column2='pip_module_id',
        string='Pip modules',
    )

    docker_image_id = fields.Many2one(
        comodel_name='docker.image',
        string='Docker image',
    )
    docker_image_tag_id = fields.Many2one(
        comodel_name='docker.image.tag',
        domain="[('docker_image_id', '=', docker_image_id)]",
        string='Docker Tag',
    )
    parent_docker_image_id = fields.Many2one(
        comodel_name='docker.image',
        string='Parent Docker image',
    )
    parent_docker_image_tag_id = fields.Many2one(
        comodel_name='docker.image.tag',
        domain="[('docker_image_id', '=', parent_docker_image_id)]",
        string='Parent Docker Tag',
    )

    parent_ids = fields.Many2many(
        comodel_name='odoo.instance',
        relation='odoo_instance_parent_rel',
        column1='instance_child',
        column2='instance_parent',
        string='Parents'
    )
    odoo_master_pwd = fields.Char(string='Odoo Master pwd', copy=False)
    db_name = fields.Char(string='Db name', copy=False)
    branch_ids = fields.One2many(
        comodel_name='odoo.instance.branch',
        inverse_name='instance_id',
        string="Used Branches",
    )
    active = fields.Boolean('active', default=True)

    # Variables for ansible
    ansible_group_ids = fields.Many2many(
        comodel_name='infrastructure.ansible.group',
        column1='odoo_instance_id',
        column2='infrastructure_ansible_group_id',
        relation='infrastructure_ansible_group_odoo_instance_rel',
        string='ansible_group')
    fqdn = fields.Char(string='fqdn')
    ip = fields.Char(string='ip')
    customer = fields.Char(string='customer')
    openvz_production_cid = fields.Integer(string='openvz_production_cid')
    ip_backup = fields.Char(string='ip_backup')
    openvz_backup_cid = fields.Integer(string='openvz_backup_cid')
    psql_dbpass = fields.Char(string='psql_dbpass')
    odoo_dbfilter = fields.Char(string='odoo_dbfilter')
    configure_zabbix = fields.Boolean(string='configure_zabbix')
    sentry_enabled = fields.Boolean(string='sentry_enabled')
    sentry_client_dsn = fields.Char(string='sentry_client_dsn')

    # Build trigger fields
    build_trigger_url = fields.Char(
        String='Build Trigger URL',
        help='If emtpy, the system defaults will be used',
        copy=False)
    build_trigger_token = fields.Char(
        String='Build Trigger Token',
        help='If emtpy, the system defaults will be used',
        copy=False)
    build_trigger_ref = fields.Char(
        String='Build Trigger Ref',
        help='If emtpy, the system defaults will be used',
        copy=False)

    _sql_constraints = [
        ('key_unique', 'UNIQUE(key)', "This key is already in use"),
    ]

    @api.multi
    @api.constrains('branch_ids', 'parent_ids')
    def _check_branch_versions(self):
        for instance in self:
            if any([o.odoo_version != instance.odoo_version for o in
                    instance.branch_ids]):
                raise exceptions.ValidationError(
                    _('Branch odoo version mismatch'))

            if any([o.odoo_version != instance.odoo_version for o in
                    instance.parent_ids]):
                raise exceptions.ValidationError(
                    _('Parent odoo version mismatch'))

    @api.depends('name', 'key', 'state')
    def _get_export_url(self):
        base_url = self.env["ir.config_parameter"].get_param(
            "web.base.url", default="http://localhost:8069")
        for record in self:
            if isinstance(record.id, models.NewId):
                record.export_url = 'Save record to retrieve url info'
            else:
                record.export_url = "%s/infrastructure_odoo/%s/%s" % (
                    base_url,
                    slug(record),
                    record.key
                )

    @api.multi
    def _get_build_trigger_info(self):
        self.ensure_one()
        ir_config_get = self.env['ir.config_parameter'].get_param
        build_trigger_url = self.build_trigger_url or ir_config_get(
            'infrastructure_odoo.build_trigger_url')
        build_trigger_token = self.build_trigger_token or ir_config_get(
            'infrastructure_odoo.build_trigger_token')
        build_trigger_ref = self.build_trigger_ref or ir_config_get(
            'infrastructure_odoo.build_trigger_ref')
        return build_trigger_url, build_trigger_token, build_trigger_ref

    @api.multi
    def do_trigger_build(self):
        for record in self:
            (trigger_url, trigger_token, trigger_ref) = \
                record._get_build_trigger_info()
            post_data = {
                'token': trigger_token,
                'ref': trigger_ref,
                'variables[CUST_CONFIG]': record.export_url,
            }
            r = requests.post(trigger_url, data=post_data)
            r.raise_for_status()

    @api.multi
    def get_instance_data(self, values=False):
        self.ensure_one()
        if not values:
            values = {}
        for parent in self.parent_ids:
            values.update(parent.get_instance_data(values))

        no_inherit_fields = (
            'docker_image_id',
            'docker_image_tag_id',
            'parent_docker_image_id',
            'parent_docker_image_tag_id',
            # ansible_fields
            'ansible_group_ids',
            'fqdn',
            'ip',
            'customer',
            'openvz_production_cid',
            'ip_backup',
            'openvz_backup_cid',
            'psql_dbpass',
            'odoo_dbfilter',
            'configure_zabbix',
            'sentry_enabled',
            'sentry_client_dsn',
        )

        # we put branch data here with "project_name -> values"
        # for parent instances, the list with enabled modules must be merged
        # with child instances branches modules with the same project_name

        branch_values = values.get('branches', {})
        for branch in self.branch_ids:
            gitproject = branch.gitproject_id.name
            project_data = branch_values.get(gitproject, {})
            new_branch_data = branch.get_branch_data()
            enabled_modules = set(project_data.get('enabled_modules', []))
            enabled_modules |= set(new_branch_data.get('enabled_modules', []))
            project_data.update(new_branch_data)
            project_data.update({'enabled_modules': list(enabled_modules)})
            branch_values.update({gitproject: project_data})
        values.update({'branches': branch_values})

        # fields that are not defined should not overwrite the data with a
        # 'False' value
        for field in ('odoo_version', 'db_name',
                      'odoo_master_pwd', 'key', 'name', 'state',
                      'export_url', 'instance_url', 'opw_contract',
                      'odoo_enterprise', 'fqdn',
                      'ip',
                      'customer',
                      'openvz_production_cid',
                      'ip_backup',
                      'openvz_backup_cid',
                      'psql_dbpass',
                      'odoo_dbfilter',
                      'configure_zabbix',
                      'sentry_enabled',
                      'sentry_client_dsn',
                      ):
            value = eval("self.{}".format(field))
            if value:
                values.update({field: value})
            elif field in no_inherit_fields and field in values:
                del values[field]

        # m2m style fields to merge with a set op
        for field in ('apt_package_ids', 'pip_module_ids'):
            data_values = eval("self.{}".format(field)).mapped('name')
            if data_values:
                new_set = set(values.get(field, []) + data_values)
                values.update({field: list(new_set)})
            elif field in no_inherit_fields and field in values:
                del values[field]

        # relation fields: pass the name attribute
        for field in ('partner_id',
                      'docker_image_id',
                      'docker_image_tag_id',
                      'parent_docker_image_id',
                      'parent_docker_image_tag_id',
                      ):
            value = eval("self.{}".format(field))
            if value:
                values.update({field: value.name})
            elif field in no_inherit_fields and field in values:
                del values[field]
        # m2m fields, pass as list
        for field in ('ansible_group_ids',):
            value = eval("self.{}.mapped('name')".format(field))
            if value:
                values.update({field: value})
            elif field in no_inherit_fields and field in values:
                del values[field]

        return values


class InfrastructureAnsibleGroup(models.Model):
    _name = 'infrastructure.ansible.group'

    name = fields.Char('Group Name')


class OdooInstanceAptPackage(models.Model):
    _name = 'odoo.instance.apt_package'

    name = fields.Char('Apt Package Name')


class OdooInstancePipModule(models.Model):
    _name = 'odoo.instance.pip_module'

    name = fields.Char('Pip Module Name')
    version = fields.Char('Pip Module Version string')


class OdooInstanceBranch(models.Model):
    _name = 'odoo.instance.branch'

    branch_id = fields.Many2one(
        comodel_name='git.branch',
        string='Project Branch',
    )
    enabled_module_ids = fields.Many2many(
        comodel_name='odoo.module',
        relation='odoo_instance_branch_odoo_module_rel',
        column1='instance_branch_id',
        column2='odoo_module_id',
        string='Enabled modules',
        domain="[('branch_id', '=', branch_id)]",
    )
    instance_id = fields.Many2one(
        comodel_name='odoo.instance',
        string="odoo.instance",
        required=True,
        ondelete='cascade',
    )

    gitproject_id = fields.Many2one(
        related='branch_id.repository_id.gitproject_id',
        string='Git Project'
    )
    name = fields.Char(
        related='branch_id.name',
        string='Name',
        readonly=True)
    repository_id = fields.Many2one(
        related='branch_id.repository_id',
        readonly=True)
    odoo_module_ids = fields.One2many(
        related='branch_id.odoo_module_ids',
        readonly=True)
    odoo_version = fields.Selection(
        related='branch_id.odoo_version',
        readonly=True)

    @api.multi
    def get_branch_data(self):
        self.ensure_one()
        values = {
            'host': self.repository_id.githost_id.name,
            'repository': self.repository_id.name,
            'gitproject': self.gitproject_id.name,
            'git_path_ssh': self.repository_id.gitpath_ssh,
            'git_path_http': self.repository_id.gitpath_http,
            'branch': self.branch_id.name,
            'enabled_modules': self.enabled_module_ids.mapped('name'),
        }
        return values
