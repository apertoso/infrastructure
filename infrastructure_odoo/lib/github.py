# -*- coding: utf-8 -*-

import requests


class Github(object):
    def __init__(self, auth_user=False, auth_token=False):
        self.auth = None
        if auth_user and auth_token:
            self.auth = (auth_user, auth_token)
        self._url = 'https://api.github.com'
        self._items_per_page = 20
        self.name = 'github'
        self.default_header = {
            'Accept': 'application / vnd.github.v3 + json'
        }

    def get_groups(self, headers=None):
        raise NotImplementedError

    def get_projects(self, group_name=False, user_name=False, headers=None):
        if group_name:
            return self.get_data('/orgs/%s/repos' % group_name, headers)
        elif user_name:
            return self.get_data('/users/%s/repos' % user_name, headers)

    def get_branches(self, group_name, project_name, headers=None):
        return self.get_data(
            '/repos/%s/%s/branches' % (group_name, project_name), headers)

    # Get files & folders in repository, from specific branch_name
    # Results from type tree, seem to be folders
    def get_files(self, group_name, project_name, branch_name, headers=None):
        data = self.get_data_dict('/repos/%s/%s/git/trees/%s' % (
            group_name, project_name, branch_name),
            headers=headers)
        return data.get('tree', [])

    def get_data_dict(self, path, headers=None, data=None):
        # work with pagination link headers and raise exceptions
        if not headers:
            headers = {}
        if not data:
            data = {}
        headers.update(self.default_header)
        url = self._url + path
        r = requests.get(url, data=data, headers=headers, auth=self.auth)
        r.raise_for_status()
        return r.json()

    def get_data(self, path, headers=None, data=None):
        # work with pagination link headers and raise exceptions
        if not headers:
            headers = {}
        if not data:
            data = {}
        headers.update(self.default_header)
        data.update({'per_page': self._items_per_page})

        url = self._url + path
        results = []
        while url:
            r = requests.get(url, data=data, headers=headers, auth=self.auth)
            r.raise_for_status()
            results.extend(r.json())

            link_next = r.links.get('next', False)
            if link_next:
                url = link_next.get('url')
            else:
                url = False

        return results
