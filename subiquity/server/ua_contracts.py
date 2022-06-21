# Copyright 2022 Canonical, Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
""" This module defines utilities to interface with the u-a contracts service.
"""

from typing import Any

import aiohttp
import yarl


PRODUCTION_BASE_URL = "https://contracts.canonical.com"
STAGING_BASE_URL = "https://contracts.staging.canonical.com"


class UAContractsClient:
    """ A class that can be used to communicate with u-a contracts through
    HTTP. """

    # NOTE: It is bad to construct a new ClientSession for each request.
    # However, it is recommended to always create ClientSession from an async
    # function: https://docs.aiohttp.org/en/stable/faq.html#id15.
    # Let's not replace the calls to aiohttp.ClientSession by a single call in
    # the constructor for now.
    def __init__(self, base_url: str = PRODUCTION_BASE_URL) -> None:
        """ Initializer. Configures the base URL. """
        self.base_url = yarl.URL(base_url)
        self.endpoint = yarl.URL("/v1/magic-attach")

    async def magic_attach_post(self, email: str) -> Any:
        """ Perform a POST to /v1/magic-attach and return the data from the
        response. """
        async with aiohttp.ClientSession() as session:
            data = {"email": email}
            headers = {"Content-Type": "application/json"}
            async with session.post(self.base_url.join(self.endpoint),
                                    json=data, headers=headers) as response:
                response.raise_for_status()
                return await response.json()

    async def magic_attach_get(self, magic_token: str) -> Any:
        """ Perform a GET to /v1/magic-attach and return the data from the
        response. If the response is a 401, then None is returned. """
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {magic_token}"}
            async with session.get(self.base_url.join(self.endpoint),
                                   headers=headers) as response:
                if response.status == 401:
                    return None
                response.raise_for_status()
                return await response.json()

    async def magic_attach_delete(self, magic_token: str) -> None:
        """ Perform a DELETE to /v1/magic-attach. """
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {magic_token}"}
            async with session.delete(self.base_url.join(self.endpoint),
                                      headers=headers) as response:
                response.raise_for_status()
