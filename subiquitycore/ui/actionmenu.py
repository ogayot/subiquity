# Copyright 2018 Canonical, Ltd.
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

import attrs
from urwid import (
    ACTIVATE,
    AttrMap,
    Button,
    LineBox,
    PopUpLauncher,
    SelectableIcon,
    Text,
    Widget,
    connect_signal,
)

from subiquitycore.ui.container import Columns, ListBox, WidgetWrap
from subiquitycore.ui.utils import Color


class ActionBackButton(Button):
    button_left = Text("\N{BLACK LEFT-POINTING SMALL TRIANGLE}")
    button_right = Text("")


class ActionMenuOpenButton(Button):
    button_left = Text("")
    button_right = Text("\N{BLACK RIGHT-POINTING SMALL TRIANGLE}")


class ActionMenuButton(Button):
    button_left = Text("")
    button_right = Text("")


class _ActionMenuDialog(WidgetWrap):
    """A list of action buttons with a box around them."""

    def __init__(self, parent):
        self.parent = parent
        close_text = "(close)"
        close = ActionBackButton(close_text)
        connect_signal(close, "click", self.close)
        group = [Color.menu_button(close)]
        width = len(close_text)
        for i, action in enumerate(self.parent._actions):
            if action.enabled:
                if isinstance(action.label, Widget):
                    btn = action.label
                elif action.opens_dialog:
                    btn = Color.menu_button(ActionMenuOpenButton(action.label))
                else:
                    btn = Color.menu_button(ActionMenuButton(action.label))
                width = max(width, len(btn.base_widget.label))
                connect_signal(
                    btn.base_widget, "click", self.click, user_args=[action.value]
                )
            else:
                label = action.label
                if isinstance(label, Widget):
                    label = label.base_widget.label
                width = max(width, len(label))
                if action.opens_dialog:
                    rhs = "\N{BLACK RIGHT-POINTING SMALL TRIANGLE}"
                else:
                    rhs = ""
                btn = Columns(
                    [
                        ("fixed", 1, Text("")),
                        Text(label),
                        ("fixed", 1, Text(rhs)),
                    ],
                    dividechars=1,
                )
                btn = AttrMap(btn, "info_minor")
            group.append(btn)
        self.width = width
        super().__init__(Color.body(LineBox(ListBox(group))))

    def close(self, sender):
        self.parent.close_pop_up()

    def click(self, value, btn):
        self.parent._action(value)
        self.parent.close_pop_up()

    def keypress(self, size, key):
        if key == "esc":
            self.parent.close_pop_up()
        else:
            return super().keypress(size, key)


@attrs.define
class Action:
    # The label that is shown in the menu
    label = attrs.field()
    enabled = attrs.field()
    # The value passed along with the 'action' signal
    value = attrs.field()
    # Actions that open a dialog get a > at the end.
    opens_dialog = attrs.field(default=False)


class ActionMenu(PopUpLauncher):
    signals = ["action", "open", "close"]

    def __init__(self, opts, icon="\N{BLACK RIGHT-POINTING SMALL TRIANGLE}"):
        self._actions = []
        for opt in opts:
            if not isinstance(opt, Action):
                opt = Action(*opt)
            self._actions.append(opt)
        self.icon = icon
        self._button = SelectableIcon(self.icon, 0)
        super().__init__(self._button)
        self._dialog = _ActionMenuDialog(self)

    def get_natural_width(self):
        return len(self.icon)

    def keypress(self, size, key):
        if self._command_map[key] != ACTIVATE:
            return key
        self.open_pop_up()

    def _action(self, action):
        self._emit("action", action)

    def open_pop_up(self):
        self._dialog._w.base_widget.focus_position = 0
        self._emit("open")
        super().open_pop_up()

    def close_pop_up(self):
        self._emit("close")
        super().close_pop_up()

    def create_pop_up(self):
        return self._dialog

    def get_pop_up_parameters(self):
        width = self._dialog.width + 7
        return {
            "left": 1,
            "top": -1,
            "overlay_width": width,
            "overlay_height": len(self._actions) + 3,
        }
