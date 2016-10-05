import re

from openerp import _, exceptions, fields, models, api
from .odoo_module import ODOO_VERSIONS
from ..lib.github import Github
from ..lib.gitlab import Gitlab


def get_values(gitapi, record):
    if gitapi == 'gitlab':
        values = {
            'name': record.get('name'),
            'external_id_git': record.get('id'),
            'description': record.get('description') or record.get(
                'name_with_namespace'),
            'gitpath_http': record.get('http_url_to_repo'),
            'gitpath_ssh': record.get('ssh_url_to_repo'),
        }
    elif gitapi == 'github':
        values = {
            'name': record.get('name'),
            'external_id_git': record.get('id'),
            'description': record.get('description') or record.get(
                'full_name'),
            'gitpath_http': record.get('clone_url'),
            'gitpath_ssh': record.get('ssh_url'),
        }
    else:
        values = {}

    return values


class GitHost(models.Model):
    _name = 'git.host'

    @api.multi
    def _get_git_credentials(self):
        domain = [('git_host_id', '=', self.id),
                  '|', ('user_id', '=', self.env.uid),
                  ('user_id', '=', False)]
        credentials = self.env['git.credential'].with_context(
            active_test=False).search(domain, limit=1)
        if not credentials and not self.auth_public:
            raise exceptions.ValidationError(
                _('No valid credentials found for host %s and user %s') %
                (self.name, self.env.user.name))
        return credentials

    @api.multi
    def get_api_object(self):

        credentials = self._get_git_credentials()
        if self.api == 'gitlab':
            return Gitlab(
                gitlab_host=self.name,
                token=credentials.user_token
            )
        elif self.api == 'github':
            return Github(
                auth_user=credentials.user_name,
                auth_token=credentials.user_token,
            )
        else:
            raise exceptions.ValidationError(
                _('Githost api %s not yet implemented') % self.api
            )

    @api.multi
    def get_gitgroups(self):
        if self.api == 'gitlab':
            return self.get_gitgroups_gitlab()
        else:
            raise exceptions.ValidationError(
                _('Githost api %s not yet implemented') % self.api
            )

    @api.multi
    def get_gitgroups_gitlab(self):
        self.ensure_one()

        gitlab = self.get_api_object()
        group_data = gitlab.get_groups()
        self.gitgroup_ids.write({'active': False})
        group_obj = self.env['git.group']

        for item in group_data:
            values = {
                'name': item.get('name'),
                'external_id_git': item.get('id'),
                'githost_id': self.id,
                'active': True,
            }
            existing_group = group_obj.with_context(active_test=False).search([
                ('githost_id', '=', self.id),
                '|', ('name', '=', item.get('name')),
                ('external_id_git', '=', item.get('id')),
            ])
            if existing_group:
                existing_group.update(values)
            else:
                group_obj.create(values)

        return self

    name = fields.Char('Name')
    api = fields.Selection(
        selection=[('git_http', 'Git over http'),
                   ('gitlab', 'GitLab API'),
                   ('github', 'GitHub API'), ],
        string='API')
    auth_public = fields.Boolean(
        'Auth Public',
        help='If auth required for this host, uncheck this option',
        default=True)
    active = fields.Boolean('active', default=True)
    auth_ids = fields.One2many(
        comodel_name='git.credential',
        inverse_name='git_host_id',
        string='Auth Credentials',
    )
    repository_ids = fields.One2many(
        comodel_name='git.repository',
        inverse_name='githost_id',
        string='Repositories',
    )
    gitgroup_ids = fields.One2many(
        comodel_name='git.group',
        inverse_name='githost_id',
        string='Git Group'
    )


class GitCredentials(models.Model):
    _name = 'git.credential'
    _rec_name = 'user_name'
    _order = 'sequence desc, id'

    user_name = fields.Char('User Name')
    user_password = fields.Char('User Password')
    user_token = fields.Char('User Token')
    sequence = fields.Integer('Sequence')
    git_host_id = fields.Many2one(
        comodel_name='git.host', required=True,
        ondelete='cascade', string='Git Host')
    user_id = fields.Many2one(
        comodel_name='res.users',
        required=False,
        ondelete='cascade',
        help='If this field is blank, this credentials can be used by all '
             'users'
    )
    active = fields.Boolean('active', default=True)


