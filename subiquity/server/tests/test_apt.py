# Copyright 2021 Canonical, Ltd.
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

import contextlib
import io
import pathlib
import subprocess
import tempfile
from collections import namedtuple
from unittest.mock import AsyncMock, Mock, patch

from curtin.commands.extract import TrivialSourceHandler

from subiquity.models.mirror import MirrorModel
from subiquity.models.proxy import ProxyModel
from subiquity.models.subiquity import DebconfSelectionsModel
from subiquity.server.apt import (
    AptConfigCheckError,
    AptConfigurer,
    DryRunAptConfigurer,
    OverlayMountpoint,
)
from subiquity.server.dryrun import DRConfig
from subiquitycore.tests import SubiTestCase
from subiquitycore.tests.mocks import make_app
from subiquitycore.tests.parameterized import parameterized
from subiquitycore.utils import astart_command

APT_UPDATE_SUCCESS = """\
Hit:1 http://mirror focal InRelease
Get:2 http://mirror focal-updates InRelease [109 kB]
Get:3 http://mirror focal-backports InRelease [99,9 kB]
Get:4 http://mirror focal-security InRelease [109 kB]
Get:5 http://mirror focal-updates/main amd64 DEP-11 Metadata [22,5 kB]
Get:6 http://mirror focal-updates/universe amd64 DEP-11 Metadata [33,6 kB]
"""

APT_UPDATE_FAILURE = """\
Err:1 http://bad-mirror focal-updates InRelease
  Could not resolve 'arcive.ubuntu.com'
Hit:2 http://mirror focal InRelease
Hit:3 http://security.ubuntu.com/ubuntu focal-security InRelease
Hit:4 http://mirror focal-updates InRelease
Hit:5 http://mirror focal-backports InRelease
Reading package lists... Done
E: Failed to fetch http://bad-mirror/dists/focal-updates/InRelease \
Could not resolve 'bad-mirror'
E: Some index files failed to download. \
They have been ignored, or old ones used instead.
"""


class TestAptConfigurer(SubiTestCase):
    def setUp(self):
        self.model = Mock()
        self.model.mirror = MirrorModel()
        self.model.mirror.create_primary_candidate("http://mymirror").elect()
        self.model.proxy = ProxyModel()
        self.model.debconf_selections = DebconfSelectionsModel()
        self.model.locale.selected_language = "en_US.UTF-8"
        self.app = make_app(self.model)
        self.configurer = AptConfigurer(self.app, AsyncMock(), TrivialSourceHandler(""))

        self.astart_sym = "subiquity.server.apt.astart_command"

    def test_apt_config_noproxy(self):
        config = self.configurer.apt_config(final=True)
        self.assertNotIn("http_proxy", config["apt"])
        self.assertNotIn("https_proxy", config["apt"])

    def test_apt_config_proxy(self):
        proxy = "http://apt-cacher-ng:3142"
        self.model.proxy.proxy = proxy

        config = self.configurer.apt_config(final=True)
        self.assertEqual(proxy, config["apt"]["http_proxy"])
        self.assertEqual(proxy, config["apt"]["https_proxy"])

    async def test_overlay(self):
        self.configurer.install_tree = OverlayMountpoint(
            upperdir="upperdir-install-tree",
            lowers=["lowers1-install-tree"],
            mountpoint="mountpoint-install-tree",
        )
        self.configurer.configured_tree = OverlayMountpoint(
            upperdir="upperdir-install-tree",
            lowers=["lowers1-install-tree"],
            mountpoint="mountpoint-install-tree",
        )
        self.source = "source"

        with patch.object(
            self.app, "command_runner", create=True, new_callable=AsyncMock
        ):
            async with self.configurer.overlay():
                pass

    async def test_run_apt_config_check(self):
        self.configurer.configured_tree = OverlayMountpoint(
            upperdir="upperdir-install-tree",
            lowers=["lowers1-install-tree"],
            mountpoint="mountpoint-install-tree",
        )

        async def astart_success(cmd, **kwargs):
            """Simulates apt-get update behaving normally."""
            proc = await astart_command(
                ["sh", "-c", "cat"], **kwargs, stdin=subprocess.PIPE
            )
            proc.stdin.write(APT_UPDATE_SUCCESS.encode("utf-8"))
            proc.stdin.write_eof()
            return proc

        async def astart_failure(cmd, **kwargs):
            """Simulates apt-get update failing."""
            proc = await astart_command(
                ["sh", "-c", "cat; exit 1"], **kwargs, stdin=subprocess.PIPE
            )
            proc.stdin.write(APT_UPDATE_FAILURE.encode("utf-8"))
            proc.stdin.write_eof()
            return proc

        output = io.StringIO()
        with patch(self.astart_sym, side_effect=astart_success):
            await self.configurer.run_apt_config_check(output)
            self.assertEqual(output.getvalue(), APT_UPDATE_SUCCESS)

        output = io.StringIO()
        with patch(self.astart_sym, side_effect=astart_failure):
            with self.assertRaises(AptConfigCheckError):
                await self.configurer.run_apt_config_check(output)

    @staticmethod
    @contextlib.contextmanager
    def naked_apt_dir():
        temp_dir = tempfile.TemporaryDirectory()
        try:
            d = pathlib.Path(temp_dir.name)

            (d / "etc/apt").mkdir(parents=True)
            (d / "etc/apt/apt.conf.d").mkdir()
            (d / "etc/apt/preferences.d").mkdir()
            (d / "etc/apt/sources.list.d").mkdir()

            yield d
        finally:
            temp_dir.cleanup()

    @parameterized.expand(
        [
            (False, "etc/apt/sources.list", False, False),
            (True, "etc/apt/sources.list", True, False),
            (False, "etc/apt/sources.list.d/ubuntu.sources", False, False),
            (True, "etc/apt/sources.list.d/ubuntu.sources", True, True),
            # If ubuntu.sources was removed because we're offline
            (True, "etc/apt/sources.list.d/ubuntu.sources", True, False),
            (False, "etc/apt/sources.list.d/10sy-original.list", True, False),
            (False, "etc/apt/apt.conf.d/90curtin-aptproxy", False, False),
            (True, "etc/apt/apt.conf.d/90curtin-aptproxy", True, True),
            # If 90curtin-aptproxy was removed because we're offline
            (True, "etc/apt/apt.conf.d/90curtin-aptproxy", False, True),
            # Files installed by other packages
            (True, "etc/apt/sources.list.d/oem-foobar-meta.list", True, False),
        ]
    )
    async def test_deconfigure(
        self, expect_found, path: str, in_installed, in_configured
    ):
        """Test if the relevant files are discarded or restored on deconfigured"""
        with self.naked_apt_dir() as target_dir, self.naked_apt_dir() as configured_tree:
            self.configurer.configured_tree = OverlayMountpoint(
                mountpoint=str(configured_tree), lowers=[], upperdir=None
            )

            # This file must always be present
            (target_dir / "etc/apt/sources.list.d/01sy-cdrom.list").touch(
                exist_ok=False
            )

            if in_configured:
                (configured_tree / path).touch(exist_ok=False)
            if in_installed:
                (target_dir / path).touch(exist_ok=False)

            with patch("subiquity.server.apt.run_curtin_command"):
                await self.configurer.deconfigure(context=None, target=str(target_dir))

            self.assertEqual(expect_found, (target_dir / path).exists())
            self.assertFalse(
                (target_dir / "etc/apt/sources.list.d/01sy-cdrom.list").exists()
            )


