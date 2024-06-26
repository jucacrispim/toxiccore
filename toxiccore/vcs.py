# -*- coding: utf-8 -*-

# Copyright 2015, 2018, 2023 Juca Crispim <juca@poraodojuca.net>

# This file is part of toxicbuild.

# toxicbuild is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# toxicbuild is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with toxicbuild. If not, see <http://www.gnu.org/licenses/>.

from abc import ABCMeta, abstractmethod
import os
from .exceptions import VCSError, ExecCmdError
from .utils import (exec_cmd, inherit_docs, string2datetime,
                    datetime2string, utc2localtime,
                    localtime2utc, LoggerMixin, match_string)


class VCS(LoggerMixin, metaclass=ABCMeta):

    """ Generic inteface to a vcs (clone, fetch, get revisions etc...).
    """
    vcsbin = None

    def __init__(self, workdir):
        """:param workdir: Directory where repository will be cloned and
        all action will happen.
        """
        self.workdir = workdir

    async def exec_cmd(self, cmd, cwd=None):
        """ Executes a shell command. If ``cwd`` is None ``self.workdir``
        will be used.

        :param cwd: Directory where the command will be executed.
        """
        if cwd is None:
            cwd = self.workdir

        ret = await exec_cmd(cmd, cwd)
        return ret

    def workdir_exists(self):
        """ Informs if the workdir for this vcs exists
        """
        return os.path.exists(self.workdir)

    @abstractmethod  # pragma no branch
    async def clone(self, url):
        """ Clones a repository into ``self.workdir``
        :param url: repository url
        """

    @abstractmethod  # pragma no branch
    async def fetch(self):
        """ Fetch changes from remote repository
        """

    @abstractmethod  # pragma no branch
    async def create_local_branch(self, branch_name, base_name):
        """Creates a branch new in the local repository

        :param branch_name: The name for the new branch
        :param base_name: The name of the base branch."""

    @abstractmethod
    async def delete_local_branch(self, branch_name):
        """Deletes a local branch.

        :param branch_name: The name of the branch to be deleted."""

    @abstractmethod  # pragma no branch
    async def set_remote(self, url, remote_name):
        """Sets the remote url of the repository.

        :param url: The new remote url.
        :param remote_name: The name of the remote url to change."""

    @abstractmethod  # pragma no branch
    async def get_remote(self, remote_name):
        """Returns the remote url used in the repo.

        :param remote_name: The name of the remote url to change."""

    @abstractmethod
    async def try_set_remote(self, url, remote_name):  # pragma no branch
        """Sets the remote url if the remote is not equal as url.

        :param url: The new url for the remote.
        :param remote_name: The name of the remote url to change."""

    @abstractmethod  # pragma no branch
    async def add_remote(self, remote_url, remote_name):
        """Adds a new remote to the repository.

        :param remote_url: The url of the remote repository.
        :param remote_name: The name of the remote."""

    @abstractmethod  # pragma no branch
    async def checkout(self, named_tree):
        """ Checkout to ``named_tree``
        :param named_tree: A commit, branch, tag...
        """

    @abstractmethod  # pragma no branch
    async def pull(self, branch_name, remote_name='origin'):
        """ Pull changes from ``branch_name`` on remote repo.

        :param branch_name: A branch name, like 'master'.
        :param remote_name: The remote repository to push from.
        """

    @abstractmethod  # pragma no branch
    async def has_changes(self):
        """ Informs if there are new revisions in the repository
        """

    @abstractmethod
    async def import_external_branch(self, external_url, external_name,
                                     external_branch, into):
        """Imports a branch from an external (not the origin one)
        repository into a local branch.

        :param external_url: The url of the external repository.
        :param external_name: Name to idenfity the remote url.
        :param external_branch: The name of the branch in the external repo.
        :param into: The name of the local branch."""

    @classmethod  # pragma no branch
    async def branch_exists(self, branch_name):
        """Checks if a local branch exists.

        :param branch_name: The name of the branch to check."""

    @abstractmethod  # pragma no branch
    async def get_revisions(self, since=None, branches=None):
        """Returns the newer revisions ``since`` for ``branches`` from
        the default remote repository.

        :param since: dictionary in the format: {branch_name: since_date}.
          ``since`` is a datetime object.
        :param branches: A list of branches to look for new revisions. If
          ``branches`` is None all remote branches will be used. You can use
          wildcards in branches to filter the remote branches.
        """

    @abstractmethod  # pragma no branch
    async def get_local_revisions(self, since=None, branches=None):
        """Returns the newer revisions ``since`` for ``branches`` in the
        local repository

        :param since: dictionary in the format: {branch_name: since_date}.
          ``since`` is a datetime object.
        :param branches: A list of branches to look for new revisions. If
          ``branches`` is None all remote branches will be used. You can use
          wildcards in branches to filter the local branches.
        """

    @abstractmethod  # pragma no branch
    async def get_revisions_for_branch(self, branch, since=None):
        """ Returns the revisions for ``branch`` since ``since``.
        If ``since`` is None, all revisions will be returned.

        :param branch: branch name
        :param since: datetime
        """

    @abstractmethod  # pragma no branch
    async def get_remote_branches(self):
        """ Returns a list of the remote branches available.
        """

    def _filter_remote_branches(self, remote_branches, branch_filters):
        """Filters the remote branches based in filters for the branches'
        names."""

        return [b for b in remote_branches if match_string(b, branch_filters)]


