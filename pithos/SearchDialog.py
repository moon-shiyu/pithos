# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
# Copyright (C) 2010-2012 Kevin Mehall <km@kevinmehall.net>
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranties of
# MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

import html
from gi.repository import GObject, Gtk

# Row type constants for the TreeStore
_ROW_TYPE_HEADER = 0
_ROW_TYPE_RESULT = 1


@Gtk.Template(resource_path='/io/github/Pithos/ui/SearchDialog.ui')
class SearchDialog(Gtk.Dialog):
    __gtype_name__ = "SearchDialog"

    entry = Gtk.Template.Child()
    treeview = Gtk.Template.Child()

    def __init__(self, *args, **kwargs):
        self.worker_run = kwargs["worker"]
        del kwargs["worker"]

        super().__init__(*args, use_header_bar=1, **kwargs)
        self.init_template()

        # TreeStore columns: (row_type: int, result: PyObject, markup: str)
        self.model = Gtk.TreeStore(int, GObject.TYPE_PYOBJECT, str)
        self.treeview.set_model(self.model)

        # Replace the UI-defined column with one that uses a cell_data_func
        # so we can style header rows differently from result rows.
        for col in self.treeview.get_columns():
            self.treeview.remove_column(col)

        column = Gtk.TreeViewColumn()
        renderer = Gtk.CellRendererText()
        column.pack_start(renderer, True)
        column.set_cell_data_func(renderer, self._cell_data_func)
        self.treeview.append_column(column)

        # Prevent header rows from being selected
        selection = self.treeview.get_selection()
        selection.set_select_function(self._select_func)

        self.query = ''
        self.result = None

    @staticmethod
    def _cell_data_func(column, cell, model, iter_, data=None):
        """Style header rows bold; result rows normal."""
        row_type = model.get_value(iter_, 0)
        markup = model.get_value(iter_, 2)
        if row_type == _ROW_TYPE_HEADER:
            cell.set_property('markup', '<span size="larger">{}</span>'.format(markup))
            cell.set_property('sensitive', False)
        else:
            cell.set_property('markup', markup)
            cell.set_property('sensitive', True)

    @staticmethod
    def _select_func(selection, model, path, path_currently_selected):
        """Only allow selecting result rows, not group headers."""
        iter_ = model.get_iter(path)
        return model.get_value(iter_, 0) == _ROW_TYPE_RESULT

    @Gtk.Template.Callback()
    def search_clicked(self, widget):
        self.search(self.entry.get_text())

    def get_selected(self):
        sel = self.treeview.get_selection().get_selected()
        if sel[1]:
            model = sel[0]
            iter_ = sel[1]
            if model.get_value(iter_, 0) == _ROW_TYPE_RESULT:
                return model.get_value(iter_, 1)
        return None

    def search(self, query):
        self.query = query
        self.model.clear()

        if not self.query:
            return

        def callback(grouped_results):
            self.model.clear()

            if not self.query:
                return

            _GROUPS = [
                ('Artists', 'artists'),
                ('Songs', 'songs'),
                ('Genres', 'genres'),
            ]

            for group_label, key in _GROUPS:
                items = grouped_results.get(key, [])
                if not items:
                    continue
                # Group header row
                header_text = '{} ({})'.format(html.escape(group_label), len(items))
                header_iter = self.model.append(None, (_ROW_TYPE_HEADER, None, header_text))
                # Child result rows
                for i in items:
                    if i.resultType == 'song':
                        mk = '<b>{}</b> by {}'.format(html.escape(i.title), html.escape(i.artist))
                    elif i.resultType == 'artist':
                        mk = '<b>{}</b>'.format(html.escape(i.name))
                    elif i.resultType == 'genre':
                        mk = '<b>{}</b>'.format(html.escape(i.stationName))
                    else:
                        mk = html.escape(str(i))
                    self.model.append(header_iter, (_ROW_TYPE_RESULT, i, mk))

            self.treeview.expand_all()
            self.treeview.show()

        self.worker_run('search_grouped', (self.query,), callback, "Searching...")

    def cursor_changed(self, *ignore):
        self.result = self.get_selected()
        self.set_response_sensitive(Gtk.ResponseType.OK, not not self.result)