class GitBranch(models.Model):
    _name = 'git.branch'

    @api.multi
    def update_modules(self):
        if self.api == 'gitlab':
            return self.update_modules_gitlab()
        else:
            raise exceptions.ValidationError(
                _('Githost api %s not yet implemented') % self.api
            )

    @api.multi
    def update_modules(self):
        module_obj = self.env['odoo.module']
        for branch in self:
            branch.odoo_module_ids.write({'active': False})
            gitapi = branch.githost_id.get_api_object()
            if branch.api == 'gitlab':
                tree_data = gitapi.get_files(
                    branch.repository_id.external_id_git,
                    branch.name)
            elif branch.api == 'github':
                tree_data = gitapi.get_files(
                    branch.repository_id.gitgroup_id.name,
                    branch.repository_id.name,
                    branch.name)
            else:
                raise exceptions.ValidationError(
                    _('Githost api %s not yet implemented') % branch.api
                )

            for item in tree_data:
                if item.get('type') != 'tree':
                    continue
                values = {
                    'name': item.get('name') or item.get('path'),
                    'branch_id': branch.id,
                    'active': True,
                }
                existing_branch = module_obj.with_context(
                    active_test=False).search(
                    [
                        ('branch_id', '=', branch.id),
                        ('name', '=', values.get('name')),
                    ])
                if existing_branch:
                    existing_branch.update(values)
                else:
                    module_obj.create(values)

    @api.multi
    def name_get(self):
        return [
            (
                b.id, "%s (%s) - %s:%s" % (
                    b.repository_id.name, b.name,
                    b.repository_id.githost_id.name,
                    b.repository_id.gitgroup_id.name,
                )
            ) for b in self
            ]

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if not args:
            args = []

        # search for repo_name and branch name toghether, with and without
        # branckets
        match_1 = re.search('(\S+) \((\S+)\)', name)
        match_2 = re.search('(\S+) \(?(\S+)', name)
        if match_1:
            domain = [
                ('repository_id.name', operator, match_1.group(1)),
                ('name', operator, match_1.group(2))
            ]
        elif match_2:
            domain = [
                ('repository_id.name', operator, match_2.group(1)),
                ('name', operator, match_2.group(2))
            ]
        else:
            domain = [('repository_id.name', operator, name)]

        recs = self.search(domain + args, limit=limit)

        return recs.name_get()

    name = fields.Char('Name')
    repository_id = fields.Many2one(
        comodel_name='git.repository',
        string='Repository',
        required=True,
        ondelete='cascade',
    )
    githost_id = fields.Many2one(
        comodel_name='git.host',
        related='repository_id.githost_id',
        auto_join=True,
    )
    gitgroup_id = fields.Many2one(
        comodel_name='git.group',
        related='repository_id.gitgroup_id',
        auto_join=True,
    )
    api = fields.Selection(
        related='repository_id.githost_id.api'
    )
    odoo_module_ids = fields.One2many(
        comodel_name='odoo.module',
        inverse_name='branch_id',
        string='Odoo Modules'
    )
    odoo_version = fields.Selection(
        selection=ODOO_VERSIONS,
        string='odoo version')
    gitproject_id = fields.Many2one(
        related='repository_id.gitproject_id',
        readonly=True,
        auto_join=True,
    )
    ref_name = fields.Char('Ref name')
    active = fields.Boolean('active', default=True)


class GitProject(models.Model):
    _name = 'git.project'
    _description = 'represents a certain git project, which might be forked ' \
                   'in several repositories on several hosts'

    name = fields.Char('name')
    description = fields.Char('Description')
    active = fields.Boolean('active', default=True)

    _sql_constraints = [
        ('name_unique',
         'UNIQUE(name)',
         "This Git Project name is already in use"),
    ]

    @api.returns('git.project')
    @api.model
    def find_by_name(self, name):
        record = self.with_context(active_test=False).search(
            [('name', '=', name)])
        if not record:
            record = self.create({
                'name': name,
            })
        return record


