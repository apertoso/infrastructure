# -*- coding: utf-8 -*-
from openerp import fields, models, api, exceptions, _


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


class WizardImportGit(models.TransientModel):
    _name = "wizard.import.git"

    githost_id = fields.Many2one(
        comodel_name='git.host',
        required=True,
        default=lambda self: self.env.context.get('active_id'),
    )
    gitgroup_id = fields.Many2one(
        comodel_name='git.group',
        domain="[('githost_id','=',githost_id)]",
        string='Git Group',
    )
    repository_ids = fields.Many2many(
        comodel_name='wizard.import.git.repository',
        domain="[('gitgroup_id', '=', gitgroup_id),"
               " ('githost_id', '=', githost_id)]",
        string="Repositories",
    )

    @api.onchange('gitgroup_id')
    def do_search_repositories(self):

        githost = self.env['git.host'].browse(self.githost_id.id)
        gitgroup = self.env['git.group'].browse(self.gitgroup_id.id)

        if not gitgroup:
            return

        wizard_imp_repo_obj = self.env['wizard.import.git.repository']

        gitapi = githost.get_api_object()

        if gitapi.name == 'gitlab':
            repository_data = gitapi.get_projects(gitgroup.external_id_git)
        elif gitapi.name == 'github':
            if gitgroup.group_type == 'group':
                repository_data = gitapi.get_projects(group_name=gitgroup.name)
            if gitgroup.group_type == 'user':
                repository_data = gitapi.get_projects(user_name=gitgroup.name)
        else:
            raise exceptions.ValidationError(
                _('Githost api %s not yet implemented') % self.api
            )

        # remove old data
        existing_ids_set = set(
            wizard_imp_repo_obj.with_context(active_test=False).search(
                [
                    ('gitgroup_id', '=', gitgroup.id),
                    ('githost_id', '=', githost.id),
                ]).ids)
        updated_ids_set = set()

        # don't add repo's already in odoo
        existing_repo_git_ids = self.env['git.repository'].with_context(
            active_test=False).search(
            [
                ('githost_id', '=', githost.id),
                ('gitgroup_id', '=', gitgroup.id)]
        ).mapped('external_id_git')

        for item in repository_data:
            if item.get('id') in existing_repo_git_ids:
                continue
            values = get_values(gitapi.name, item)
            values.update({
                'gitgroup_id': gitgroup.id,
                'githost_id': githost.id,
            })
            domain = [
                ('gitgroup_id', '=', gitgroup.id),
                ('githost_id', '=', githost.id),
                ('external_id_git', '=', values.get('external_id_git'))
            ]
            existing_wizard_imp_repo = wizard_imp_repo_obj.with_context(
                active_test=False).search(domain)
            if existing_wizard_imp_repo:
                existing_wizard_imp_repo.write(values)
                updated_ids_set.add(existing_wizard_imp_repo.id)
            else:
                existing_wizard_imp_repo.create(values)
        wizard_imp_repo_obj.with_context(active_test=False).search(
            [('id', 'in', list(existing_ids_set - updated_ids_set))]).unlink()

    @api.multi
    def do_create_repositories(self):
        self.ensure_one()
        git_repo_obj = self.env['git.repository']
        for repo in self.repository_ids:
            git_repo_obj.create({
                'name': repo.name,
                'description': repo.description,
                'external_id_git': repo.external_id_git,
                'githost_id': repo.githost_id.id,
                'gitgroup_id': repo.gitgroup_id.id,
                'gitproject_id': self.env['git.project'].find_by_name(
                    repo.name).id,
                'gitpath_http': repo.gitpath_http,
                'gitpath_ssh': repo.gitpath_ssh,
            })


class WizardImportGitRepository(models.TransientModel):
    _name = 'wizard.import.git.repository'
    _order = 'name'

    name = fields.Char('name')
    description = fields.Char('description')
    external_id_git = fields.Integer('git id')
    githost_id = fields.Many2one(
        comodel_name='git.host',
        string='git host id',
        required=True,
        ondelete='cascade',
    )
    gitgroup_id = fields.Many2one(
        comodel_name='git.group',
        string='git group id',
        required=True,
        ondelete='cascade',
    )
    gitpath_http = fields.Char('gitpath_http')
    gitpath_ssh = fields.Char('gitpath_ssh')
