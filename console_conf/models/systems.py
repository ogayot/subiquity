#!/usr/bin/env python3
# Copyright 2020 Canonical, Ltd.
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
import json
import logging

import attrs
import jsonschema

log = logging.getLogger("console_conf.models.systems")

# This json schema describes the recovery systems data. Allow additional
# properties at each level so that console-conf does not have to be exactly in
# sync with snapd.
_RECOVERY_SYSTEMS_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "title": "systems",
    "type": "object",
    "additionalProperties": True,
    "required": ["systems"],
    "properties": {
        "systems": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["label", "brand", "model"],
                "properties": {
                    "label": {"type": "string"},
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": True,
                            "required": ["title", "mode"],
                            "properties": {
                                "title": {"type": "string"},
                                "mode": {"type": "string"},
                            },
                        },
                    },
                    "brand": {
                        "type": "object",
                        "additionalProperties": True,
                        "required": ["id", "username", "display-name"],
                        "properties": {
                            "id": {"type": "string"},
                            "username": {"type": "string"},
                            "display-name": {"type": "string"},
                            "validation": {"type": "string"},
                        },
                    },
                    "model": {
                        "type": "object",
                        "additionalProperties": True,
                        "required": ["model", "brand-id", "display-name"],
                        "properties": {
                            "model": {"type": "string"},
                            "brand-id": {"type": "string"},
                            "display-name": {"type": "string"},
                        },
                    },
                },
            },
        },
    },
}


class RecoverySystemsModel:
    """Recovery chooser data"""

    def __init__(self, systems_data):
        self.systems = systems_data
        # current selection
        self._selection = None
        self._current = None
        # find which system is current one, but be robust if none is marked as
        # such
        cs = [s for s in systems_data if s.current]
        if cs:
            self._current = cs[0]

    def select(self, system, action):
        self._selection = SelectedSystemAction(system=system, action=action)

    def unselect(self):
        self._selection = None

    @property
    def selection(self):
        return self._selection

    @property
    def current(self):
        return self._current

    @staticmethod
    def from_systems(recovery_systems):
        systems = []
        for syst in recovery_systems:
            m = syst["model"]
            b = syst["brand"]
            model = SystemModel(
                model=m["model"], brand_id=m["brand-id"], display_name=m["display-name"]
            )
            brand = Brand(
                ID=b["id"],
                username=b["username"],
                display_name=b["display-name"],
                validation=b.get("validation", "unproven"),
            )
            actions = []
            for a in syst.get("actions", []):
                actions.append(SystemAction(title=a["title"], mode=a["mode"]))
            s = RecoverySystem(
                current=syst.get("current", False),
                label=syst["label"],
                model=model,
                brand=brand,
                actions=actions,
            )
            systems.append(s)

        return RecoverySystemsModel(systems)

    @staticmethod
    def from_systems_stream(chooser_input):
        """Deserialize recovery systems from input JSON stream."""
        try:
            dec = json.load(chooser_input)
            jsonschema.validate(dec, _RECOVERY_SYSTEMS_SCHEMA)
            systems = dec.get("systems", [])
        except json.JSONDecodeError:
            log.exception("cannot decode recovery systems info")
            raise
        except jsonschema.ValidationError:
            log.exception("cannot validate recovery systems data")
            raise

        return RecoverySystemsModel.from_systems(systems)

    @staticmethod
    def to_response_stream(obj, chooser_output):
        """Serialize an object with selected action as JSON to the given output
        stream.
        """
        if not isinstance(obj, SelectedSystemAction):
            raise TypeError("unexpected type: {}".format(type(obj)))

        choice = {
            "label": obj.system.label,
            "action": {
                "mode": obj.action.mode,
                "title": obj.action.title,
            },
        }
        return json.dump(choice, fp=chooser_output)


@attrs.define
class RecoverySystem:
    current = attrs.field()
    label = attrs.field()
    model = attrs.field()
    brand = attrs.field()
    actions = attrs.field()

    def __eq__(self, other):
        return (
            self.current == other.current
            and self.label == other.label
            and self.model == other.model
            and self.brand == other.brand
            and self.actions == other.actions
        )


@attrs.define
class Brand:
    ID = attrs.field()
    username = attrs.field()
    display_name = attrs.field()
    validation = attrs.field()

    def __eq__(self, other):
        return (
            self.ID == other.ID
            and self.username == other.username
            and self.display_name == other.display_name
            and self.validation == other.validation
        )


@attrs.define
class SystemModel:
    model = attrs.field()
    brand_id = attrs.field()
    display_name = attrs.field()

    def __eq__(self, other):
        return (
            self.model == other.model
            and self.brand_id == other.brand_id
            and self.display_name == other.display_name
        )


@attrs.define
class SystemAction:
    title = attrs.field()
    mode = attrs.field()

    def __eq__(self, other):
        return self.title == other.title and self.mode == other.mode


@attrs.define
class SelectedSystemAction:
    system = attrs.field()
    action = attrs.field()

    def __eq__(self, other):
        return self.system == other.system and self.action == other.action
