### Copyright (C) 2007-2015 Peter Williams <pwil3058@gmail.com>
###
### This program is free software; you can redistribute it and/or modify
### it under the terms of the GNU General Public License as published by
### the Free Software Foundation; version 2 of the License only.
###
### This program is distributed in the hope that it will be useful,
### but WITHOUT ANY WARRANTY; without even the implied warranty of
### MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
### GNU General Public License for more details.
###
### You should have received a copy of the GNU General Public License
### along with this program; if not, write to the Free Software
### Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

"""
Provide generic enhancements to Textview widgets primarily to create
them from templates and allow easier access to named contents.
"""

import hashlib

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import Gdk

from ..bab import enotify

from . import gutils
from . import actions
from . import tlview
from . import dialogue
from . import auto_update

AC_MODIFIED, AC_NOT_MODIFIED, AC_MODIFIED_MASK = actions.ActionCondns.new_flags_and_mask(2)

class EditableEntriesView(tlview.ListView, actions.CBGUserMixin):
    __g_type_name__ = "EditableEntriesView"
    MODEL = tlview.ListView.MODEL
    def __init__(self, model=None, size_req=None):
        tlview.ListView.__init__(self, model)
        if size_req:
            self.set_size_request(*size_req)
        actions.CBGUserMixin.__init__(self, self.get_selection())
        self._set_modified(False)
        self.model.connect("row-inserted", self._row_inserted_cb)
        self.register_modification_callback(self._set_modified, True)
    @property
    def model(self):
        return self.get_model()
    @property
    def seln(self):
        return self.get_selection()
    def populate_button_groups(self):
        self.button_groups[actions.AC_DONT_CARE].add_buttons(
            [
                ("table_add_row", Gtk.Button.new_from_stock(Gtk.STOCK_ADD),
                 _("Add a new entry to the table"),
                 [("clicked", self._add_row_acb)]
                ),
            ])
        self.button_groups[AC_MODIFIED].add_buttons(
            [
                ("table_undo_changes", Gtk.Button.new_from_stock(Gtk.STOCK_UNDO),
                 _("Undo unapplied changes"),
                 [("clicked", self._undo_changes_acb)]
                ),
                ("table_apply_changes", Gtk.Button.new_from_stock(Gtk.STOCK_APPLY),
                 _("Apply outstanding changes"),
                 [("clicked", self._apply_changes_acb)]
                ),
            ])
        self.button_groups[actions.AC_SELN_MADE].add_buttons(
            [
                ("table_delete_selection", Gtk.Button.new_from_stock(Gtk.STOCK_DELETE),
                 _("Delete selected row(s)"),
                 [("clicked", self._delete_selection_acb)]
                ),
                ("table_insert_row", Gtk.Button.new_with_label(_("Insert")),
                 _("Insert a new entry before the selected row(s)"),
                 [("clicked", self._insert_row_acb)]
                ),
            ])
    def _set_modified(self, val):
        self._modified = val
        if val:
            self.button_groups.update_condns(actions.MaskedCondns(AC_MODIFIED, AC_MODIFIED_MASK))
        else:
            self.button_groups.update_condns(actions.MaskedCondns(AC_NOT_MODIFIED, AC_MODIFIED_MASK))
    def _fetch_contents(self):
        assert False, _("Must be defined in child")
    def set_contents(self):
        self.model.set_contents(self._fetch_contents())
        self._set_modified(False)
    def get_contents(self):
        return [row for row in self.model.named()]
    def apply_changes(self):
        assert False, _("Must be defined in child")
    def _row_inserted_cb(self, model, path, model_iter):
        self._set_modified(True)
    def _undo_changes_acb(self, _action=None):
        self.set_contents()
    def _apply_changes_acb(self, _action=None):
        self.apply_changes()
    def append_row(self, row, select=False):
        model_iter = self.model.append(row)
        if select:
            self.seln.select_iter(model_iter)
    def _add_row_acb(self, _action=None):
        self.append_row(None, True)
    def _delete_selection_acb(self, _action=None):
        model, paths = self.seln.get_selected_rows()
        iters = []
        for path in paths:
            iters.append(model.get_iter(path))
        for model_iter in iters:
            model.remove(model_iter)
    def insert_row(self, row, select=False):
        model, paths = self.seln.get_selected_rows()
        if not paths:
            return
        model_iter = self.model.insert_before(model.get_iter(paths[0]), row)
        if select:
            self.seln.select_iter(model_iter)
    def _insert_row_acb(self, _action=None):
        self.insert_row(None, True)
    def get_selected_data(self, columns=None):
        store, selected_rows = self.seln.get_selected_rows()
        if not columns:
            columns = list(range(store.get_n_columns()))
        result = []
        for row in selected_rows:
            model_iter = store.get_iter(row)
            assert model_iter is not None
            result.append(store.get(model_iter, *columns))
        return result
    def get_selected_data_by_label(self, labels):
        columns = self.model.col_indices(labels)
        return self.get_selected_data(columns)
    def create_button_box(self, button_name_list):
        return self.button_groups.create_button_box(button_name_list)

