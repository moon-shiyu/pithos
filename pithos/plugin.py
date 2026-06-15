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


import logging
import glob
import os
from gi.repository import (
    GLib,
    Gio,
    GObject
)


class PithosPlugin(GObject.Object):
    __gtype_name__ = 'PithosPlugin'

    _PITHOS_PLUGIN = True # used to find the plugin class in a module
    preference = None
    description = ""

    def __init__(self, name, window, bus):
        super().__init__()
        self.name = name
        self.window = window
        self.bus = bus
        self.preferences_dialog = None
        self.prepared = False
        self._enabled = False
        self.error = None

    @GObject.Property
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, enabled):
        self._enabled = enabled

    def enable(self):
        if not self.prepared:
            logging.info('Preparing module {}'.format(self.name))
            self.on_prepare()
        elif not self.error and not self.enabled:
            self._enable()

    def _enable(self):
        logging.info('Enabling module {}'.format(self.name))
        self.on_enable()
        self.enabled = True

    def disable(self):
        if self.enabled:
            logging.info('Disabling module {}'.format(self.name))
            self.on_disable()
            self.enabled = False

    def prepare_complete(self, error=None):
        self.prepared = True
        if error:
            self.on_error(error)
        else:
            self._enable()

    def on_error(self, error):
        self.error = str(error)
        if hasattr(self, 'settings') and self.settings is not None:
            self.settings['enabled'] = False

    def on_prepare(self):
        pass

    def on_enable(self):
        pass

    def on_disable(self):
        pass


class ErrorPlugin(PithosPlugin):
    __gtype_name__ = 'PithosErrorPlugin'

    def __init__(self, name, window, bus, error):
        super().__init__(name, window, bus)
        self.prepared = True
        self.error = str(error)
        self.description = 'Error loading plugin: {}'.format(self.error)
        logging.error('Error loading plugin %s: %s', name, self.error)


def _import_plugin_module(name):
    """Import and return the plugin submodule. Separated for testability."""
    module = __import__('pithos.plugins.' + name)
    return getattr(module.plugins, name)


def load_plugin(name, window, bus):
    try:
        module = _import_plugin_module(name)
    except Exception as e:
        logging.exception('Failed to import plugin %s', name)
        return ErrorPlugin(name, window, bus, 'Import failed: {}'.format(e))

    # find the class object for the actual plugin
    for key, item in module.__dict__.items():
        if getattr(item, '_PITHOS_PLUGIN', False) and key != "PithosPlugin":
            plugin_class = item
            break
    else:
        return ErrorPlugin(name, window, bus, 'No PithosPlugin subclass found in module')

    try:
        return plugin_class(name, window, bus)
    except Exception as e:
        logging.exception('Failed to instantiate plugin %s', name)
        return ErrorPlugin(name, window, bus, 'Instantiation failed: {}'.format(e))


def _maybe_migrate_setting(new_setting, name):
    if name != 'notification_icon':
        return

    old_setting = Gio.Settings.new_with_path('io.github.Pithos.plugin', '/io/github/Pithos/{}/'.format(name))
    if old_setting['enabled']:
        new_setting['enabled'] = True
        old_setting.reset('enabled')


def load_plugins(window):
    def on_got_bus(source, result, userdata):
        try:
            bus = Gio.bus_get_finish(result)
            logging.info('Got session bus')
        except GLib.Error as e:
            logging.warning('Failed to connect to session bus, some plugins will not function: {}'.format(e))
            bus = None

        plugins = window.plugins

        settings = window.settings
        in_tree_plugins = settings.props.settings_schema.list_children()
        plugins_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugins")
        discovered_plugins = [fname[:-3] for fname in glob.glob1(plugins_dir, "*.py") if not fname.startswith("_")]
        discovered_plugins.sort()

        for name in discovered_plugins:
            if name not in plugins:
                plugin = plugins[name] = load_plugin(name, window, bus)
            else:
                plugin = plugins[name]

            settings_name = name.replace('_', '-')
            if settings_name in in_tree_plugins:
                plugin.settings = settings.get_child(settings_name)
                _maybe_migrate_setting(plugin.settings, name)
            else:
                # Out of tree plugin
                plugin.settings = Gio.Settings.new_with_path('io.github.Pithos.plugin',
                                                         '/io/github/Pithos/{}/'.format(settings_name))

            if plugin.settings['enabled']:
                plugin.enable()
            else:
                plugin.disable()

        window.prefs_dlg.set_plugins(window.plugins)

    Gio.bus_get(
        Gio.BusType.SESSION,
        None,
        on_got_bus,
        None,
    )
