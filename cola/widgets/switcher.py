"""Provides quick switcher"""
from __future__ import absolute_import, division, print_function, unicode_literals

import re

from qtpy import QtCore
from qtpy import QtGui
from qtpy.QtCore import Qt
from qtpy.QtCore import Signal

from .. import qtutils
from ..widgets import defs
from ..widgets import standard
from ..widgets import text


def switcher_inner_view(
    context, entries, title=None, place_holder=None, enter_action=None, parent=None
):
    dialog = SwitcherInnerView(
        context, entries, title, place_holder, enter_action, parent
    )
    dialog.show()
    return dialog


def switcher_outer_view(context, entries, place_holder=None, parent=None):
    dialog = SwitcherOuterView(context, entries, place_holder, parent)
    dialog.show()
    return dialog


def switcher_item(key, icon=None, name=None):
    return SwitcherListItem(key, icon, name)


def moving_keys():
    selection_move_keys = [
        Qt.Key_Enter,
        Qt.Key_Return,
        Qt.Key_Up,
        Qt.Key_Down,
        Qt.Key_Home,
        Qt.Key_End,
        Qt.Key_PageUp,
        Qt.Key_PageDown,
    ]
    return selection_move_keys


class Switcher(standard.Dialog):
    """
    Quick switcher base class. This contains input field, filter proxy model.
    This will be inherited by outer-view class(SwitcherOuterView) or inner-view class
    (SwitcherInnerView).

    inner-view class is a quick-switcher widget including view. In this case, this
    switcher will have switcher_list field, and show the items list in itself.
    outer-view class is a quick-switcher widget without view(only input field), which
    means sharing model with other view class.

    switcher_selection_move signal is for the event that selection move key like UP,
    DOWN has pressed while focusing on input field.
    """

    def __init__(
        self,
        context,
        entries_model,
        place_holder=None,
        parent=None,
    ):
        standard.Dialog.__init__(self, parent=parent)

        self.context = context
        self.entries_model = entries_model

        self.filter_input = SwitcherLineEdit(place_holder=place_holder, parent=self)

        self.proxy_model = SwitcherSortFilterProxyModel(entries_model, parent=self)
        self.switcher_list = None

        self.filter_input.textChanged.connect(self.filter_input_changed)

    def filter_input_changed(self):
        input_text = self.filter_input.text()
        pattern = '.*'.join(re.escape(c) for c in input_text)
        self.proxy_model.setFilterRegExp(pattern)


class SwitcherInnerView(Switcher):
    def __init__(
        self,
        context,
        entries_model,
        title,
        place_holder=None,
        enter_action=None,
        parent=None,
    ):
        Switcher.__init__(
            self,
            context,
            entries_model,
            place_holder=place_holder,
            parent=parent,
        )
        self.setModal(False)
        self.setWindowTitle(title)

        self.enter_action = enter_action
        self.switcher_list = SwitcherTreeView(
            self.proxy_model, self.enter_selected_item, parent=self
        )

        self.main_layout = qtutils.vbox(
            defs.no_margin, defs.spacing, self.filter_input, self.switcher_list
        )
        self.setLayout(self.main_layout)

        # moving key has pressed while focusing on input field
        self.filter_input.switcher_selection_move.connect(
            self.switcher_list.keyPressEvent
        )
        # some key except moving key has pressed while focusing on list view
        self.switcher_list.switcher_inner_text.connect(self.filter_input.keyPressEvent)

    def resizeEvent(self, _event):
        parent = self.parent()
        if parent is None:
            return
        left = parent.x()
        width = parent.width()
        center_x = left + width // 2
        x = center_x - self.width() // 2
        y = parent.y()

        self.move(x, y)

    def enter_selected_item(self, index):
        item = self.switcher_list.model().itemFromIndex(index)
        if item:
            self.enter_action(item)
        self.close()


class SwitcherOuterView(Switcher):
    def __init__(self, context, entries_model, place_holder=None, parent=None):
        Switcher.__init__(
            self,
            context,
            entries_model,
            place_holder=place_holder,
            parent=parent,
        )
        self.filter_input.setVisible(False)

        self.main_layout = qtutils.vbox(defs.no_margin, defs.spacing, self.filter_input)
        self.setLayout(self.main_layout)

    def filter_input_changed(self):
        input_text = self.filter_input.text()
        pattern = '.*'.join(re.escape(c) for c in input_text)
        self.proxy_model.setFilterRegExp(pattern)

        # set invisible when input field get empty
        if input_text == '':
            self.filter_input.setVisible(False)


class SwitcherLineEdit(text.LineEdit):
    """Quick switcher input line class"""

    # signal is for the event that selection move key like UP, DOWN has pressed
    # while focusing on this line edit widget
    switcher_selection_move = Signal(QtGui.QKeyEvent)
    switcher_visible = Signal(bool)

    def __init__(self, place_holder=None, parent=None):
        text.LineEdit.__init__(self, parent=parent)
        if place_holder:
            self.setPlaceholderText(place_holder)

    def keyPressEvent(self, event):
        """
        To be able to move the selection while focus on the input field, input text
        field should be able to filter pressed key.
        If pressed key is moving selection key like UP or DOWN, the
        switcher_selection_move signal will be emitted and the view selection
        will be moved regardless whether Switcher is inner-view or outer-view.
        Or else, simply act like text input to the field.
        """
        selection_moving_keys = moving_keys()
        pressed_key = event.key()

        if pressed_key in selection_moving_keys:
            self.switcher_selection_move.emit(event)
        else:
            super().keyPressEvent(event)


class SwitcherSortFilterProxyModel(QtCore.QSortFilterProxyModel):
    """Filtering class for candidate items."""

    def __init__(self, entries, parent=None):
        QtCore.QSortFilterProxyModel.__init__(self, parent)

        self.entries = entries

        self.setDynamicSortFilter(True)
        self.setSourceModel(entries)
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)

    def itemFromIndex(self, index):
        return self.entries.itemFromIndex(self.mapToSource(index))


class SwitcherTreeView(standard.TreeView):
    """Tree view class for showing proxy items in SwitcherSortFilterProxyModel"""

    # signal is for the event that some key except moving key has pressed
    # while focusing this view
    switcher_inner_text = Signal(QtGui.QKeyEvent)

    def __init__(self, entries_proxy_model, enter_action, parent=None):
        standard.TreeView.__init__(self, parent)

        self.setHeaderHidden(True)
        self.setModel(entries_proxy_model)

        self.activated.connect(enter_action)
        self.doubleClicked.connect(enter_action)
        self.entered.connect(enter_action)

    def keyPressEvent(self, event):
        """hooks when a key has pressed while focusing on list view"""
        selection_moving_keys = moving_keys()
        pressed_key = event.key()

        if pressed_key in selection_moving_keys or pressed_key == Qt.Key_Escape:
            super().keyPressEvent(event)
        else:
            self.switcher_inner_text.emit(event)


class SwitcherListItem(QtGui.QStandardItem):
    """Item class for SwitcherTreeView and SwitcherSortFilterProxyModel"""

    def __init__(self, key, icon=None, name=None):
        QtGui.QStandardItem.__init__(self)

        self.key = key
        if not name:
            name = key

        self.setText(name)
        if icon:
            self.setIcon(icon)