class EditedEntriesTable(Gtk.VBox):
    __g_type_name__ = "EditedEntriesTable"
    VIEW = EditableEntriesView
    BUTTONS = ["table_add_row", "table_insert_row", "table_delete_selection", "table_undo_changes", "table_apply_changes"]
    def __init__(self, size_req=None, **kwargs):
        Gtk.VBox.__init__(self)
        self.view = self.VIEW(**kwargs)
        self.pack_start(gutils.wrap_in_scrolled_window(self.view), expand=True, fill=True, padding=0)
        self.pack_start(self.view.create_button_box(self.BUTTONS), expand=False, fill=True, padding=0)
        self.show_all()
    @property
    def seln(self):
        return self.view.get_selection()

def simple_text_specification(model, *hdrs_flds_xalign, selection_mode=Gtk.SelectionMode.MULTIPLE):
    specification = tlview.ViewSpec(
        properties={
            "enable-grid-lines" : False,
            "reorderable" : False,
            "rules_hint" : False,
            "headers-visible" : True,
        },
        selection_mode=selection_mode,
        columns=[tlview.simple_column(hdr, tlview.fixed_text_cell(model, fld, xalign)) for hdr, fld, xalign in hdrs_flds_xalign]
    )
    return specification

class TableView(tlview.ListView, actions.CAGandUIManager, dialogue.BusyIndicatorUser, auto_update.AutoUpdater, enotify.Listener):
    __g_type_name__ = "TableView"
    PopUp = None
    SET_EVENTS = enotify.E_CHANGE_WD
    REFRESH_EVENTS = 0
    AU_REQ_EVENTS = 0
    def __init__(self, size_req=None):
        tlview.ListView.__init__(self)
        actions.CAGandUIManager.__init__(self, selection=self.get_selection(), popup=self.PopUp)
        auto_update.AutoUpdater.__init__(self)
        enotify.Listener.__init__(self)
        self._table_db = self._get_table_db()
        if self.SET_EVENTS:
            self.add_notification_cb(self.SET_EVENTS, self.set_contents)
        if self.REFRESH_EVENTS:
            self.add_notification_cb(self.REFRESH_EVENTS, self.refresh_contents)
        if self.AU_REQ_EVENTS:
            self.register_auto_update_cb(self.auto_update_cb)
        if size_req:
            self.set_size_request(size_req[0], size_req[1])
    def populate_action_groups(self):
        self.action_groups[actions.AC_DONT_CARE].add_actions(
            [
                ("table_refresh_contents", Gtk.STOCK_REFRESH, _("Refresh"), None,
                 _("Refresh the table's contents"),
                 lambda _action=None: self.refresh_contents()
                ),
            ])
    @property
    def model(self):
        return self.get_model()
    @property
    def seln(self):
        return self.get_selection()
    def auto_update_cb(self, events_so_far, args):
        if (events_so_far & (self.SET_EVENTS|self.REFRESH_EVENTS)) or  self._table_db.is_current:
            return 0
        try:
            args["tbd_reset_only"].append(self)
        except KeyError:
            args["tbd_reset_only"] = [self]
        return self.AU_REQ_EVENTS
    def _get_table_db(self):
        # this method's purpose is to fetch a TableData instance
        NotImplemented
    def _fetch_contents(self, tbd_reset_only=False, **kwargs):
        self._table_db = self._table_db.reset() if (tbd_reset_only and self in tbd_reset_only) else self._get_table_db()
        return iter(self._table_db)
    def _set_contents(self, **kwargs):
        model = self.MODEL()
        model.set_contents(self._fetch_contents(**kwargs))
        self.set_model(model)
        self.columns_autosize()
        self.seln.unselect_all()
    def set_contents(self, **kwargs):
        with self.showing_busy():
            self._set_contents(**kwargs)
    def refresh_contents(self, **kwargs):
        with self.showing_busy():
            selected_keys = self.get_selected_keys()
            visible_range = self.get_visible_range()
            if visible_range is not None:
                start = visible_range[0][0]
                end = visible_range[1][0]
                length = end - start + 1
                middle_offset = length // 2
                align = float(middle_offset) / float(length)
                middle = start + middle_offset
                middle_key = self.model.get_value(self.model.get_iter(middle), 0)
            self._set_contents(**kwargs)
            for key in selected_keys:
                model_iter = self.model.find_named(lambda x: x[0] == key)
                if model_iter is not None:
                    self.seln.select_iter(model_iter)
            if visible_range is not None:
                middle_iter = self.model.find_named(lambda x: x[0] == middle_key)
                if middle_iter is not None:
                    middle = self.model.get_path(middle_iter)
                    self.scroll_to_cell(middle, use_align=True, row_align=align)
    def get_contents(self):
        return [row for row in self.model.named()]
    def get_selected_data(self, columns=None):
        store, selected_rows = self.seln.get_selected_rows()
        if not columns:
            columns = list(range(store.get_n_columns()))
        result = []
        for row in selected_rows:
            model_iter = store.get_iter(row)
            assert model_iter is not None
            result.append(store.get(model_iter, *columns))
        return result
    def get_selected_keys(self, keycol=0):
        store, selected_rows = self.seln.get_selected_rows()
        keys = []
        for row in selected_rows:
            model_iter = store.get_iter(row)
            assert model_iter is not None
            keys.append(store.get_value(model_iter, keycol))
        return keys
    def get_selected_data_by_label(self, labels):
        return self.get_selected_data(self.model.col_indices(labels))
    def get_selected_keys_by_label(self, label):
        return self.get_selected_keys(self.model.col_index(label))
    def get_selected_key(self, keycol=0):
        keys = self.get_selected_keys(keycol)
        assert len(keys) <= 1
        if keys:
            return keys[0]
        else:
            return None
    def get_selected_key_by_label(self, label):
        return self.get_selected_key(self.model.col_index(label))
    def select_and_scroll_to_row_with_key_value(self, key_value, key=None):
        index = 0 if key is None else (key if isinstance(key, int) else self.model.col_index(key))
        model_iter = self.model.find_named(lambda x: x[index] == key_value)
        if not model_iter:
            return False
        self.seln.select_iter(model_iter)
        path = self.model.get_path(model_iter)
        self.scroll_to_cell(path, use_align=True, row_align=0.5)
        return True

