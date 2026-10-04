"""Tests for Layer 0 & Conductor: Discovery, Caching, and Scheduler."""

from pathlib import Path

import pytest

from seraph.guard.config import CacheConfig
from seraph.guard.orchestration.cache import ScanCache
from seraph.guard.orchestration.discovery import RepoDiscovery


@pytest.mark.integration
def test_repo_discovery_languages(tmp_path: Path):
    """Verify language detection across multiple file types."""
    (tmp_path / "main.py").write_text("print('hello')")
    (tmp_path / "app.js").write_text("console.log('hello')")
    discovery = RepoDiscovery(tmp_path)
    profile = discovery.discover()
    assert "python" in profile.languages
    assert "javascript" in profile.languages
    assert profile.file_count == 2


@pytest.mark.integration
def test_repo_discovery_framework(tmp_path: Path):
    """Verify framework fingerprinting via manifest files."""
    (tmp_path / "requirements.txt").write_text("django==4.0")
    discovery = RepoDiscovery(tmp_path)
    profile = discovery.discover()
    assert profile.is_framework
    assert "Python Web Framework" in profile.frameworks


@pytest.mark.integration
def test_scan_cache_persistence(tmp_path: Path):
    """Verify incremental scan cache saves and loads file hashes correctly."""
    cache_dir = tmp_path / "cache"
    config = CacheConfig(directory=cache_dir, enabled=True, ttl_seconds=3600)
    cache = ScanCache(config)

    f = tmp_path / "test.txt"
    f.write_text("hello")

    assert cache.is_changed(f)
    cache.update(f)
    cache.save()

    # Reload from disk
    cache2 = ScanCache(config)
    assert not cache2.is_changed(f)

    # Modify file
    f.write_text("world")
    assert cache2.is_changed(f)
