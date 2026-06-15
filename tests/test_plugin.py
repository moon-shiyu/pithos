# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
"""
Tests for pithos.plugin — ErrorPlugin, load_plugin(), and load_plugins() resilience.

These tests run without PyGObject/GTK/D-Bus by using the mock gi stack
installed by conftest.py.
"""
import types
from unittest.mock import MagicMock, patch

import pytest

from pithos.plugin import PithosPlugin, ErrorPlugin, load_plugin


class TestErrorPlugin:
    """Tests for ErrorPlugin sentinel class."""

    def test_has_correct_attributes(self):
        plugin = ErrorPlugin('test_plugin', 'some error message')
        assert plugin.name == 'test_plugin'
        assert plugin.error == 'some error message'
        assert plugin.prepared is True
        assert plugin._enabled is False
        assert 'some error message' in plugin.description

    def test_inherits_pithos_plugin(self):
        plugin = ErrorPlugin('test_plugin', 'err')
        assert isinstance(plugin, PithosPlugin)

    def test_connect_works(self):
        """GObject signal connect should not raise."""
        plugin = ErrorPlugin('test_plugin', 'err')
        handler_id = plugin.connect('notify::enabled', lambda *a: None)
        assert handler_id > 0
        plugin.disconnect(handler_id)

    def test_enable_is_noop(self):
        plugin = ErrorPlugin('test_plugin', 'err')
        plugin.enable()
        assert plugin._enabled is False

    def test_disable_is_noop(self):
        plugin = ErrorPlugin('test_plugin', 'err')
        plugin.disable()
        assert plugin._enabled is False

    def test_str_coercion(self):
        """Error argument is coerced to string even if an Exception object is passed."""
        exc = ImportError('No module named foo')
        plugin = ErrorPlugin('test_plugin', exc)
        assert isinstance(plugin.error, str)
        assert 'No module named foo' in plugin.error

    def test_on_error_does_not_access_settings(self):
        """on_error should work without settings attribute being set."""
        plugin = ErrorPlugin('test_plugin', 'initial error')
        plugin.on_error('new error')
        assert plugin.error == 'new error'


class TestLoadPlugin:
    """Tests for load_plugin() function."""

    def test_import_error_returns_error_plugin(self):
        with patch('builtins.__import__', side_effect=ImportError('No module named pithos.plugins.nonexistent')):
            result = load_plugin('nonexistent', None, None)
        assert isinstance(result, ErrorPlugin)
        assert 'No module named' in result.error

    def test_syntax_error_returns_error_plugin(self):
        with patch('builtins.__import__', side_effect=SyntaxError('invalid syntax')):
            result = load_plugin('broken', None, None)
        assert isinstance(result, ErrorPlugin)
        assert 'invalid syntax' in result.error

    def test_attribute_error_returns_error_plugin(self):
        with patch('builtins.__import__', side_effect=AttributeError("module has no attribute 'plugins'")):
            result = load_plugin('broken', None, None)
        assert isinstance(result, ErrorPlugin)
        assert result.error

    def test_missing_plugin_class_returns_error_plugin(self):
        """Module that loads but contains no class with _PITHOS_PLUGIN."""
        fake_plugins_mod = types.ModuleType('pithos.plugins.empty_mod')
        fake_plugins_mod.SomeClass = type('SomeClass', (), {})

        fake_plugins = types.ModuleType('pithos.plugins')
        fake_plugins.empty_mod = fake_plugins_mod

        fake_pithos = types.ModuleType('pithos')
        fake_pithos.plugins = fake_plugins

        def fake_import(name, *args, **kwargs):
            if name == 'pithos.plugins.empty_mod':
                return fake_pithos
            raise ImportError(name)

        with patch('builtins.__import__', side_effect=fake_import):
            result = load_plugin('empty_mod', None, None)
        assert isinstance(result, ErrorPlugin)
        assert 'Could not find plugin class' in result.error

    def test_plugin_init_exception_returns_error_plugin(self):
        """Plugin class found but its __init__ raises."""

        class CrashPlugin(PithosPlugin):
            _PITHOS_PLUGIN = True

            def __init__(self, name, window, bus):
                raise RuntimeError('init crashed')

        fake_plugins_mod = types.ModuleType('pithos.plugins.crash')
        fake_plugins_mod.CrashPlugin = CrashPlugin

        fake_plugins = types.ModuleType('pithos.plugins')
        fake_plugins.crash = fake_plugins_mod

        fake_pithos = types.ModuleType('pithos')
        fake_pithos.plugins = fake_plugins

        def fake_import(name, *args, **kwargs):
            if name == 'pithos.plugins.crash':
                return fake_pithos
            raise ImportError(name)

        with patch('builtins.__import__', side_effect=fake_import):
            result = load_plugin('crash', MagicMock(), MagicMock())
        assert isinstance(result, ErrorPlugin)
        assert 'init crashed' in result.error

    def test_successful_load(self):
        """Valid plugin module returns an instance of the plugin class."""

        class GoodPlugin(PithosPlugin):
            _PITHOS_PLUGIN = True
            description = "A good plugin"

        fake_plugins_mod = types.ModuleType('pithos.plugins.good')
        fake_plugins_mod.GoodPlugin = GoodPlugin

        fake_plugins = types.ModuleType('pithos.plugins')
        fake_plugins.good = fake_plugins_mod

        fake_pithos = types.ModuleType('pithos')
        fake_pithos.plugins = fake_plugins

        def fake_import(name, *args, **kwargs):
            if name == 'pithos.plugins.good':
                return fake_pithos
            raise ImportError(name)

        mock_window = MagicMock()
        mock_bus = MagicMock()

        with patch('builtins.__import__', side_effect=fake_import):
            result = load_plugin('good', mock_window, mock_bus)
        assert isinstance(result, GoodPlugin)
        assert not isinstance(result, ErrorPlugin)
        assert result.name == 'good'
        assert result.window is mock_window
        assert result.bus is mock_bus


