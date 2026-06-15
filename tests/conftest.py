# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
"""
Conftest that mocks the gi.repository stack so plugin tests run
without PyGObject / GTK / D-Bus installed.
"""
import sys
import types
from unittest.mock import MagicMock, PropertyMock

import pytest

# ---------------------------------------------------------------------------
# Build a lightweight mock of gi.repository.GObject
# ---------------------------------------------------------------------------

_signal_counter = 0


class _MockGObjectMeta(type):
    """Metaclass that silently accepts __gtype_name__."""
    pass


class _MockGObject(metaclass=_MockGObjectMeta):
    """Minimal stand-in for GObject.Object."""

    def __init__(self, *args, **kwargs):
        self._signal_handlers = {}

    def connect(self, signal_name, handler):
        global _signal_counter
        _signal_counter += 1
        handler_id = _signal_counter
        self._signal_handlers[handler_id] = (signal_name, handler)
        return handler_id

    def disconnect(self, handler_id):
        self._signal_handlers.pop(handler_id, None)

    def emit(self, signal_name, *args):
        for hid, (sig, handler) in list(self._signal_handlers.items()):
            if sig == signal_name:
                handler(self, *args)


class _MockProperty:
    """Stand-in for GObject.Property that acts as a plain descriptor."""

    def __init__(self, fget=None, type=None, default=None, **kwargs):
        self.fget = fget
        self._setter = None

    def __call__(self, fget):
        self.fget = fget
        return self

    def setter(self, fset):
        self._setter = fset
        return self

    def __set_name__(self, owner, name):
        self._name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        if self.fget:
            return self.fget(obj)
        return getattr(obj, '_prop_' + self._name, None)

    def __set__(self, obj, value):
        if self._setter:
            self._setter(obj, value)
        else:
            setattr(obj, '_prop_' + self._name, value)


class _MockSignalFlags:
    RUN_FIRST = 1
    RUN_LAST = 2


# Assemble mock GObject module
_mock_gobject = types.ModuleType('gi.repository.GObject')
_mock_gobject.Object = _MockGObject
_mock_gobject.Property = _MockProperty
_mock_gobject.SignalFlags = _MockSignalFlags
_mock_gobject.TYPE_PYOBJECT = 'PyObject'


# ---------------------------------------------------------------------------
# Build mocks for GLib and Gio
# ---------------------------------------------------------------------------

_mock_glib = types.ModuleType('gi.repository.GLib')
_mock_glib.Error = Exception
_mock_glib.markup_escape_text = lambda text, length=-1: (
    str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
)

_mock_gio = types.ModuleType('gi.repository.Gio')
_mock_gio.Settings = MagicMock()
_mock_gio.bus_get = MagicMock()
_mock_gio.bus_get_finish = MagicMock()
_mock_gio.BusType = MagicMock()
_mock_gio.SettingsBindFlags = MagicMock()
_mock_gio.SettingsBindFlags.DEFAULT = 0

# gi and gi.repository themselves
_mock_gi = types.ModuleType('gi')
_mock_gi_repository = types.ModuleType('gi.repository')
_mock_gi_repository.GObject = _mock_gobject
_mock_gi_repository.GLib = _mock_glib
_mock_gi_repository.Gio = _mock_gio
_mock_gi.repository = _mock_gi_repository


# ---------------------------------------------------------------------------
# Install mocks into sys.modules before any pithos imports
# ---------------------------------------------------------------------------

sys.modules.setdefault('gi', _mock_gi)
sys.modules.setdefault('gi.repository', _mock_gi_repository)
sys.modules.setdefault('gi.repository.GObject', _mock_gobject)
sys.modules.setdefault('gi.repository.GLib', _mock_glib)
sys.modules.setdefault('gi.repository.Gio', _mock_gio)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_settings():
    """A mock Gio.Settings that supports item access and bind()."""
    settings = MagicMock()
    settings.__getitem__ = MagicMock(return_value=False)
    settings.__setitem__ = MagicMock()
    settings.get_child = MagicMock(return_value=MagicMock())
    settings.props.settings_schema.list_children.return_value = []
    return settings


@pytest.fixture
def mock_window(mock_settings):
    """A mock PithosWindow with plugins dict and prefs_dlg."""
    window = MagicMock()
    window.plugins = {}
    window.settings = mock_settings
    window.prefs_dlg = MagicMock()
    return window
