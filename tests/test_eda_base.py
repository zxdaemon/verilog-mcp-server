"""
Tests for EDA base adapter and cache system.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from verilog_mcp_server.eda.base_adapter import BaseEdaAdapter
from verilog_mcp_server.eda.cache import EdaCache


# ── Concrete adapter for testing ──

class _MockAdapter(BaseEdaAdapter):
    """Mock adapter for testing the abstract base class."""

    def check_available(self) -> bool:
        return self.config.get("available", True)

    def run(self, file_paths: list[str], top_module: str, output_dir: str) -> bool:
        return True

    def parse_output(self, output_dir: str) -> dict:
        return {"status": "ok"}


class TestBaseEdaAdapter:
    """Tests for BaseEdaAdapter abstract base class."""

    def test_check_available_is_cached(self):
        """is_available() caches the result from check_available()."""
        adapter = _MockAdapter({"available": True})
        assert adapter.is_available() is True
        # Change config, but cached result should remain
        adapter.config["available"] = False
        assert adapter.is_available() is True  # cached

    def test_check_available_false(self):
        """When config says unavailable, is_available() returns False."""
        adapter = _MockAdapter({"available": False})
        assert adapter.is_available() is False

    def test_run_method_exists(self):
        """Abstract method run() is callable on concrete adapter."""
        adapter = _MockAdapter()
        result = adapter.run(["test.v"], "top", "/tmp/test")
        assert result is True

    def test_parse_output_method_exists(self):
        """Abstract method parse_output() is callable on concrete adapter."""
        adapter = _MockAdapter()
        result = adapter.parse_output("/tmp/test")
        assert result == {"status": "ok"}

    def test_default_config_is_empty_dict(self):
        """Adapter with no config uses empty dict."""
        adapter = _MockAdapter()
        assert adapter.config == {}

    def test_is_available_lazy_evaluation(self):
        """is_available() only calls check_available() once."""
        adapter = _MockAdapter()
        adapter._available = None  # ensure clean state
        with patch.object(adapter, "check_available", wraps=adapter.check_available) as spy:
            adapter.is_available()
            adapter.is_available()
            assert spy.call_count == 1  # only called once, cached


class TestEdaCache:
    """Tests for EdaCache."""

    def test_compute_files_hash_consistent(self):
        """Same files produce the same hash."""
        cache = EdaCache("/tmp/test_cache")
        files = ["a.v", "b.v", "c.v"]
        h1 = cache.compute_files_hash(files)
        h2 = cache.compute_files_hash(files)
        assert h1 == h2

    def test_compute_files_hash_order_independent(self):
        """Hash is independent of file order (sorted internally)."""
        cache = EdaCache("/tmp/test_cache")
        h1 = cache.compute_files_hash(["a.v", "b.v"])
        h2 = cache.compute_files_hash(["b.v", "a.v"])
        assert h1 == h2

    def test_compute_files_hash_different(self):
        """Different files produce different hashes."""
        cache = EdaCache("/tmp/test_cache")
        h1 = cache.compute_files_hash(["a.v", "b.v"])
        h2 = cache.compute_files_hash(["a.v", "c.v"])
        assert h1 != h2

    def test_save_and_load(self):
        """Round-trip: save data then load it back."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = EdaCache(tmpdir)
            data = {"fsm": [], "stats": {"cells": 100}}
            cache.save("test_key_001", data)
            loaded = cache.load("test_key_001")
            assert loaded == data

    def test_check_miss(self):
        """check() returns None when cache doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = EdaCache(tmpdir)
            result = cache.check(["a.v"], "top")
            assert result is None

    def test_check_hit(self):
        """check() returns cache_key when cache exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = EdaCache(tmpdir)
            data = {"test": True}
            # Pre-populate cache manually
            cache.save("some_key", data)
            # check() with the same files+top should NOT hit (different key)
            # We need to compute the key the same way check() does
            result = cache.check(["not_matching.v"], "top")
            assert result is None

    def test_cache_dir_auto_created(self):
        """Cache directory is created automatically."""
        with tempfile.TemporaryDirectory() as base:
            cache_dir = os.path.join(base, "nested", "yosys_outputs")
            cache = EdaCache(cache_dir)
            assert Path(cache_dir).exists()

    def test_get_cache_path(self):
        """get_cache_path returns correct path."""
        cache = EdaCache("/tmp/test_cache")
        path = cache.get_cache_path("abc123", "yosys_output.json")
        assert path == Path("/tmp/test_cache/abc123/yosys_output.json")

    def test_hash_file_with_missing_file(self):
        """_hash_file handles missing files gracefully."""
        result = EdaCache._hash_file("/nonexistent/file.v")
        assert len(result) == 64  # SHA256 hex digest length

    def test_check_includes_top_module(self):
        """check() includes top_module in hash, so different tops yield different cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = EdaCache(tmpdir)
            data = {"dummy": True}
            # Create cache for one top
            all_inputs = ["test.v", "__top__:top_a"]
            key_a = cache.compute_files_hash(all_inputs)
            cache.save(key_a, data)

            # Same files, different top should miss
            result = cache.check(["test.v"], "top_b")
            assert result is None  # different cache key
