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
""" Module that define widgets that can show a countdown. """

import asyncio
import time
from typing import Optional

from urwid import Text

from subiquitycore.async_helpers import schedule_task


class CountdownSeconds(Text):
    """ Widget that goes from X seconds to 0 and then stops counting. """
    def __init__(self, duration: int) -> None:
        """ Initializes the countdown with the initial number of seconds. """
        self.duration = duration
        self.handle: Optional[asyncio.Task] = None
        super().__init__("", align="center")

    def update(self) -> None:
        """ Update the text using the current number of seconds remaining.
        Raises StopIteration if the counter reaches 0. """
        remaining = self.end_time - time.monotonic()

        if remaining <= 0:
            self.set_text("00:00")
            raise StopIteration

        minutes = int(remaining / 60)
        seconds = int(remaining % 60)
        self.set_text(f"{minutes:02d}:{seconds:02d}")

    def start(self) -> None:
        """ Start counting down and refresh periodically until we reach 0. """
        async def count_down(rate_seconds: int = 1) -> None:
            while True:
                try:
                    self.update()
                except StopIteration:
                    break
                await asyncio.sleep(rate_seconds)

        self.end_time = time.monotonic() + self.duration
        self.handle = schedule_task(count_down())

    def stop(self):
        """ Stop counting down. """
        self.handle.cancel()
        self.handle = None
