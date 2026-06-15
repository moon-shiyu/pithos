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
import os
from urllib.parse import splittype, splituser, splitpasswd

import gi
gi.require_version('Secret', '1')
from gi.repository import (
    GLib,
    Secret,
    Gtk
)


class _SecretService:

    _account_schema = Secret.Schema.new(
        'io.github.Pithos.Account',
        Secret.SchemaFlags.NONE,
        {'email': Secret.SchemaAttributeType.STRING},
    )

    def __init__(self):
        self._current_collection = Secret.COLLECTION_DEFAULT

    def unlock_keyring(self, callback):
        # Inside of flatpak we only have access to the simple API.
        if is_flatpak():
            callback(None)
            return

        def on_unlock_finish(source, result, data):
            service, default_collection = data
            try:
                num_items, unlocked = service.unlock_finish(result)
            except GLib.Error as e:
                logging.error('Error on service.unlock, Error: {}'.format(e))
                callback(e)
            else:
                if not num_items or default_collection not in unlocked:
                    self._current_collection = Secret.COLLECTION_SESSION
                    logging.debug('The default keyring is still locked. Using session collection.')
                else:
                    logging.debug('The default keyring was unlocked.')
                callback(None)

        def on_for_alias_finish(source, result, service):
            try:
                default_collection = Secret.Collection.for_alias_finish(result)
            except GLib.Error as e:
                logging.error('Error getting Secret.COLLECTION_DEFAULT, Error: {}'.format(e))
                callback(e)
            else:
                if default_collection is None:
                    logging.warning(
                        'Could not get the default Secret Collection.\n'
                        'Attempting to use the session Collection.'
                    )

                    self._current_collection = Secret.COLLECTION_SESSION
                    callback(None)

                elif default_collection.get_locked():
                    logging.debug('The default keyring is locked.')
                    service.unlock(
                        [default_collection],
                        None,
                        on_unlock_finish,
                        (service, default_collection),
                    )

                else:
                    logging.debug('The default keyring is unlocked.')
                    callback(None)

        def on_get_finish(source, result, data):
            try:
                service = Secret.Service.get_finish(result)
            except GLib.Error as e:
                logging.error('Failed to get Secret.Service, Error: {}'.format(e))
                callback(e)
            else:
                Secret.Collection.for_alias(
                    service,
                    Secret.COLLECTION_DEFAULT,
                    Secret.CollectionFlags.NONE,
                    None,
                    on_for_alias_finish,
                    service,
                )

        Secret.Service.get(
            Secret.ServiceFlags.NONE,
            None,
            on_get_finish,
            None,
        )

    def get_account_password(self, email, callback):
        def on_password_lookup_finish(_, result):
            try:
                password = Secret.password_lookup_finish(result) or ''
                callback(password)
            except GLib.Error as e:
                logging.error('Failed to lookup password async, Error: {}'.format(e))
                callback('')

        # The async version of this hangs forever in flatpak and its been broken for years
        # so for now lets just use the sync version as it works.
        if is_flatpak():
            try:
                password = Secret.password_lookup_sync(
                    self._account_schema,
                    {'email': email},
                    None,
                ) or ''
                callback(password)
            except GLib.Error as e:
                logging.error('Failed to lookup password sync, Error: {}'.format(e))
                callback('')
            return

        Secret.password_lookup(
            self._account_schema,
            {'email': email},
            None,
            on_password_lookup_finish,
        )

    def set_account_password(self, old_email, new_email, password, callback):
        def on_password_store_finish(source, result, data):
            try:
                success = Secret.password_store_finish(result)
            except GLib.Error as e:
                logging.error('Failed to store password, Error: {}'.format(e))
                success = False
            if callback:
                callback(success)

        def on_password_clear_finish(source, result, data):
            try:
                password_removed = Secret.password_clear_finish(result)
                if password_removed:
                    logging.debug('Cleared password for: {}'.format(old_email))
                else:
                    logging.debug('No password found to clear for: {}'.format(old_email))
            except GLib.Error as e:
                logging.error('Failed to clear password for: {}, Error: {}'.format(old_email, e))
                if callback:
                    callback(False)
            else:
                Secret.password_store(
                    self._account_schema,
                    {'email': new_email},
                    self._current_collection,
                    'Pandora Account',
                    password,
                    None,
                    on_password_store_finish,
                    None,
                )

        if old_email and old_email != new_email:
            Secret.password_clear(
                self._account_schema,
                {'email': old_email},
                None,
                on_password_clear_finish,
                None,
            )

        else:
            Secret.password_store(
                self._account_schema,
                {'email': new_email},
                self._current_collection,
                'Pandora Account',
                password,
                None,
                on_password_store_finish,
                None,
            )


SecretService = _SecretService()


def parse_proxy(proxy):
    """ _parse_proxy from urllib """
    scheme, r_scheme = splittype(proxy)
    if not r_scheme.startswith("/"):
        # authority
        scheme = None
        authority = proxy
    else:
        # URL
        if not r_scheme.startswith("//"):
            raise ValueError("proxy URL with no authority: %r" % proxy)
        # We have an authority, so for RFC 3986-compliant URLs (by ss 3.
        # and 3.3.), path is empty or starts with '/'
        end = r_scheme.find("/", 2)
        if end == -1:
            end = None
        authority = r_scheme[2:end]
    userinfo, hostport = splituser(authority)
    if userinfo is not None:
        user, password = splitpasswd(userinfo)
    else:
        user = password = None
    return scheme, user, password, hostport


