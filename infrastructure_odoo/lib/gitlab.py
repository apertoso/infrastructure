# -*- coding: utf-8 -*-

import requests


class Gitlab(object):
    def __init__(self, gitlab_host=False, token=False):
        self.auth_token = False
        self.gitlab_host = gitlab_host
        self.gitlab_url = 'https://%s' % gitlab_host
        self.gitlab_items_per_page = 20
        self.name = 'gitlab'
        if token:
            self.set_auth_token(token)

    def set_auth_token(self, token):
        self.auth_token = token

    def get_auth_header(self):
        if self.auth_token:
            return {'PRIVATE-TOKEN': self.auth_token}
        else:
            return {}

    def get_groups(self, headers=None):
        return self.get_data('/api/v3/groups', headers)

    def get_projects(self, group_id=False, headers=None):
        return self.get_data('/api/v3/groups/%s/projects' % group_id, headers)

    def get_branches(self, project_id, headers=None):
        return self.get_data(
            '/api/v3/projects/%s/repository/branches' % project_id, headers)

    # Get files & folders in repository, from specific branch_name
    # Results from type tree, seem to be folders
    def get_files(self, project_id, ref_name, headers=None):
        return self.get_data(
            '/api/v3/projects/%s/repository/tree' % project_id,
            headers=headers, data={'ref_name': ref_name})

    def get_data(self, path, headers=None, data=None):
        # work with pagination link headers and raise exceptions
        if not headers:
            headers = {}
        if not data:
            data = {}
        headers.update(self.get_auth_header())
        data.update({'per_page': self.gitlab_items_per_page})

        url = self.gitlab_url + path
        results = []
        # check if status != 200
        while url:
            r = requests.get(url, data=data, headers=headers)
            r.raise_for_status()
            results.extend(r.json())
            link_next = r.links.get('next', False)
            if link_next:
                url = link_next.get('url')
            else:
                url = False

        return results
