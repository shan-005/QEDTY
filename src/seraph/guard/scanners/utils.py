import asyncio
import logging
import re

from collections.abc import Iterable, Iterator
from pathlib import Path


logger = logging.getLogger(__name__)

_REGEX_CACHE: dict[str, re.Pattern[str]] = {}


def get_compiled_regex(pattern: str, flags: int = 0) -> re.Pattern[str]:
    """Get a cached compiled regex pattern to avoid recompilation overhead."""
    cache_key = f"{pattern}:{flags}"
    if cache_key not in _REGEX_CACHE:
        try:
            _REGEX_CACHE[cache_key] = re.compile(pattern, flags)
        except re.error as e:
            logger.warning("Invalid regex pattern '%s': %s", pattern, e)
            raise
    return _REGEX_CACHE[cache_key]


def read_file_safe(file_path: Path, max_size: int = 1_000_000) -> str | None:
    """Safely read a file, handling encoding errors and size limits.
    Returns None if the file is too large or unreadable.
    """
    try:
        if file_path.stat().st_size > max_size:
            return None
        return file_path.read_text(encoding="utf-8", errors="ignore")
    except (OSError, UnicodeDecodeError) as e:
        logger.debug("Failed to read %s: %s", file_path, e)
        return None


async def read_file_safe_async(file_path: Path, max_size: int = 1_000_000) -> str | None:
    """Async version of read_file_safe to prevent blocking the event loop."""
    try:
        stat = await asyncio.to_thread(file_path.stat)
        if stat.st_size > max_size:
            return None
        return await asyncio.to_thread(file_path.read_text, encoding="utf-8", errors="ignore")
    except (OSError, UnicodeDecodeError) as e:
        logger.debug("Failed to read %s: %s", file_path, e)
        return None


def iter_scannable_files(
    scan_path: Path,
    ignore_dirs: Iterable[str],
    ignore_extensions: Iterable[str],
    scan_extensions: Iterable[str] | None = None,
) -> Iterator[Path]:
    """Efficiently iterate over scannable files, skipping ignored directories and extensions."""
    ignore_dirs_set = set(ignore_dirs)
    ignore_exts_set = set(ignore_extensions)
    scan_exts_set = set(scan_extensions) if scan_extensions else None

    for file_path in scan_path.rglob("*"):
        if not file_path.is_file():
            continue

        if any(part in ignore_dirs_set for part in file_path.parts):
            continue

        if file_path.suffix in ignore_exts_set:
            continue

        if scan_exts_set and file_path.suffix not in scan_exts_set:
            continue

        if ".min." in file_path.name:
            continue

        yield file_path