_VALID_PROXY_SCHEMES = ('http', 'https', 'socks4', 'socks4a', 'socks5', 'socks5h')


def validate_proxy(proxy):
    """Validate a proxy string and return a structured result.

    Returns a dict with:
        valid (bool):       True if the proxy is valid (or empty).
        error (str|None):   Error message when invalid, else None.
        normalized (str):   Standardized proxy string (empty when invalid).
        scheme (str|None):  Parsed scheme (lowercased).
        user (str|None):    Parsed username.
        password (str|None): Parsed password.
        host (str|None):    Parsed hostname / IP.
        port (int|None):    Parsed port number.
    """
    result = {
        'valid': True,
        'error': None,
        'normalized': '',
        'scheme': None,
        'user': None,
        'password': None,
        'host': None,
        'port': None,
    }

    if not proxy or not proxy.strip():
        return result

    proxy = proxy.strip()

    if ' ' in proxy or '\t' in proxy or '\n' in proxy:
        result['valid'] = False
        result['error'] = "Proxy address must not contain whitespace"
        return result

    try:
        scheme, user, password, hostport = parse_proxy(proxy)
    except ValueError as e:
        result['valid'] = False
        result['error'] = str(e)
        return result

    # --- scheme ---
    if scheme is not None:
        scheme_lower = scheme.lower()
        if scheme_lower not in _VALID_PROXY_SCHEMES:
            result['valid'] = False
            result['error'] = (
                "Invalid scheme '{}'. Expected one of: {}".format(
                    scheme, ', '.join(_VALID_PROXY_SCHEMES)
                )
            )
            return result
        scheme = scheme_lower
    # scheme may be None (bare authority like host:port) — that is acceptable.

    # --- hostport ---
    if not hostport:
        result['valid'] = False
        result['error'] = "Proxy address is missing a host"
        return result

    # Bracket-aware split for IPv6 (e.g. [::1]:8080)
    if hostport.startswith('['):
        bracket_end = hostport.find(']')
        if bracket_end == -1:
            result['valid'] = False
            result['error'] = "Unclosed bracket in host"
            return result
        host = hostport[:bracket_end + 1]
        rest = hostport[bracket_end + 1:]
        if rest.startswith(':'):
            port_str = rest[1:]
        elif rest == '':
            port_str = None
        else:
            result['valid'] = False
            result['error'] = "Unexpected characters after host: '{}'".format(rest)
            return result
    else:
        colon = hostport.rfind(':')
        if colon != -1:
            host = hostport[:colon]
            port_str = hostport[colon + 1:] or None
        else:
            host = hostport
            port_str = None

    if not host:
        result['valid'] = False
        result['error'] = "Proxy address is missing a host"
        return result

    port = None
    if port_str is not None:
        try:
            port = int(port_str)
        except ValueError:
            result['valid'] = False
            result['error'] = "Invalid port number: '{}'".format(port_str)
            return result
        if port < 1 or port > 65535:
            result['valid'] = False
            result['error'] = "Port must be between 1 and 65535 (got {})".format(port)
            return result

    # --- build normalized form ---
    norm_scheme = scheme if scheme is not None else 'http'
    host_display = host.lower()

    normalized = norm_scheme + '://'
    if user is not None:
        normalized += user
        if password is not None:
            normalized += ':' + password
        normalized += '@'
    normalized += host_display
    if port is not None:
        normalized += ':' + str(port)

    result['normalized'] = normalized
    result['scheme'] = scheme
    result['user'] = user
    result['password'] = password
    result['host'] = host_display
    result['port'] = port
    return result


def validate_proxy_url(url):
    """Validate a PAC (or general HTTP/HTTPS) URL.

    Returns a dict with:
        valid (bool):     True if the URL looks valid.
        error (str|None): Error message when invalid, else None.
    """
    result = {'valid': True, 'error': None}

    if not url or not url.strip():
        return result

    url = url.strip()

    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
    except Exception:
        result['valid'] = False
        result['error'] = "Invalid URL format"
        return result

    if parsed.scheme not in ('http', 'https'):
        result['valid'] = False
        result['error'] = "URL must start with http:// or https://"
        return result

    if not parsed.netloc:
        result['valid'] = False
        result['error'] = "URL is missing a hostname"
        return result

    return result


def open_browser(url, parent=None, timestamp=0):
    logging.info("Opening URL {}".format(url))
    if not timestamp:
        timestamp = Gtk.get_current_event_time()
    try:
        if hasattr(Gtk, 'show_uri_on_window'):
            Gtk.show_uri_on_window(parent, url, timestamp)
        else: # Gtk <= 3.20
            screen = None
            if parent:
                screen = parent.get_screen()
            Gtk.show_uri(screen, url, timestamp)
    except GLib.Error as e:
        logging.warning('Failed to open URL: {}'.format(e.message))

if hasattr(Gtk.Menu, 'popup_at_pointer'):
    popup_at_pointer = Gtk.Menu.popup_at_pointer
else:
    popup_at_pointer = lambda menu, event: menu.popup(None, None, None, None, event.button, event.time)

_is_flatpak = None
def is_flatpak() -> bool:
    global _is_flatpak

    if _is_flatpak is None:
        _is_flatpak = os.path.exists('/.flatpak-info')

    return _is_flatpak