class TestDRAptConfigurer(SubiTestCase):
    def setUp(self):
        self.model = Mock()
        self.model.mirror = MirrorModel()
        self.candidate = self.model.mirror.primary_candidates[0]
        self.candidate.stage()
        self.app = make_app(self.model)
        self.app.dr_cfg = DRConfig()
        self.app.dr_cfg.apt_mirror_check_default_strategy = "failure"
        self.app.dr_cfg.apt_mirrors_known = [
            {"url": "http://success", "strategy": "success"},
            {"url": "http://failure", "strategy": "failure"},
            {"url": "http://run-on-host", "strategy": "run-on-host"},
            {"pattern": "/random$", "strategy": "random"},
        ]
        self.configurer = DryRunAptConfigurer(self.app, AsyncMock(), "")
        self.configurer.configured_tree = OverlayMountpoint(
            upperdir="upperdir-install-tree",
            lowers=["lowers1-install-tree"],
            mountpoint="mountpoint-install-tree",
        )

    def test_get_mirror_check_strategy(self):
        Strategy = DryRunAptConfigurer.MirrorCheckStrategy
        self.assertEqual(
            Strategy.SUCCESS,
            self.configurer.get_mirror_check_strategy("http://success"),
        )
        self.assertEqual(
            Strategy.FAILURE,
            self.configurer.get_mirror_check_strategy("http://failure"),
        )
        self.assertEqual(
            Strategy.RUN_ON_HOST,
            self.configurer.get_mirror_check_strategy("http://run-on-host"),
        )
        self.assertEqual(
            Strategy.RANDOM,
            self.configurer.get_mirror_check_strategy("http://mirror/random"),
        )
        self.assertEqual(
            Strategy.FAILURE,
            self.configurer.get_mirror_check_strategy("http://default"),
        )

    async def test_run_apt_config_check_success(self):
        output = io.StringIO()
        self.app.dr_cfg.apt_mirror_check_default_strategy = "success"
        self.candidate.uri = "http://default"
        await self.configurer.run_apt_config_check(output)

    async def test_run_apt_config_check_failed(self):
        output = io.StringIO()
        self.app.dr_cfg.apt_mirror_check_default_strategy = "failure"
        self.candidate.uri = "http://default"
        with self.assertRaises(AptConfigCheckError):
            await self.configurer.run_apt_config_check(output)

    async def test_run_apt_config_check_random(self):
        output = io.StringIO()
        self.app.dr_cfg.apt_mirror_check_default_strategy = "random"
        self.candidate.uri = "http://default"
        with patch(
            "subiquity.server.apt.random.choice",
            return_value=self.configurer.apt_config_check_success,
        ):
            await self.configurer.run_apt_config_check(output)
        with patch(
            "subiquity.server.apt.random.choice",
            return_value=self.configurer.apt_config_check_failure,
        ):
            with self.assertRaises(AptConfigCheckError):
                await self.configurer.run_apt_config_check(output)
