# Copyright 2015 Canonical, Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging

import attrs

log = logging.getLogger("console_conf.models.identity")


@attrs.define
class User(object):
    realname = attrs.field()
    username = attrs.field()
    homedir = attrs.field(default=None)


class IdentityModel(object):
    """Model representing user identity"""

    def __init__(self):
        self._user = None

    def add_user(self, result):
        result = result.copy()
        self._user = User(**result)

    @property
    def user(self):
        return self._user

    def __repr__(self):
        return "<LocalUser: {}>".format(self.user)
