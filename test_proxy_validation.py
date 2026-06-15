#!/usr/bin/env python3
"""Standalone tests for validate_proxy / validate_proxy_url (no GTK needed)."""

import sys
import os

# Allow importing from the project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# We only need the pure-Python functions; bypass the gi import inside util.py
# by stubbing it out before importing.
import types
gi_stub = types.ModuleType('gi')
gi_stub.require_version = lambda *a: None
gi_repo = types.ModuleType('gi.repository')

class _FakeGtk:
    class Menu:
        pass
    @staticmethod
    def get_current_event_time():
        return 0

class _FakeGLib:
    class Error(Exception):
        pass

class _FakeSecret:
    Schema = type('Schema', (), {'new': staticmethod(lambda *a: None)})
    SchemaFlags = type('SchemaFlags', (), {'NONE': 0})
    SchemaAttributeType = type('SchemaAttributeType', (), {'STRING': 0})
    COLLECTION_DEFAULT = None
    COLLECTION_SESSION = None
    ServiceFlags = type('ServiceFlags', (), {'NONE': 0})
    CollectionFlags = type('CollectionFlags', (), {'NONE': 0})

gi_repo.GLib = _FakeGLib
gi_repo.Secret = _FakeSecret
gi_repo.Gtk = _FakeGtk
gi_stub.repository = gi_repo
sys.modules['gi'] = gi_stub
sys.modules['gi.repository'] = gi_repo

from pithos.util import parse_proxy, validate_proxy, validate_proxy_url  # noqa: E402

# ── helpers ──────────────────────────────────────────────────────────────────

_pass = 0
_fail = 0


def check(label, condition, detail=""):
    global _pass, _fail
    if condition:
        _pass += 1
        print("  \033[32mPASS\033[0m  {}".format(label))
    else:
        _fail += 1
        print("  \033[31mFAIL\033[0m  {} {}".format(label, detail))


def section(title):
    print("\n\033[1m=== {} ===\033[0m".format(title))


# ── parse_proxy (existing function, basic smoke tests) ───────────────────────

section("parse_proxy – smoke tests")

s, u, p, hp = parse_proxy("http://proxy.example.com:8080")
check("scheme http", s == "http", "got {!r}".format(s))
check("user None", u is None)
check("password None", p is None)
check("hostport", hp == "proxy.example.com:8080", "got {!r}".format(hp))

s, u, p, hp = parse_proxy("https://user:pass@proxy.example.com:443")
check("scheme https", s == "https")
check("user", u == "user", "got {!r}".format(u))
check("password", p == "pass", "got {!r}".format(p))
check("hostport w/ creds", hp == "proxy.example.com:443", "got {!r}".format(hp))

s, u, p, hp = parse_proxy("proxy.example.com:3128")
check("bare authority: scheme None", s is None)
check("bare authority: hostport", hp == "proxy.example.com:3128", "got {!r}".format(hp))

try:
    parse_proxy("http:bad")
    check("malformed raises ValueError", False, "did not raise")
except ValueError:
    check("malformed raises ValueError", True)


# ── validate_proxy ───────────────────────────────────────────────────────────

section("validate_proxy – valid inputs")

cases_valid = [
    ("",                                    ""),
    ("  ",                                  ""),
    ("http://proxy.example.com:8080",       "http://proxy.example.com:8080"),
    ("HTTP://proxy.example.com:8080",       "http://proxy.example.com:8080"),
    ("https://proxy.example.com:443",       "https://proxy.example.com:443"),
    ("socks5://proxy.example.com:1080",     "socks5://proxy.example.com:1080"),
    ("socks5h://tor.example.com:9050",      "socks5h://tor.example.com:9050"),
    ("http://user:pass@proxy.example.com:8080",
     "http://user:pass@proxy.example.com:8080"),
    ("http://user@proxy.example.com:8080",  "http://user@proxy.example.com:8080"),
    ("proxy.example.com:3128",              "http://proxy.example.com:3128"),
    ("proxy.example.com",                   "http://proxy.example.com"),
    ("http://proxy.example.com",            "http://proxy.example.com"),
    ("http://127.0.0.1:8080",               "http://127.0.0.1:8080"),
    ("http://[::1]:8080",                   "http://[::1]:8080"),
    ("socks4a://proxy.example.com:1080",    "socks4a://proxy.example.com:1080"),
]

for raw, expected_norm in cases_valid:
    r = validate_proxy(raw)
    label = "valid: {!r}".format(raw)
    ok = r['valid'] and r['normalized'] == expected_norm
    detail = ""
    if not r['valid']:
        detail = "(error: {})".format(r['error'])
    elif r['normalized'] != expected_norm:
        detail = "(normalized={!r}, expected={!r})".format(r['normalized'], expected_norm)
    check(label, ok, detail)


section("validate_proxy – invalid inputs")

cases_invalid = [
    ("ftp://proxy.example.com:21",      "Invalid scheme 'ftp'"),
    ("htt p://proxy.example.com:80",    "whitespace"),
    ("http://:8080",                     "missing a host"),
    ("http://proxy.example.com:99999",  "Port must be between 1 and 65535"),
    ("http://proxy.example.com:0",      "Port must be between 1 and 65535"),
    ("http://proxy.example.com:-1",     "Port must be between 1 and 65535"),
    ("http://proxy.example.com:abc",    "Invalid port number"),
    ("http:bad",                         "ValueError"),
]

for raw, expected_fragment in cases_invalid:
    r = validate_proxy(raw)
    label = "invalid: {!r}".format(raw)
    ok = not r['valid'] and r['error'] is not None
    detail = ""
    if r['valid']:
        detail = "(should be invalid, got normalized={!r})".format(r['normalized'])
    elif r['error'] and expected_fragment.lower() not in r['error'].lower():
        detail = "(error={!r}, expected to contain {!r})".format(r['error'], expected_fragment)
    check(label, ok, detail)


# ── validate_proxy_url (PAC URL) ─────────────────────────────────────────────

section("validate_proxy_url")

cases_url_valid = [
    "",
    "http://pac.example.com/proxy.pac",
    "https://pac.example.com/proxy.pac",
]
for raw in cases_url_valid:
    r = validate_proxy_url(raw)
    check("url valid: {!r}".format(raw), r['valid'], "error={}".format(r['error']))

cases_url_invalid = [
    ("ftp://pac.example.com/proxy.pac",  "http:// or https://"),
    ("not-a-url",                         "http:// or https://"),
    ("http://",                            "missing a hostname"),
]
for raw, expected_fragment in cases_url_invalid:
    r = validate_proxy_url(raw)
    label = "url invalid: {!r}".format(raw)
    ok = not r['valid'] and r['error'] is not None
    detail = ""
    if r['valid']:
        detail = "(should be invalid)"
    elif expected_fragment.lower() not in r['error'].lower():
        detail = "(error={!r})".format(r['error'])
    check(label, ok, detail)


# ── summary ──────────────────────────────────────────────────────────────────

print("\n" + "=" * 50)
total = _pass + _fail
if _fail:
    print("\033[31m{}/{} tests FAILED\033[0m".format(_fail, total))
    sys.exit(1)
else:
    print("\033[32mAll {} tests PASSED\033[0m".format(total))
    sys.exit(0)
