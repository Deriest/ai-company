"""Test isolation for the backend suite.

QA-HARDENING: tests previously shared the persistent backend/data/aic.db,
which caused DB-state flakiness (StaleDataError / count mismatches) when a
live backend or a prior test run left rows behind. This conftest redirects
AIC_DATA_DIR to a per-session temp directory BEFORE backend.config is first
imported, so every test run uses a clean, isolated SQLite database.
"""
import os
import tempfile

# Must be set before backend.config / backend.database.session are imported.
_TEST_DATA_DIR = tempfile.mkdtemp(prefix="aic-test-data-")
os.environ["AIC_DATA_DIR"] = _TEST_DATA_DIR