class GitGroup(models.Model):
    _name = 'git.group'
    _description = 'github organisations / gitlab groups'

    @api.multi
    def add_group_repositories(self):
        self.ensure_one()

        githost = self.githost_id
        gitgroup = self

        gitapi = githost.get_api_object()
        repository_obj = self.env['git.repository']
        gitproject_obj = self.env['git.project']

        if githost.api == 'gitlab':
            repository_data = gitapi.get_projects(gitgroup.external_id_git)
        elif gitapi.name == 'github':
            if gitgroup.group_type == 'group':
                repository_data = gitapi.get_projects(group_name=gitgroup.name)
            elif gitgroup.group_type == 'user':
                repository_data = gitapi.get_projects(user_name=gitgroup.name)
        else:
            raise exceptions.ValidationError(
                _('Githost api %s not yet implemented') % githost.api
            )
        repository_obj.search([
            ('gitgroup_id', '=', gitgroup.id),
            ('githost_id', '=', githost.id),
        ]).write({'active': False})

        for item in repository_data:

            values = get_values(gitapi.name, item)
            values.update({
                'gitgroup_id': gitgroup.id,
                'githost_id': githost.id,
                'active': True,
                'gitproject_id': gitproject_obj.find_by_name(
                    values.get('name')).id,
            })
            domain = [
                ('gitgroup_id', '=', gitgroup.id),
                ('githost_id', '=', githost.id),
                ('external_id_git', '=', values.get('external_id_git'))
            ]
            existing_repo = repository_obj.with_context(
                active_test=False).search(domain)
            if existing_repo:
                existing_repo.write(values)
            else:
                existing_repo.create(values)

    name = fields.Char('name')
    description = fields.Char('description')
    active = fields.Boolean('active', default=True)
    githost_id = fields.Many2one(
        comodel_name='git.host',
        string='Git Host',
    )
    group_type = fields.Selection(
        selection=[('group', 'Organisation / Group'), ('user', 'User')],
        string='Group Type',
        default='group',
    )

    # gitlab specific field
    external_id_git = fields.Integer('git external api id')


class GitRepository(models.Model):
    _name = 'git.repository'

    @api.multi
    def update_branches(self):

        branch_obj = self.env['git.branch']

        def guess_version(version):
            for odoo_version, odoo_version_string in ODOO_VERSIONS:
                if version.startswith(odoo_version):
                    return odoo_version
            # else
            return False

        for repository in self:
            # set all branches to inactive
            repository.branch_ids.write({'active': False})
            gitapi = repository.githost_id.get_api_object()

            if repository.api == 'gitlab':
                branch_data = gitapi.get_branches(
                    repository.external_id_git)
            elif repository.api == 'github':
                branch_data = gitapi.get_branches(
                    repository.gitgroup_id.name,
                    repository.name)
            else:
                raise exceptions.ValidationError(
                    _('Githost api %s not yet implemented') % repository.api
                )

            for item in branch_data:
                values = {
                    'name': item.get('name'),
                    'odoo_version': guess_version(item.get('name')),
                    'repository_id': repository.id,
                    'active': True,
                }
                existing_branch = branch_obj.with_context(
                    active_test=False).search(
                    [
                        ('repository_id', '=', repository.id),
                        ('name', '=', item.get('name')),
                    ])
                if existing_branch:
                    existing_branch.update(values)
                else:
                    branch_obj.create(values)

    name = fields.Char('Name')
    description = fields.Char('Description')

    branch_ids = fields.One2many(
        comodel_name='git.branch',
        inverse_name='repository_id',
        string='Default branch')
    githost_id = fields.Many2one(
        comodel_name='git.host',
        string='Git Host',
        required=True,
        ondelete='cascade',
    )
    api = fields.Selection(
        related='githost_id.api'
    )
    gitproject_id = fields.Many2one(
        comodel_name='git.project',
        string='Git Project',
        required=True,
    )
    gitgroup_id = fields.Many2one(
        comodel_name='git.group',
        string='Git Group'
    )
    gitpath_http = fields.Char('Path (http)')
    gitpath_ssh = fields.Char('Path (ssh)')
    active = fields.Boolean('active', default=True)

    # gitlab specific field
    external_id_git = fields.Integer('git external api id')
