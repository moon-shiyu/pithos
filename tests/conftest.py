# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
"""
conftest.py - Set up gi mock before any tests run.
"""

# Import _gi_mock to register mock gi modules in sys.modules
# before any test imports pithos.plugin
from tests import _gi_mock  # noqa: F401
