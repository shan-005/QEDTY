import hashlib
import json
import time

from pathlib import Path
from typing import Any

from seraph.config import CacheConfig


class ScanCache:
    def __init__(self, config: CacheConfig):
        self.config = config
        self.cache_dir = config.directory
        self.cache_file = self.cache_dir / "scan_cache.json"
        self._cache: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if not self.config.enabled or not self.cache_file.exists():
            return
        try:
            data = json.loads(self.cache_file.read_text(encoding="utf-8"))
            if time.time() - data.get("timestamp", 0) < self.config.ttl_seconds:
                self._cache = data.get("files", {})
            else:
                self._cache = {}
        except (json.JSONDecodeError, OSError):
            self._cache = {}

    def save(self) -> None:
        if not self.config.enabled:
            return
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.cache_file.write_text(
                json.dumps({"timestamp": time.time(), "files": self._cache}, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    def get_file_hash(self, file_path: Path) -> str:
        hasher = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
        except (OSError, PermissionError):
            return ""
        return hasher.hexdigest()

    def is_changed(self, file_path: Path) -> bool:
        if not self.config.enabled:
            return True
        file_hash = self.get_file_hash(file_path)
        if not file_hash:
            return True
        return self._cache.get(str(file_path)) != file_hash

    def update(self, file_path: Path) -> None:
        file_hash = self.get_file_hash(file_path)
        if file_hash:
            self._cache[str(file_path)] = file_hash

    def get_unchanged_files(self) -> list[str]:
        return list(self._cache.keys())

    def clear(self) -> None:
        self._cache = {}
        if self.cache_file.exists():
            self.cache_file.unlink()

    @property
    def size(self) -> int:
        return len(self._cache)
