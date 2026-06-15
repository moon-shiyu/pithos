# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
"""
tests/_gi_mock.py - Mock gi.repository for headless testing.

Provides a minimal but functional GObject.Object base class with
property descriptors and signal support, so that pithos.plugin can
be imported and tested without a real GTK/DBus environment.

Import this module BEFORE importing anything from pithos.
"""

import sys
import types
from unittest.mock import MagicMock

# Check if real gi is available
_gi_available = False
try:
    import gi
    gi.require_version('GObject', '2.0')
    from gi.repository import GObject  # noqa: F401
    _gi_available = True
except (ImportError, ValueError):
    pass

if not _gi_available:

    class _FakeGObjectMeta(type):
        """Metaclass that silently handles __gtype_name__ and __gsignals__."""
        def __new__(mcs, name, bases, namespace):
            namespace.pop('__gtype_name__', None)
            namespace.pop('__gsignals__', None)
            return super().__new__(mcs, name, bases, namespace)

    class _GObjectBase(metaclass=_FakeGObjectMeta):
        """Minimal GObject.Object substitute for testing."""

        def __init__(self, **kwargs):
            self._signal_handlers = {}
            self._next_handler_id = 1

        def connect(self, signal_name, callback, *args):
            handler_id = self._next_handler_id
            self._next_handler_id += 1
            self._signal_handlers.setdefault(signal_name, []).append(
                (handler_id, callback, args))
            return handler_id

        def notify(self, property_name):
            signal = 'notify::{}'.format(property_name)
            for handler_id, callback, extra_args in self._signal_handlers.get(signal, []):
                callback(self, None, *extra_args)

        def disconnect(self, handler_id):
            for signal_name, handlers in self._signal_handlers.items():
                self._signal_handlers[signal_name] = [
                    h for h in handlers if h[0] != handler_id
                ]

    class _Property:
        """Descriptor that mimics GObject.Property for testing."""

        def __init__(self, getter=None, setter=None, **kwargs):
            self._getter = getter
            self._setter = setter
            self._attr_name = None

        def __set_name__(self, owner, name):
            self._attr_name = '_gprop_{}'.format(name)

        def __get__(self, obj, objtype=None):
            if obj is None:
                return self
            if self._getter and self._attr_name not in obj.__dict__:
                return self._getter(obj)
            return obj.__dict__.get(
                self._attr_name,
                self._getter(obj) if self._getter else None)

        def __set__(self, obj, value):
            if self._setter:
                self._setter(obj, value)
            else:
                obj.__dict__[self._attr_name] = value

        def setter(self, func):
            return _Property(self._getter, func)

    # Build the mock GObject module
    mock_gobject = types.ModuleType('gi.repository.GObject')
    mock_gobject.Object = _GObjectBase
    mock_gobject.Property = _Property
    mock_gobject.SignalFlags = MagicMock()
    mock_gobject.TYPE_PYOBJECT = 'pyobject'

    # Build the mock Gio module
    mock_gio = types.ModuleType('gi.repository.Gio')
    mock_gio.Settings = MagicMock
    mock_gio.SettingsBindFlags = MagicMock()
    mock_gio.BusType = MagicMock()
    mock_gio.bus_get = MagicMock()

    # Build the mock GLib module
    mock_glib = types.ModuleType('gi.repository.GLib')
    mock_glib.Error = type('GLibError', (Exception,), {})

    # Build the mock Gtk module
    mock_gtk = types.ModuleType('gi.repository.Gtk')
    mock_gtk.ListBoxRow = type('ListBoxRow', (), {
        '__init__': lambda self, **kw: None,
    })
    mock_gtk.Box = MagicMock
    mock_gtk.Label = MagicMock
    mock_gtk.Switch = MagicMock
    mock_gtk.Align = MagicMock()
    mock_gtk.Dialog = type('Dialog', (), {})
    mock_gtk.DialogFlags = MagicMock()
    mock_gtk.MessageType = MagicMock()
    mock_gtk.ButtonsType = MagicMock()
    mock_gtk.MessageDialog = MagicMock
    mock_gtk.ResponseType = MagicMock()
    mock_gtk.Orientation = MagicMock()
    mock_gtk.Separator = MagicMock
    mock_gtk.Template = MagicMock()

    # Build the mock Pango module
    mock_pango = types.ModuleType('gi.repository.Pango')
    mock_pango.EllipsizeMode = MagicMock()

    # Set up gi module hierarchy in sys.modules
    gi_mod = sys.modules.get('gi', types.ModuleType('gi'))
    gi_mod.require_version = lambda *a: None
    gi_repository = types.ModuleType('gi.repository')
    gi_repository.GObject = mock_gobject
    gi_repository.Gio = mock_gio
    gi_repository.GLib = mock_glib
    gi_repository.Gtk = mock_gtk
    gi_repository.Pango = mock_pango

    sys.modules['gi'] = gi_mod
    sys.modules['gi.repository'] = gi_repository
    sys.modules['gi.repository.GObject'] = mock_gobject
    sys.modules['gi.repository.Gio'] = mock_gio
    sys.modules['gi.repository.GLib'] = mock_glib
    sys.modules['gi.repository.Gtk'] = mock_gtk
    sys.modules['gi.repository.Pango'] = mock_pango