@inherit_docs
class Git(VCS):

    """ An interface to git version control system
    """

    vcsbin = 'git'
    # this date_format is used to ask git about revisions since
    # some date
    date_format = '%a %b %d %H:%M:%S %Y'
    _commit_separator = '<end-toxiccommit>'

    async def _set_remote_origin_config(self):
        # when we do a shallow clone of a repo, we need to
        # set the remote origins to * otherwise we will not
        # be able to fetch all remote branches.
        remote = '+refs/heads/*:refs/remotes/origin/*'
        cmd = '{} config remote.origin.fetch {}'.format(self.vcsbin,
                                                        remote)
        await self.exec_cmd(cmd, cwd=self.workdir)

    async def clone(self, url):

        cmd = '%s clone --depth=2 %s %s --recursive' % (
            self.vcsbin, url, self.workdir)
        # we can't go to self.workdir while we do not clone the repo
        await self.exec_cmd(cmd, cwd='.')
        await self._set_remote_origin_config()

    async def set_remote(self, url, remote_name='origin'):
        cmd = '{} remote set-url {} {}'.format(self.vcsbin, remote_name, url)
        await self.exec_cmd(cmd)

    async def get_remote(self, remote_name='origin'):
        cmd = r"{} remote -v | grep -m1 {} | sed -e 's/{}\s*//g' "
        cmd += "-e 's/(.*)//g'"
        cmd = cmd.format(self.vcsbin, remote_name, remote_name)
        remote = await self.exec_cmd(cmd)
        return remote

    async def add_remote(self, remote_url, remote_name):
        cmd = '{} remote add {} {}'.format(self.vcsbin,
                                           remote_name, remote_url)
        r = await self.exec_cmd(cmd)
        return r

    async def rm_remote(self, remote_name):
        cmd = '{} remote rm {}'.format(self.vcsbin, remote_name)
        r = await self.exec_cmd(cmd)
        return r

    async def try_set_remote(self, url, remote_name='origin'):
        current_remote = await self.get_remote(remote_name)
        if current_remote != url:
            self.log('Changing remote from {} to {}'.format(
                current_remote, url), level='debug')
            await self.set_remote(url, remote_name)

    async def fetch(self):
        cmd = '%s %s' % (self.vcsbin, 'fetch')

        fetched = await self.exec_cmd(cmd)
        return fetched

    async def create_local_branch(self, branch_name, base_name):

        await self.checkout(base_name)
        cmd = '{} branch {}'.format(self.vcsbin, branch_name)
        r = await self.exec_cmd(cmd)
        return r

    async def delete_local_branch(self, branch_name):
        await self.checkout('master')
        cmd = '{} branch -D {}'.format(self.vcsbin, branch_name)
        r = await self.exec_cmd(cmd)
        return r

    async def checkout(self, named_tree):

        cmd = '{} checkout {}'.format(self.vcsbin, named_tree)
        await self.exec_cmd(cmd)

    async def pull(self, branch_name, remote_name='origin'):

        # rebase here because we don't care about the
        # ci's repo history. Whatever the original repo
        # does we simply follow
        cmd = '{} pull --no-edit {} {} --rebase'.format(
            self.vcsbin, remote_name,
            branch_name)

        ret = await self.exec_cmd(cmd)
        return ret

    async def has_changes(self):
        ret = await self.fetch()
        return bool(ret)

    async def import_external_branch(self, external_url, external_name,
                                     external_branch, into):
        exists = await self.branch_exists(into)
        if not exists:
            await self.create_local_branch(into, 'master')

        await self.add_remote(external_url, external_name)
        await self.checkout(into)
        await self.pull(external_branch, external_name)
        await self.rm_remote(external_name)

    async def branch_exists(self, branch_name):
        cmd = '{} rev-parse --verify {}'.format(self.vcsbin, branch_name)
        try:
            await self.exec_cmd(cmd)
            exists = True
        except ExecCmdError:
            exists = False

        return exists

    async def update_submodule(self):
        cmd = '{} submodule init'.format(self.vcsbin)
        await self.exec_cmd(cmd)
        cmd = '{} submodule update'.format(self.vcsbin)
        ret = await self.exec_cmd(cmd)
        return ret

    async def get_local_revisions(self, since=None, branches=None):
        since = since or {}
        branches = branches or []
        revisions = {}
        for branch in branches:
            try:
                await self.checkout(branch)
                since_date = since.get(branch)
                revs = await self.get_revisions_for_branch(branch, since_date)
                if revs:
                    revisions[branch] = revs
            except Exception as e:
                msg = 'Error fetching local changes on branch {}. {}'.format(
                    branch, str(e))
                self.log(msg, level='error')
        return revisions

    async def get_revisions(self, since=None, branches=None):

        since = since or {}
        # this must be called everytime so we sync our repo
        # with the remote repo and then we can see new branches
        await self.fetch()
        remote_branches = await self.get_remote_branches()
        if branches:
            remote_branches = self._filter_remote_branches(
                remote_branches, branches)

        revisions = {}
        for branch in remote_branches:
            try:
                await self.checkout(branch)
                await self.pull(branch)
                since_date = since.get(branch)

                revs = await self.get_revisions_for_branch(branch,
                                                           since_date)
                if revs:
                    revisions[branch] = revs
            except Exception as e:
                msg = 'Error fetching changes on branch {}. {}'.format(
                    branch, str(e))
                self.log(msg, level='error')

        return revisions

    async def get_revisions_for_branch(self, branch, since=None):
        # hash | commit date | author | title
        commit_fmt = "%H | %ad | %an | %s | %+b {}".format(
            self._commit_separator)
        cmd = '{} log --pretty=format:"{}" '.format(
            self.vcsbin, commit_fmt)
        if since:
            # Here we change the time to localtime since we can't get
            # utc time in git commits unless we are using git 2.7+
            localtime = utc2localtime(since)
            date = datetime2string(localtime, self.date_format)
            self.log('get revisions for branch {} since {}'.format(branch,
                                                                   date),
                     level='debug')
            cmd += '--since="%s" ' % date

        cmd += '--date=local'
        msg = 'Getting revisions for branch {} with command {}'.format(
            branch, cmd)
        self.log(msg, level='debug')
        last_revs = [r for r in (await self.exec_cmd(cmd)).split(
            self._commit_separator + '\n') if r]
        last_revs.reverse()
        self.log('Got {}'.format(last_revs), level='debug')
        revisions = []

        for rev in last_revs:
            rev_uuid, date, author, title, body = rev.split(' | ')
            date = string2datetime(date.strip(), dtformat=self.date_format)
            # Here we change the date from git, that is in localtime to
            # utc before saving to database.
            date = localtime2utc(date)
            revisions.append({'commit': rev_uuid.strip(), 'commit_date': date,
                              'author': author, 'title': title, 'body': body})

        # The thing here is that the first revision in the list
        # is the last one consumed on last time
        return revisions[1:]

    async def get_remote_branches(self):
        await self.fetch()
        await self._update_remote_prune()
        cmd = '%s branch -r' % self.vcsbin

        out = await self.exec_cmd(cmd)
        msg = 'Remote branches: {}'.format(out)
        self.log(msg, level='debug')
        remote_branches = out.split('\n')
        # master, with some shitty arrow...
        parts = remote_branches[0].split('->')
        if len(parts) > 1:
            remote_branches[0] = parts[1].strip()
        else:
            remote_branches[0] = parts[0].strip()

        return set([b.strip().split('/', 1)[1] for b in remote_branches])

    async def _update_remote_prune(self):
        """Updates remote branches list, prunning deleted branches."""

        cmd = '{} remote update --prune'.format(self.vcsbin)
        msg = 'Updating --prune remote'
        self.log(msg, level='debug')
        await self.exec_cmd(cmd)


VCS_TYPES = {'git': Git}


def get_vcs(vcs_type):
    """ Retuns a subclass of :class:`..vcs.VCS` for ``vcs_type``
    """
    vcs = VCS_TYPES.get(vcs_type)
    if not vcs:
        raise VCSError('VCS not found for {}'.format(vcs_type))
    return vcs