class MapManagedTableView(TableView, gutils.MappedManager):
    __g_type_name__ = "MapManagedTableView"
    _NEEDS_RESET = 123
    def __init__(self, size_req=None):
        TableView.__init__(self, size_req=size_req)
        gutils.MappedManager.__init__(self)
        self._needs_refresh = True
    def auto_update_cb(self, events_so_far, args):
        if self._needs_refresh:
            # This implies (both) that we're not mapped AND that we're
            # already scheduled for update when we become mapped so
            # there's no point in wasting effort making any checks
            return 0
        return TableView.auto_update_cb(self, events_so_far, args)
    def map_action(self):
        if self._needs_refresh == self._NEEDS_RESET:
            TableView.set_contents(self)
            self._needs_refresh = False
        elif self._needs_refresh:
            TableView.refresh_contents(self)
            self._needs_refresh = False
    def unmap_action(self):
        pass
    def set_contents(self, **kwargs):
        if self.is_mapped:
            TableView.set_contents(self, **kwargs)
            self._needs_refresh = False
        else:
            self._needs_refresh = self._NEEDS_RESET
    def refresh_contents(self, **kwargs):
        if self.is_mapped:
            TableView.refresh_contents(self, **kwargs)
            self._needs_refresh = False
        else:
            self._needs_refresh = True

class TableWidget(Gtk.VBox):
    __g_type_name__ = "TableWidget"
    VIEW = TableView
    def __init__(self, scroll_bar=True, size_req=None, **kwargs):
        Gtk.VBox.__init__(self)
        self.header = gutils.SplitBar()
        self.pack_start(self.header, expand=False, fill=True, padding=0)
        self.view = self.VIEW(size_req=size_req, **kwargs)
        if scroll_bar:
            self.pack_start(gutils.wrap_in_scrolled_window(self.view), expand=True, fill=True, padding=0)
        else:
            self.pack_start(self.view, expand=True, fill=True, padding=0)
        self.show_all()
    @property
    def ui_manager(self):
        return self.view.ui_manager
    @property
    def action_groups(self):
        return self.view.action_groups
    @property
    def seln(self):
        return self.view.get_selection()
    def unselect_all(self):
        self.seln.unselect_all()

class TableData:
    def __init__(self, **kwargs):
        self._kwargs = kwargs
        h = hashlib.sha1()
        pdt = self._get_data_text(h)
        self._db_hash_digest = h.digest()
        self._current_text_digest = None
        self._finalize(pdt)
    @property
    def is_current(self):
        return self._is_current()
    def __iter__(self):
        return (row for row in self._rows)
    def _finalize(self, pdt):
        # this method's role is to create the iterable self._rows
        NotImplemented
    def _is_current(self):
        h = hashlib.sha1()
        self._current_text = self._get_data_text(h)
        self._current_text_digest = h.digest()
        return self._current_text_digest == self._db_hash_digest
    def reset(self):
        if self._current_text_digest is None:
            return self.__class__(**self._kwargs)
        if self._current_text_digest != self._db_hash_digest:
            self._db_hash_digest = self._current_text_digest
            self._finalize(self._current_text)
        return self
    def _get_data_text(self, h):
        # this method's role is to get the RAW text for _finalize() to turn into rows if needed
        NotImplemented
    def iter_rows(self):
        # DEPRECATED: use __iter__ instead
        return iter(self)

class NullTableData(TableData):
    def _finalize(self, pdt):
        self._rows = []
    def _get_data_text(self, h):
        return ""
