### Copyright (C) 2005-2015 Peter Williams <pwil3058@gmail.com>

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


import os
from shutil import which

try:
    import gi
    gi.require_version("Vte", "2.91")
    from gi.repository import Vte
    AVAILABLE = True
except (ValueError, ImportError):
    AVAILABLE = False
    GITSOME_AVAILABLE = False

if AVAILABLE:
    from gi.repository import Gtk
    from gi.repository import GLib
    from gi.repository import Gdk

    from ..bab import enotify
    from ..bab import utils

    class Terminal(Gtk.ScrolledWindow, enotify.Listener):
        ARGV = [os.getenv("SHELL", "/bin/bash")]
        def __init__(self, follow_chdir=True):
            Gtk.ScrolledWindow.__init__(self, None, None)
            enotify.Listener.__init__(self)
            self._vte = Vte.Terminal()
            self._vte.set_size(self._vte.get_column_count(), 10)
            self._vte.set_size_request(200, 50)
            self._vte.set_scrollback_lines(-1)
            self._vte.show()
            self._vte.connect("button_press_event", self._button_press_cb)
            self.add(self._vte)
            self.show_all()
            self._pid = self._vte.spawn_sync(Vte.PtyFlags.DEFAULT, os.getcwd(), self.ARGV, [], GLib.SpawnFlags.DO_NOT_REAP_CHILD, None, None,)
            if follow_chdir:
                self.add_notification_cb(enotify.E_CHANGE_WD, self._cwd_cb)
        def _cwd_cb(self, **kwargs):
            self.set_cwd(os.getcwd())
        def set_cwd(self, path):
            command = "cd {}\n".format(utils.quote_if_needed(os.path.abspath(os.path.expanduser(path))))
            try:
                self._vte.feed_child(command, len(command))
            except TypeError:
                self._vte.feed_child([ord(c) for c in command])
        def _button_press_cb(self, widget, event):
            if event.type == Gdk.EventType.BUTTON_PRESS:
                if event.button == 3:
                    menu = Gtk.Menu()
                    copy_item = Gtk.MenuItem(label=_("Copy"))
                    copy_item.connect("activate", lambda _item: widget.copy_clipboard())
                    copy_item.set_sensitive(widget.get_has_selection())
                    clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
                    paste_item = Gtk.MenuItem(label=_("Paste"))
                    paste_item.set_sensitive(clipboard.wait_is_text_available())
                    paste_item.connect("activate", lambda _item: widget.paste_clipboard())
                    menu.append(copy_item)
                    menu.append(paste_item)
                    menu.show_all()
                    menu.popup(None, None, None, None, event.button, event.time)
                    return True
            return False
    GITSOME = which("gitsome")
    if GITSOME:
        GITSOME_AVAILABLE = True
        class GitsomeTerminal(Terminal):
            ARGV = [GITSOME]
    else:
        GITSOME_AVAILABLE = False
