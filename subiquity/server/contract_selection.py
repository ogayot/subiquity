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
""" Module that deals with contract token selection. """

import asyncio
import logging

import aiohttp

from subiquity.server.ua_contracts import UAContractsClient

from subiquitycore.async_helpers import schedule_task


log = logging.getLogger("subiquity.server.contract_selection")


class UPCSExpiredError(Exception):
    """ Exception to be raised when a contract selection expired. """


class ContractSelection:
    def __init__(
            self,
            client: UAContractsClient,
            magic_token: str,
            confirmation_code: str,
            validity_seconds: int) -> None:
        """ Initialize the contract selection. """
        self.client = client
        self.magic_token = magic_token
        self.confirmation_code = confirmation_code
        self.validity_seconds = validity_seconds
        self.task = asyncio.create_task(self._run_polling())

    @classmethod
    async def initiate(cls, client: UAContractsClient, email: str) \
            -> "ContractSelection":
        """ Initiate a contract selection and return a ContractSelection
        request object. """
        answer = await client.magic_attach_post(email)

        return cls(
                client=client,
                magic_token=answer["token"],
                validity_seconds=answer["expiresIn"],
                confirmation_code=answer["confirmationCode"])

    async def _run_polling(self) -> str:
        """ Runs the polling and eventually return a contract token. """
        # Wait an initlal 30 seconds before sending the first request, then
        # send requests at regular interval every 10 seconds.
        await asyncio.sleep(30)
        while True:
            answer = await \
                    self.client.magic_attach_get(magic_token=self.magic_token)

            if answer is None:
                raise UPCSExpiredError

            if "contractToken" in answer:
                return answer["contractToken"]

            await asyncio.sleep(10)

    def cancel(self):
        """ Cancel the polling task and asynchronously delete the associated
        resource. """
        self.task.cancel()

        async def delete_resource() -> None:
            """ Release the resource on the server. """
            try:
                await self.client.magic_attach_delete(
                        magic_token=self.magic_token)
            except aiohttp.ClientError as e:
                log.warn("failed to revoke magic-token: %r", e)
            else:
                log.debug("successfully revoked magic-token")

        schedule_task(delete_resource())
