# COPYRIGHT (C) 2020 Nicotine+ Team
# COPYRIGHT (C) 2016-2017 Michael Labouebe <gfarmerfr@free.fr>
# COPYRIGHT (C) 2016-2018 Mutnick <mutnick@techie.com>
# COPYRIGHT (C) 2008-2011 Quinox <quinox@users.sf.net>
# COPYRIGHT (C) 2006-2009 Daelstorm <daelstorm@gmail.com>
# COPYRIGHT (C) 2009 Hedonist <ak@sensi.org>
# COPYRIGHT (C) 2003-2004 Hyriand <hyriand@thegraveyard.org>
#
# GNU GENERAL PUBLIC LICENSE
#    Version 3, 29 June 2007
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os

from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import Pango

from pynicotine import slskmessages
from pynicotine.gtkgui.utils import initialise_columns
from pynicotine.gtkgui.utils import load_ui_elements
from pynicotine.gtkgui.utils import PopupMenu
from pynicotine.gtkgui.utils import set_treeview_selected_row
from pynicotine.gtkgui.utils import triggers_context_menu
from pynicotine.gtkgui.utils import update_widget_visuals


class RoomList:

    def __init__(self, frame, joined_rooms, private_rooms):

        # Build the window
        self.frame = frame
        self.joined_rooms = joined_rooms
        self.private_rooms = private_rooms

        load_ui_elements(self, os.path.join(self.frame.gui_dir, "ui", "dialogs", "roomlist.ui"))
        self.RoomListDialog.set_transient_for(frame.MainWindow)

        self.room_model = Gtk.ListStore(str, int, int)
        self.RoomsList.set_model(self.room_model)

        self.cols = initialise_columns(
            None,
            self.RoomsList,
            ["room", _("Room"), 180, "text", self.room_status, None],
            ["users", _("Users"), 0, "number", self.room_status, None]
        )
        self.cols["room"].set_sort_column_id(0)
        self.cols["users"].set_sort_column_id(1)

        self.room_model.set_sort_func(1, self.private_rooms_sort, 1)

        self.popup_room = None
        self.popup_menu = PopupMenu(self.frame)
        self.popup_menu.setup(
            ("#" + _("Join Room"), self.on_popup_join),
            ("#" + _("Leave Room"), self.on_popup_leave),
            ("", None),
            ("#" + _("Disown Private Room"), self.on_popup_private_room_disown),
            ("#" + _("Cancel Room Membership"), self.on_popup_private_room_dismember),
            ("", None),
            ("#" + _("Join Public Room"), self.on_join_public_room)
        )

        self.RoomsList.connect("button_press_event", self.on_list_clicked)
        self.RoomsList.connect("popup-menu", self.on_popup_menu)
        self.RoomsList.connect("touch_event", self.on_list_clicked)
        self.RoomsList.set_headers_clickable(True)

        self.search_iter = None
        self.query = ""

        self.AcceptPrivateRoom.set_active(self.frame.np.config.sections["server"]["private_chatrooms"])
        self.AcceptPrivateRoom.connect("toggled", self.on_toggle_accept_private_room)

        frame.RoomList.connect("clicked", self.show)

    def get_selected_room(self, treeview):

        model, iterator = treeview.get_selection().get_selected()

        if iterator is None:
            return None

        return model.get_value(iterator, 0)

    def is_private_room_owned(self, room):

        if room in self.private_rooms:
            if self.private_rooms[room]["owner"] == self.frame.np.config.sections["server"]["login"]:
                return True

        return False

    def is_private_room_member(self, room):

        if room in self.private_rooms:
            return True

        return False

    def is_private_room_operator(self, room):

        if room in self.private_rooms:
            if self.frame.np.config.sections["server"]["login"] in self.private_rooms[room]["operators"]:
                return True

        return False

    def private_rooms_sort(self, model, iter1, iter2, column):

        try:
            private1 = model.get_value(iter1, 2) * 10000
            private1 += model.get_value(iter1, 1)
        except Exception:
            private1 = 0

        try:
            private2 = model.get_value(iter2, 2) * 10000
            private2 += model.get_value(iter2, 1)
        except Exception:
            private2 = 0

        return (private1 > private2) - (private1 < private2)

    def room_status(self, column, cellrenderer, model, iterator, dummy='dummy'):

        if self.room_model.get_value(iterator, 2) >= 2:
            cellrenderer.set_property("underline", Pango.Underline.SINGLE)
            cellrenderer.set_property("weight", Pango.Weight.BOLD)

        elif self.room_model.get_value(iterator, 2) >= 1:
            cellrenderer.set_property("weight", Pango.Weight.BOLD)
            cellrenderer.set_property("underline", Pango.Underline.NONE)

        else:
            cellrenderer.set_property("weight", Pango.Weight.NORMAL)
            cellrenderer.set_property("underline", Pango.Underline.NONE)

    def set_room_list(self, rooms):

        self.room_model.clear()
        self.RoomsList.set_model(None)
        self.room_model.set_default_sort_func(lambda *args: -1)
        self.room_model.set_sort_func(1, lambda *args: -1)
        self.room_model.set_sort_column_id(-1, Gtk.SortType.ASCENDING)

        for room, users in rooms:
            self.room_model.append([room, users, 0])

        self.RoomsList.set_model(self.room_model)
        self.room_model.set_sort_func(1, self.private_rooms_sort, 1)
        self.room_model.set_sort_column_id(1, Gtk.SortType.DESCENDING)
        self.room_model.set_default_sort_func(self.private_rooms_sort)

    def update_private_rooms(self):

        iterator = self.room_model.get_iter_first()

        while iterator is not None:
            room = self.room_model.get_value(iterator, 0)
            lastiter = iterator
            iterator = self.room_model.iter_next(iterator)

            if self.is_private_room_owned(room) or self.is_private_room_member(room):
                self.room_model.remove(lastiter)

        for room in self.private_rooms:

            num = self.private_rooms[room]["joined"]

            if self.is_private_room_owned(room):
                self.room_model.prepend([room, num, 2])

            elif self.is_private_room_member(room):
                self.room_model.prepend([room, num, 1])

    def on_list_clicked(self, widget, event):

        set_treeview_selected_row(widget, event)

        if triggers_context_menu(event):
            return self.on_popup_menu(widget)

        if event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS:
            room = self.get_selected_room(widget)

            if room is not None and room not in self.joined_rooms:
                self.on_popup_join(widget)
                return True

            self.hide()

        return False

    def on_popup_menu(self, widget):

        if self.room_model is None:
            return False

        room = self.get_selected_room(widget)

        if room is not None:
            if room in self.joined_rooms:
                act = (False, True)
            else:
                act = (True, False)
        else:
            act = (False, False)

        self.popup_room = room
        prooms_enabled = True

        items = self.popup_menu.get_items()

        items[_("Join Room")].set_sensitive(act[0])
        items[_("Leave Room")].set_sensitive(act[1])

        items[_("Disown Private Room")].set_sensitive(self.is_private_room_owned(self.popup_room))
        items[_("Cancel Room Membership")].set_sensitive((prooms_enabled and self.is_private_room_member(self.popup_room)))

        self.popup_menu.popup()
        return True

    def on_popup_join(self, widget):
        self.frame.np.queue.put(slskmessages.JoinRoom(self.popup_room))

    def on_join_public_room(self, widget):
        self.frame.chatrooms.join_public_room()
        self.frame.np.queue.put(slskmessages.JoinPublicRoom())
        self.hide()

    def on_popup_private_room_disown(self, widget):

        if self.is_private_room_owned(self.popup_room):
            self.frame.np.queue.put(slskmessages.PrivateRoomDisown(self.popup_room))
            del self.private_rooms[self.popup_room]
            self.update_private_rooms()

    def on_popup_private_room_dismember(self, widget):

        if self.is_private_room_member(self.popup_room):
            self.frame.np.queue.put(slskmessages.PrivateRoomDismember(self.popup_room))
            del self.private_rooms[self.popup_room]
            self.update_private_rooms()

    def on_popup_leave(self, widget):
        self.frame.np.queue.put(slskmessages.LeaveRoom(self.popup_room))

    def on_search_room(self, widget):

        if self.room_model is not self.RoomsList.get_model():
            self.room_model = self.RoomsList.get_model()
            self.search_iter = self.room_model.get_iter_first()

        room = self.SearchRooms.get_text().lower()

        if not room:
            return

        if self.query == room:
            if self.search_iter is None:
                self.search_iter = self.room_model.get_iter_first()
            else:
                self.search_iter = self.room_model.iter_next(self.search_iter)
        else:
            self.search_iter = self.room_model.get_iter_first()
            self.query = room

        while self.search_iter:

            room_match, size = self.room_model.get(self.search_iter, 0, 1)
            if self.query in room_match.lower():
                path = self.room_model.get_path(self.search_iter)
                self.RoomsList.set_cursor(path)
                break

            self.search_iter = self.room_model.iter_next(self.search_iter)

    def on_toggle_accept_private_room(self, widget):

        value = self.AcceptPrivateRoom.get_active()
        self.frame.np.queue.put(slskmessages.PrivateRoomToggle(value))

    def update_visuals(self):

        for widget in self.__dict__.values():
            update_widget_visuals(widget)

    def hide(self, *args):
        self.SearchRooms.set_text("")
        self.RoomListDialog.hide()
        return True

    def show(self, *args):
        # Refresh list
        self.frame.np.queue.put(slskmessages.RoomList())

        self.RoomListDialog.show()