class TestLoadPluginsLoop:
    """Tests for load_plugins() loop resilience."""

    def test_one_bad_plugin_does_not_block_others(self, mock_window, mock_settings):
        """If one plugin fails mid-loop, other plugins still load and set_plugins is called."""
        from pithos.plugin import load_plugins

        good1 = MagicMock(spec=['prepared', 'error', 'settings', 'enable', 'disable'])
        good1.prepared = False
        good1.error = None

        good2 = MagicMock(spec=['prepared', 'error', 'settings', 'enable', 'disable'])
        good2.prepared = False
        good2.error = None

        def fake_load_plugin(name, window, bus):
            if name == 'bad':
                raise RuntimeError('unexpected failure')
            elif name == 'good1':
                return good1
            elif name == 'good2':
                return good2

        with patch('pithos.plugin.load_plugin', side_effect=fake_load_plugin), \
             patch('pithos.plugin.glob.glob1', return_value=['good1.py', 'bad.py', 'good2.py']), \
             patch('pithos.plugin.os.path.dirname', return_value='/fake'), \
             patch('pithos.plugin.os.path.abspath', return_value='/fake/plugin.py'), \
             patch('pithos.plugin.Gio.bus_get') as mock_bus_get, \
             patch('pithos.plugin.Gio.bus_get_finish', return_value=MagicMock()), \
             patch('pithos.plugin.Gio.Settings.new_with_path', return_value=mock_settings), \
             patch('pithos.plugin._maybe_migrate_setting'):

            def call_callback(bus_type, cancel, callback, userdata):
                callback(None, MagicMock(), userdata)

            mock_bus_get.side_effect = call_callback
            load_plugins(mock_window)

        assert 'good1' in mock_window.plugins
        assert 'bad' in mock_window.plugins
        assert 'good2' in mock_window.plugins
        assert isinstance(mock_window.plugins['bad'], ErrorPlugin)
        mock_window.prefs_dlg.set_plugins.assert_called_once()

    def test_set_plugins_always_called(self, mock_window, mock_settings):
        """set_plugins is called even when all plugins fail."""
        from pithos.plugin import load_plugins

        def fake_load_plugin(name, window, bus):
            raise RuntimeError('all fail')

        with patch('pithos.plugin.load_plugin', side_effect=fake_load_plugin), \
             patch('pithos.plugin.glob.glob1', return_value=['p1.py', 'p2.py']), \
             patch('pithos.plugin.os.path.dirname', return_value='/fake'), \
             patch('pithos.plugin.os.path.abspath', return_value='/fake/plugin.py'), \
             patch('pithos.plugin.Gio.bus_get') as mock_bus_get, \
             patch('pithos.plugin.Gio.bus_get_finish', return_value=MagicMock()), \
             patch('pithos.plugin.Gio.Settings.new_with_path', return_value=mock_settings), \
             patch('pithos.plugin._maybe_migrate_setting'):

            def call_callback(bus_type, cancel, callback, userdata):
                callback(None, MagicMock(), userdata)

            mock_bus_get.side_effect = call_callback
            load_plugins(mock_window)

        mock_window.prefs_dlg.set_plugins.assert_called_once()
        assert len(mock_window.plugins) == 2
        for plugin in mock_window.plugins.values():
            assert isinstance(plugin, ErrorPlugin)
