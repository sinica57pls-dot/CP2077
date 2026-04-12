#!/usr/bin/env python3
"""
RED4 Mod Test Runner
====================

Discovers and runs all test suites in tests/mods/.
No dependencies required -- just Python 3.9+.

Usage:
    python tests/run_tests.py
"""

import sys
import os
import unittest

# Ensure tests/ is on the import path
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)

def main():
    loader = unittest.TestLoader()
    suite = loader.discover(
        start_dir=os.path.join(TESTS_DIR, 'mods'),
        pattern='test_*.py',
        top_level_dir=TESTS_DIR,
    )

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Exit with code 1 on any failure (for CI)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
