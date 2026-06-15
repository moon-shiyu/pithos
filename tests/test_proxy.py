# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
"""Tests for proxy parsing / validation in pithos.util.

These tests run without GTK by mocking the gi stack so that only
the pure-Python proxy helpers are exercised.
"""

import sys
import types
import unittest
from unittest.mock import MagicMock

# ---------- mock gi before importing pithos.util ----------
_gi = types.ModuleType('gi')
_gi.require_version = MagicMock()
_gi_repository = types.ModuleType('gi.repository')
_gi_repository.GLib = MagicMock()
_gi_repository.Secret = MagicMock()
_gi_repository.Gtk = MagicMock()
_gi.repository = _gi_repository

sys.modules.setdefault('gi', _gi)
sys.modules.setdefault('gi.repository', _gi_repository)

from pithos.util import (  # noqa: E402
    parse_proxy,
    validate_proxy,
    format_proxy_display,
    _split_hostport,
)


class TestParseProxy(unittest.TestCase):
    """Low-level parse_proxy (unchanged upstream behaviour)."""

    def test_simple_host_port(self):
        scheme, user, pw, hostport = parse_proxy('myproxy.example.com:8080')
        self.assertIsNone(scheme)
        self.assertIsNone(user)
        self.assertIsNone(pw)
        self.assertEqual(hostport, 'myproxy.example.com:8080')

    def test_http_scheme(self):
        scheme, user, pw, hostport = parse_proxy('http://proxy.local:3128')
        self.assertEqual(scheme, 'http')
        self.assertEqual(hostport, 'proxy.local:3128')

    def test_socks5_with_auth(self):
        scheme, user, pw, hostport = parse_proxy('socks5://admin:secret@proxy:1080')
        self.assertEqual(scheme, 'socks5')
        self.assertEqual(user, 'admin')
        self.assertEqual(pw, 'secret')
        self.assertEqual(hostport, 'proxy:1080')

    def test_no_authority_raises(self):
        with self.assertRaises(ValueError):
            parse_proxy('http:/bad')


class TestSplitHostport(unittest.TestCase):

    def test_host_and_port(self):
        self.assertEqual(_split_hostport('host:8080'), ('host', '8080'))

    def test_host_only(self):
        self.assertEqual(_split_hostport('host'), ('host', None))

    def test_ipv6_with_port(self):
        self.assertEqual(_split_hostport('[::1]:9090'), ('::1', '9090'))

    def test_ipv6_no_port(self):
        self.assertEqual(_split_hostport('[::1]'), ('::1', None))

    def test_ipv6_unterminated(self):
        with self.assertRaises(ValueError):
            _split_hostport('[::1')


class TestValidateProxy(unittest.TestCase):
    """validate_proxy: full validation including scheme, host, port."""

    # -- empty / whitespace --
    def test_empty_string(self):
        r = validate_proxy('')
        self.assertTrue(r['valid'])
        self.assertEqual(r['display'], '')

    def test_whitespace_only(self):
        r = validate_proxy('   ')
        self.assertTrue(r['valid'])

    def test_none(self):
        r = validate_proxy(None)
        self.assertTrue(r['valid'])

    # -- valid proxies --
    def test_simple_host_port(self):
        r = validate_proxy('proxy.example.com:3128')
        self.assertTrue(r['valid'])
        self.assertIsNone(r['scheme'])
        self.assertEqual(r['host'], 'proxy.example.com')
        self.assertEqual(r['port'], 3128)
        self.assertEqual(r['display'], 'proxy.example.com:3128')

    def test_http_scheme(self):
        r = validate_proxy('http://proxy:8080')
        self.assertTrue(r['valid'])
        self.assertEqual(r['scheme'], 'http')
        self.assertEqual(r['display'], 'http://proxy:8080')

    def test_https_scheme(self):
        r = validate_proxy('https://secure.proxy:443')
        self.assertTrue(r['valid'])
        self.assertEqual(r['scheme'], 'https')

    def test_socks5_scheme(self):
        r = validate_proxy('socks5://s:1080')
        self.assertTrue(r['valid'])
        self.assertEqual(r['scheme'], 'socks5')

    def test_socks4a_scheme(self):
        r = validate_proxy('SOCKS4A://s:1080')
        self.assertTrue(r['valid'])
        self.assertEqual(r['scheme'], 'socks4a')

    def test_host_no_port(self):
        r = validate_proxy('proxy.example.com')
        self.assertTrue(r['valid'])
        self.assertIsNone(r['port'])

    def test_auth(self):
        r = validate_proxy('http://alice:pa%24%24@proxy:3128')
        self.assertTrue(r['valid'])
        self.assertEqual(r['user'], 'alice')
        self.assertEqual(r['display'], 'http://alice:***@proxy:3128')

    def test_user_no_password(self):
        r = validate_proxy('http://bob@proxy:3128')
        self.assertTrue(r['valid'])
        self.assertEqual(r['user'], 'bob')
        self.assertIsNone(r['password'])
        self.assertIn('bob@', r['display'])
        self.assertNotIn('***', r['display'])

    def test_ipv6(self):
        r = validate_proxy('http://[::1]:8080')
        self.assertTrue(r['valid'])
        self.assertEqual(r['host'], '::1')
        self.assertEqual(r['port'], 8080)
        self.assertEqual(r['display'], 'http://[::1]:8080')

    # -- invalid proxies --
    def test_bad_scheme(self):
        r = validate_proxy('ftp://proxy:21')
        self.assertFalse(r['valid'])
        self.assertIn('unsupported', r['error'])

    def test_missing_host(self):
        r = validate_proxy('http://:8080')
        self.assertFalse(r['valid'])
        self.assertIn('host', r['error'].lower())

    def test_port_not_integer(self):
        r = validate_proxy('proxy:abc')
        self.assertFalse(r['valid'])
        self.assertIn('invalid proxy port', r['error'])

    def test_port_out_of_range_zero(self):
        r = validate_proxy('proxy:0')
        self.assertFalse(r['valid'])
        self.assertIn('out of range', r['error'])

    def test_port_out_of_range_high(self):
        r = validate_proxy('proxy:70000')
        self.assertFalse(r['valid'])
        self.assertIn('out of range', r['error'])

    def test_no_authority(self):
        r = validate_proxy('http:/bad')
        self.assertFalse(r['valid'])

    # -- whitespace trimming --
    def test_leading_trailing_whitespace(self):
        r = validate_proxy('  http://proxy:8080  ')
        self.assertTrue(r['valid'])
        self.assertEqual(r['host'], 'proxy')


class TestFormatProxyDisplay(unittest.TestCase):

    def test_invalid_returns_empty(self):
        self.assertEqual(format_proxy_display({'valid': False}), '')

    def test_no_host_returns_empty(self):
        self.assertEqual(format_proxy_display({'valid': True, 'host': None}), '')

    def test_full_proxy(self):
        info = {
            'valid': True, 'scheme': 'http', 'user': 'u',
            'password': 'p', 'host': 'h', 'port': 80,
        }
        self.assertEqual(format_proxy_display(info), 'http://u:***@h:80')

    def test_ipv6_display(self):
        info = {
            'valid': True, 'scheme': 'socks5', 'user': None,
            'password': None, 'host': 'fe80::1', 'port': 1080,
        }
        self.assertEqual(format_proxy_display(info), 'socks5://[fe80::1]:1080')


if __name__ == '__main__':
    unittest.main()
