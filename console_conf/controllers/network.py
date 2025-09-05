# Copyright 2025 Canonical, Ltd.
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
import subprocess

import subiquitycore.controllers.network

log = logging.getLogger("console_conf.controllers.network")


class NetworkController(subiquitycore.controllers.network.NetworkController):
    async def _apply_config(self, *args, **kwargs) -> None:
        try:
            await super()._apply_config(*args, **kwargs)
        except subprocess.CalledProcessError as exc:
            log.exception("_apply_config failed")
