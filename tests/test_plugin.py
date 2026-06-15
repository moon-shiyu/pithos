# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-

import types
import unittest
from unittest.mock import MagicMock, patch

# Set up gi mock before any gi imports
from tests import _gi_mock  # noqa: F401

import gi
gi.require_version('GObject', '2.0')
from gi.repository import GObject

from pithos.plugin import ErrorPlugin, PithosPlugin, load_plugin


class TestErrorPluginInit(unittest.TestCase):
    """Verify ErrorPlugin is properly initialized as a PithosPlugin/GObject."""

    def setUp(self):
        self.window = MagicMock()
        self.bus = MagicMock()

    def test_is_pithos_plugin_instance(self):
        ep = ErrorPlugin('test', self.window, self.bus, 'some error')
        self.assertIsInstance(ep, PithosPlugin)

    def test_is_gobject_instance(self):
        ep = ErrorPlugin('test', self.window, self.bus, 'some error')
        self.assertIsInstance(ep, GObject.Object)

    def test_error_attribute_set(self):
        ep = ErrorPlugin('test', self.window, self.bus, 'disk on fire')
        self.assertEqual(ep.error, 'disk on fire')

    def test_error_converted_to_string(self):
        ep = ErrorPlugin('test', self.window, self.bus, ValueError('bad'))
        self.assertEqual(ep.error, 'bad')

    def test_prepared_is_true(self):
        ep = ErrorPlugin('test', self.window, self.bus, 'err')
        self.assertTrue(ep.prepared)

    def test_enabled_is_false(self):
        ep = ErrorPlugin('test', self.window, self.bus, 'err')
        self.assertFalse(ep.enabled)

    def test_name_set(self):
        ep = ErrorPlugin('my_plugin', self.window, self.bus, 'err')
        self.assertEqual(ep.name, 'my_plugin')

    def test_description_contains_error(self):
        ep = ErrorPlugin('test', self.window, self.bus, 'missing dep')
        self.assertIn('missing dep', ep.description)

    def test_window_and_bus_set(self):
        ep = ErrorPlugin('test', self.window, self.bus, 'err')
        self.assertIs(ep.window, self.window)
        self.assertIs(ep.bus, self.bus)

    def test_preferences_dialog_is_none(self):
        ep = ErrorPlugin('test', self.window, self.bus, 'err')
        self.assertIsNone(ep.preferences_dialog)


class TestErrorPluginBehavior(unittest.TestCase):
    """Verify ErrorPlugin behaves correctly when methods are called."""

    def setUp(self):
        self.ep = ErrorPlugin('test', MagicMock(), MagicMock(), 'error')

    def test_enable_is_noop(self):
        self.ep.enable()
        self.assertFalse(self.ep.enabled)

    def test_disable_is_noop(self):
        self.ep.disable()
        self.assertFalse(self.ep.enabled)

    def test_gobject_connect_works(self):
        handler_id = self.ep.connect('notify::enabled', MagicMock())
        self.assertIsInstance(handler_id, int)

    def test_gobject_notify_enabled_signal(self):
        callback = MagicMock()
        self.ep.connect('notify::enabled', callback)
        self.ep._enabled = True
        self.ep.notify('enabled')
        self.assertTrue(callback.called)


class TestLoadPluginExceptions(unittest.TestCase):
    """Verify load_plugin returns ErrorPlugin for various exception types."""

    def setUp(self):
        self.window = MagicMock()
        self.bus = MagicMock()

    @patch('pithos.plugin._import_plugin_module',
           side_effect=ImportError('No module named foo'))
    def test_import_error(self, mock_import):
        plugin = load_plugin('missing', self.window, self.bus)
        self.assertIsInstance(plugin, ErrorPlugin)
        self.assertIn('Import failed', plugin.error)

    @patch('pithos.plugin._import_plugin_module',
           side_effect=SyntaxError('invalid syntax'))
    def test_syntax_error(self, mock_import):
        plugin = load_plugin('broken', self.window, self.bus)
        self.assertIsInstance(plugin, ErrorPlugin)
        self.assertIn('Import failed', plugin.error)

    @patch('pithos.plugin._import_plugin_module')
    def test_no_plugin_class(self, mock_import):
        fake_module = types.ModuleType('fake')
        fake_module.SomeClass = type('SomeClass', (), {})
        mock_import.return_value = fake_module
        plugin = load_plugin('empty', self.window, self.bus)
        self.assertIsInstance(plugin, ErrorPlugin)
        self.assertIn('No PithosPlugin subclass', plugin.error)

    @patch('pithos.plugin._import_plugin_module')
    def test_instantiation_failure(self, mock_import):
        class BrokenPlugin(PithosPlugin):
            __gtype_name__ = 'BrokenPluginTest'

            def __init__(self, name, window, bus):
                raise RuntimeError('missing dependency')

        fake_module = types.ModuleType('fake')
        fake_module.BrokenPlugin = BrokenPlugin
        mock_import.return_value = fake_module
        plugin = load_plugin('broken_init', self.window, self.bus)
        self.assertIsInstance(plugin, ErrorPlugin)
        self.assertIn('Instantiation failed', plugin.error)
        self.assertIn('missing dependency', plugin.error)

    @patch('pithos.plugin._import_plugin_module',
           side_effect=KeyboardInterrupt)
    def test_base_exception_propagates(self, mock_import):
        with self.assertRaises(KeyboardInterrupt):
            load_plugin('interrupted', self.window, self.bus)


class TestPithosPluginOnError(unittest.TestCase):
    """Test the base PithosPlugin.on_error method."""

    def test_on_error_without_settings(self):
        plugin = PithosPlugin.__new__(PithosPlugin)
        plugin.error = None
        plugin.prepared = False
        plugin._enabled = False
        plugin.on_error('test error')
        self.assertEqual(plugin.error, 'test error')

    def test_on_error_with_settings(self):
        plugin = PithosPlugin.__new__(PithosPlugin)
        plugin.error = None
        plugin.prepared = False
        plugin._enabled = False
        plugin.settings = MagicMock()
        plugin.on_error('test error')
        plugin.settings.__setitem__.assert_called_with('enabled', False)


if __name__ == '__main__':
    unittest.main()
