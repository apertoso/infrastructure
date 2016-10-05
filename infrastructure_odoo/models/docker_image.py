# -*- coding: utf-8 -*-

from openerp import fields, models, exceptions, api

GLYPH_ICON_MAP = {
    # http://www.utf8icons.com/character/10060/cross-mark
    'failed': unichr(10060),
    # http://www.utf8icons.com/character/10003/check-mark
    'success': unichr(10003),
}


class DockerImage(models.Model):
    _name = 'docker.image'

    name = fields.Char('Name')
    tag_ids = fields.One2many(comodel_name='docker.image.tag',
                              inverse_name='docker_image_id',
                              string='Tags')
    tags_failed = fields.Integer(
        'Failed Build Tags',
        compute='_get_build_count')
    tags_success = fields.Integer(
        'Successful Build Tags',
        compute='_get_build_count')

    @api.multi
    def _get_build_count(self):
        for rec in self:
            rec.update({
                'tags_failed': len(
                    rec.tag_ids.filtered(lambda t: t.state == 'failed')),
                'tags_success': len(
                    rec.tag_ids.filtered(lambda t: t.state == 'success')),
            })


class DockerImageTag(models.Model):
    _name = 'docker.image.tag'

    name = fields.Char('Name')
    docker_image_id = fields.Many2one('docker.image', 'Image')
    state = fields.Selection(
        string='Build Status',
        selection=[
            ('failed', 'Build Failed'),
            ('success', 'Build Success'),
        ],
        default='failed',
    )
    state_glyph = fields.Char(
        'Build',
        compute='_compute_state_glyph')

    _sql_constraints = [
        ('tag_image_unique',
         'UNIQUE(name, docker_image_id)',
         "This tag name already exists for this image"),
    ]

    @api.multi
    def _compute_state_glyph(self):
        for record in self:
            record.state_glyph = GLYPH_ICON_MAP.get(
                record.state, u'')

    @api.multi
    def name_get(self):
        return [
            (tag.id, u'[%s] %s:%s' % (
                tag.state_glyph,
                tag.docker_image_id.name,
                tag.name))
            for tag in self
            ]

    @api.model
    def set_docker_image_state(self, docker_image_name,
                               docker_image_tag_name, state):

        docker_image = self.docker_image_id.search(
            [
                ('name', '=', docker_image_name),
            ], limit=1
        )
        if not docker_image:
            raise exceptions.ValidationError('Docker image not found')

        docker_image_tag = self.search(
            [
                ('name', '=', docker_image_tag_name),
                ('docker_image_id', '=', docker_image.id)
            ], limit=1
        )
        if docker_image_tag:
            docker_image_tag.state = state
        else:
            self.create({
                'name': docker_image_tag_name,
                'docker_image_id': docker_image.id,
                'state': state,
            })
