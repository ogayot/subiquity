# Copyright 2024 Canonical, Ltd.
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


class RecoverableError(Exception):
    """An error type that can be treated as non-fatal when raised from a
    request handler."""

    # If this exception is uncaught in a request handler, what should we do.
    # By default we produce a crash report, but one can change set it to False.
    produce_crash_report = True
