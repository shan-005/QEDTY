"""Privacy-safe local adaptive learning for Seraph Guard.

The learning engine is subordinate to scanner truth and impact analysis. It may
suppress a finding only from previously observed user/team behavior; it never
manufactures impact evidence, changes blast-radius assessment, or claims a
calibrated probability. The canonical persisted file is ``cache.json`` so the
PatternScanner can consume the same learned suppression state.

The implementation keeps Seraph's historical public methods while hardening
migration, bounded growth, atomic persistence, and privacy-safe team export.
No formal differential-privacy (epsilon, delta) guarantee is claimed.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import tempfile
import time

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast


STATE_VERSION = 3
_MAX_PATTERNS = 10_000
_MAX_EVENTS = 50_000
_PATTERN_EXPIRY_SECONDS = 90 * 86400


def _to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _severity(value: Any) -> str:
    raw = getattr(value, "value", value)
    text = str(raw or "info").strip().lower()
    return text if text in {"critical", "high", "medium", "low", "info"} else "info"


def _category(value: Any) -> str:
    raw = getattr(value, "value", value)
    return str(raw or "unknown").strip().lower() or "unknown"


def _norm_path(value: Any) -> str:
    text = str(value or "").replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text.strip("/")


def _finding_meta(finding: Any) -> dict[str, Any]:
    if isinstance(finding, dict):
        meta = finding.get("metadata")
    else:
        meta = getattr(finding, "metadata", {})
    return dict(meta) if isinstance(meta, dict) else {}


def _finding_data(finding: Any) -> dict[str, str]:
    meta = _finding_meta(finding)
    if isinstance(finding, dict):
        return {
            "category": _category(finding.get("category")),
            "title": str(finding.get("title") or finding.get("rule_name") or "unknown"),
            "rule_id": str(finding.get("rule_id") or finding.get("id") or "unknown"),
            "file": _norm_path(finding.get("file") or finding.get("path")),
            "severity": _severity(finding.get("severity")),
            "pattern": str(meta.get("pattern") or finding.get("pattern") or ""),
        }
    return {
        "category": _category(getattr(finding, "category", "unknown")),
        "title": str(
            getattr(finding, "title", "") or getattr(finding, "rule_name", "") or "unknown"
        ),
        "rule_id": str(getattr(finding, "rule_id", "") or getattr(finding, "id", "") or "unknown"),
        "file": _norm_path(getattr(finding, "file", "") or getattr(finding, "path", "")),
        "severity": _severity(getattr(finding, "severity", "info")),
        "pattern": str(meta.get("pattern", "")),
    }


def _pattern_key(finding: Any) -> str:
    data = _finding_data(finding)
    if data["pattern"] and data["file"]:
        # Exact compatibility with PatternScanner._make_learning_key().
        return hashlib.sha256(f"{data['pattern']}:{data['file']}".encode()).hexdigest()[:16]
    semantic = "|".join((data["category"], data["rule_id"], data["title"].lower()))
    return hashlib.sha256(semantic.encode("utf-8")).hexdigest()


def _legacy_key(finding: Any) -> str:
    data = _finding_data(finding)
    return f"{data['category']}.{data['title']}"


def _is_test_file(file_path: str) -> bool:
    lower = _norm_path(file_path).lower()
    parts = set(lower.split("/"))
    name = Path(lower).name
    return (
        "tests" in parts
        or "test" in parts
        or "__tests__" in parts
        or "e2e" in parts
        or name.startswith("test_")
        or name.endswith(("_test.py", "_test.go"))
        or ".test." in name
        or ".spec." in name
    )


def _atomic_json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        Path(temp_name).replace(path)
    finally:
        try:
            Path(temp_name).unlink()
        except FileNotFoundError:
            pass


class AdaptiveLearningEngine:
    """Aggregate-only adaptive suppression/history engine."""

    def __init__(
        self,
        cache_dir: Path | str = Path(".seraph-learn"),
        *,
        suppression_threshold: float = 0.90,
        min_observations_for_auto_action: int = 5,
    ) -> None:
        threshold_message = "suppression_threshold must be in (0, 1]"
        if not 0.0 < float(suppression_threshold) <= 1.0:
            raise ValueError(threshold_message)

        self.cache_dir = Path(cache_dir)
        self.cache_file = self.cache_dir / "cache.json"
        # Historical callers may reference either name.
        self.state_path = self.cache_file
        self.state_file = self.cache_file
        self.auto_policies_file = self.cache_dir / "auto-policies.yml"
        self.suppression_threshold = float(suppression_threshold)
        self.min_observations_for_auto_action = max(1, int(min_observations_for_auto_action))

        # Compatibility attribute retained for older callers/tests.
        self._ufic_available: bool | None = None
        self._ufic_checked = False
        self._ufic_classifier_cls: Any | None = None

        self._dirty = False
        self._last_save = 0.0
        self.state = self._load()

    @staticmethod
    def _default_state() -> dict[str, Any]:
        return {
            "version": STATE_VERSION,
            "patterns": {},
            "pattern_suppressions": {},
            "team_sync": {},
            "team_behavior": {
                "mean_time_to_fix_hours": 0.0,
                "fix_rate_by_severity": {},
                "total_findings_seen": 0,
                "total_findings_fixed": 0,
                "total_findings_suppressed": 0,
            },
            "suppressions": [],
            "fixes": [],
            "fix_events": [],
            "updated_at": None,
        }

    def _load(self) -> dict[str, Any]:
        if not self.cache_file.exists():
            return self._default_state()
        try:
            data = json.loads(self.cache_file.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return self._default_state()
        if not isinstance(data, dict):
            return self._default_state()
        return self._migrate(data)

    @classmethod
    def _migrate(cls, data: dict[str, Any]) -> dict[str, Any]:
        state = cls._default_state()
        patterns = data.get("patterns", {})
        if isinstance(patterns, dict):
            for key, entry in patterns.items():
                if not isinstance(entry, dict):
                    continue
                state["patterns"][str(key)] = {
                    "suppressed_count": max(
                        0,
                        _to_int(entry.get("suppressed_count", entry.get("suppressed", 0))),
                    ),
                    "fixed_count": max(
                        0,
                        _to_int(entry.get("fixed_count", entry.get("fixed", 0))),
                    ),
                    "seen_count": max(
                        0,
                        _to_int(entry.get("seen_count", entry.get("seen", 0))),
                    ),
                    "first_seen": entry.get("first_seen"),
                    "last_seen": entry.get("last_seen"),
                    "confidence": max(
                        0.0,
                        min(
                            1.0,
                            _to_float(
                                entry.get(
                                    "confidence",
                                    entry.get("suppression_propensity", 0.0),
                                ),
                                0.0,
                            ),
                        ),
                    ),
                    "auto_action": str(entry.get("auto_action", "none")),
                    "sample_file": "",
                }

        pattern_suppressions = data.get("pattern_suppressions", {})
        if isinstance(pattern_suppressions, dict):
            for key, entry in pattern_suppressions.items():
                if isinstance(entry, dict) and entry.get("status") == "suppressed":
                    state["pattern_suppressions"][str(key)] = {
                        "status": "suppressed",
                        "confidence": max(
                            0.0,
                            min(1.0, _to_float(entry.get("confidence", 0.0), 0.0)),
                        ),
                    }

        behavior = data.get("team_behavior", {})
        if isinstance(behavior, dict):
            state["team_behavior"].update(
                {
                    "mean_time_to_fix_hours": max(
                        0.0,
                        _to_float(behavior.get("mean_time_to_fix_hours", 0.0), 0.0),
                    ),
                    "fix_rate_by_severity": (
                        behavior.get("fix_rate_by_severity", {})
                        if isinstance(behavior.get("fix_rate_by_severity", {}), dict)
                        else {}
                    ),
                    "total_findings_seen": max(
                        0,
                        _to_int(behavior.get("total_findings_seen", 0)),
                    ),
                    "total_findings_fixed": max(
                        0,
                        _to_int(behavior.get("total_findings_fixed", 0)),
                    ),
                    "total_findings_suppressed": max(
                        0,
                        _to_int(behavior.get("total_findings_suppressed", 0)),
                    ),
                }
            )

        for key in ("team_sync", "suppressions", "fixes", "fix_events"):
            value = data.get(key)
            if isinstance(value, type(state[key])):
                state[key] = value

        state["updated_at"] = data.get("updated_at")
        return state

    def _trim_state(self) -> None:
        now = time.time()
        patterns = self.state.get("patterns", {})
        if not isinstance(patterns, dict):
            patterns = {}
            self.state["patterns"] = patterns

        for key in list(patterns):
            entry = patterns[key]
            if not isinstance(entry, dict):
                del patterns[key]
                continue
            last = _to_float(entry.get("last_seen"), 0.0)
            if last and now - last > _PATTERN_EXPIRY_SECONDS:
                del patterns[key]

        if len(patterns) > _MAX_PATTERNS:
            ordered = sorted(
                patterns.items(),
                key=lambda item: (
                    _to_float(item[1].get("last_seen"), 0.0) if isinstance(item[1], dict) else 0.0
                ),
                reverse=True,
            )
            self.state["patterns"] = dict(ordered[:_MAX_PATTERNS])

        self.state["suppressions"] = list(self.state.get("suppressions", []))[-_MAX_EVENTS:]
        self.state["fixes"] = list(self.state.get("fixes", []))[-_MAX_EVENTS:]
        self.state["fix_events"] = list(self.state.get("fix_events", []))[-_MAX_EVENTS:]

    def save(self, force: bool = False) -> None:
        if not force and not self._dirty:
            return
        now = time.monotonic()
        if not force and now - self._last_save < 5.0:
            return
        self._trim_state()
        self.state["version"] = STATE_VERSION
        self.state["updated_at"] = datetime.now(UTC).isoformat()
        _atomic_json_write(self.cache_file, self.state)
        self._dirty = False
        self._last_save = now

    def _ensure_pattern(self, key: str) -> dict[str, Any]:
        existing = self.state["patterns"].get(key)
        if isinstance(existing, dict):
            return cast("dict[str, Any]", existing)

        now = time.time()
        entry: dict[str, Any] = {
            "suppressed_count": 0,
            "fixed_count": 0,
            "seen_count": 0,
            "first_seen": now,
            "last_seen": now,
            "confidence": 0.0,
            "auto_action": "none",
            "sample_file": "",
        }
        self.state["patterns"][key] = entry
        return entry

    def _refresh_pattern(self, entry: dict[str, Any]) -> None:
        suppressed = max(0, _to_int(entry.get("suppressed_count", 0)))
        fixed = max(0, _to_int(entry.get("fixed_count", 0)))
        total_decisions = suppressed + fixed
        denominator = max(1, total_decisions)
        confidence = suppressed / denominator
        entry["confidence"] = round(max(0.0, min(1.0, confidence)), 6)
        if (
            total_decisions >= self.min_observations_for_auto_action
            and confidence >= self.suppression_threshold
        ):
            entry["auto_action"] = "allow"
        elif (
            total_decisions >= self.min_observations_for_auto_action
            and _is_test_file(str(entry.get("sample_file", "")))
            and confidence >= 0.75
        ):
            entry["auto_action"] = "allow_in_test_files"
        else:
            entry["auto_action"] = "none"

    def _record_seen(self, finding: Any) -> None:
        data = _finding_data(finding)
        entry = self._ensure_pattern(_pattern_key(finding))
        now = time.time()
        entry["seen_count"] = max(0, _to_int(entry.get("seen_count", 0))) + 1
        entry["last_seen"] = now
        if not entry.get("sample_file") and _is_test_file(data["file"]):
            entry["sample_file"] = data["file"]

        behavior = self.state["team_behavior"]
        behavior["total_findings_seen"] = (
            max(0, _to_int(behavior.get("total_findings_seen", 0))) + 1
        )

        rates = behavior.setdefault("fix_rate_by_severity", {})
        bucket = rates.setdefault(data["severity"], {"fixed": 0, "total": 0})
        bucket["total"] = max(0, _to_int(bucket.get("total", 0))) + 1

        self._refresh_pattern(entry)
        self._dirty = True

    def record_finding(self, finding: Any) -> None:
        self._record_seen(finding)
        self.save()

    def record_findings(self, findings: list[Any]) -> None:
        for finding in findings:
            self._record_seen(finding)
        self.save()

    def record_suppression(self, finding: Any, reason: str = "manual") -> None:
        data = _finding_data(finding)
        key = _pattern_key(finding)
        entry = self._ensure_pattern(key)
        entry["suppressed_count"] = max(0, _to_int(entry.get("suppressed_count", 0))) + 1
        entry["last_seen"] = time.time()
        if data["file"]:
            entry["sample_file"] = data["file"]

        self._refresh_pattern(entry)

        behavior = self.state["team_behavior"]
        behavior["total_findings_suppressed"] = (
            max(0, _to_int(behavior.get("total_findings_suppressed", 0))) + 1
        )

        self.state["suppressions"].append(
            {
                "pattern_hash": hashlib.sha256(key.encode("utf-8")).hexdigest(),
                "reason": str(reason)[:200],
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

        if data["pattern"] and entry["auto_action"] == "allow":
            self.state["pattern_suppressions"][key] = {
                "status": "suppressed",
                "confidence": entry["confidence"],
            }

        self._dirty = True
        self.save(force=True)

    def record_fix(self, finding: Any, fix_duration_hours: float = 0.0) -> None:
        data = _finding_data(finding)
        key = _pattern_key(finding)
        entry = self._ensure_pattern(key)
        entry["fixed_count"] = max(0, _to_int(entry.get("fixed_count", 0))) + 1
        entry["last_seen"] = time.time()
        self._refresh_pattern(entry)

        behavior = self.state["team_behavior"]
        behavior["total_findings_fixed"] = (
            max(0, _to_int(behavior.get("total_findings_fixed", 0))) + 1
        )

        rates = behavior.setdefault("fix_rate_by_severity", {})
        bucket = rates.setdefault(data["severity"], {"fixed": 0, "total": 0})
        bucket["fixed"] = max(0, _to_int(bucket.get("fixed", 0))) + 1

        duration = max(0.0, _to_float(fix_duration_hours, 0.0))
        if duration > 0:
            total = max(1, _to_int(behavior.get("total_findings_fixed", 1)))
            old_mean = _to_float(behavior.get("mean_time_to_fix_hours", 0.0), 0.0)
            behavior["mean_time_to_fix_hours"] = round(
                ((old_mean * (total - 1)) + duration) / total,
                4,
            )

        self.state["fixes"].append(
            {
                "pattern_hash": hashlib.sha256(key.encode("utf-8")).hexdigest(),
                "duration_hours": duration,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

        self._dirty = True
        self.save(force=True)

    def _ufic_suppresses(self, finding: Any) -> bool:
        if not self._ufic_checked:
            self._ufic_checked = True
            try:
                module = importlib.import_module("seraph.intelligence.ufic.classifier")
                classifier_cls = getattr(module, "UFICClassifier", None)
                self._ufic_classifier_cls = classifier_cls if callable(classifier_cls) else None
            except Exception:
                self._ufic_classifier_cls = None
            self._ufic_available = self._ufic_classifier_cls is not None

        classifier_cls = self._ufic_classifier_cls
        if classifier_cls is None:
            return False

        try:
            return bool(classifier_cls(topology={}).evaluate_finding(finding))
        except Exception:
            return False

    def should_suppress(self, finding: Any) -> tuple[bool, str]:
        if self._ufic_suppresses(finding):
            return True, "UFIC framework-context suppression"

        data = _finding_data(finding)
        key = _pattern_key(finding)
        entry = self._ensure_pattern(key)
        confidence = _to_float(entry.get("confidence", 0.0), 0.0)
        auto_action = str(entry.get("auto_action", "none"))

        if auto_action == "allow" and confidence >= self.suppression_threshold:
            return (
                True,
                f"Auto-suppressed from learned behavior at {confidence:.0%} historical rate",
            )

        if auto_action == "allow_in_test_files" and _is_test_file(data["file"]):
            return True, f"Auto-suppressed in test file at {confidence:.0%} historical rate"

        pattern_states_raw = self.state.get("pattern_suppressions", {})
        if isinstance(pattern_states_raw, dict):
            pattern_states = cast("dict[str, Any]", pattern_states_raw)
            if data["pattern"] and key in pattern_states:
                state_entry = pattern_states.get(key)
                if isinstance(state_entry, dict) and state_entry.get("status") == "suppressed":
                    return True, "Auto-suppressed by PatternScanner learning state"

        return False, ""

    def apply_learning(self, findings: Iterable[Any]) -> list[Any]:
        result: list[Any] = []
        for finding in findings:
            self._record_seen(finding)
            should, reason = self.should_suppress(finding)
            if should:
                if isinstance(finding, dict):
                    finding["is_suppressed"] = True
                    finding["suppression_reason"] = reason
                else:
                    try:
                        object.__setattr__(finding, "is_suppressed", True)
                        object.__setattr__(finding, "suppression_reason", reason)
                    except (AttributeError, TypeError):
                        pass

                behavior = self.state["team_behavior"]
                behavior["total_findings_suppressed"] = (
                    max(0, _to_int(behavior.get("total_findings_suppressed", 0))) + 1
                )
            else:
                result.append(finding)

            data = _finding_data(finding)
            key = _pattern_key(finding)
            entry = self._ensure_pattern(key)

            if isinstance(finding, dict):
                metadata = finding.setdefault("metadata", {})
            else:
                metadata = getattr(finding, "metadata", None)

            if isinstance(metadata, dict):
                learning = metadata.setdefault("learning", {})
                if isinstance(learning, dict):
                    learning.update(
                        {
                            "applied": True,
                            "pattern_hash": hashlib.sha256(key.encode("utf-8")).hexdigest(),
                            "observation_count": _to_int(entry.get("seen_count", 0)),
                            "suppression_propensity": _to_float(
                                entry.get("confidence", 0.0),
                                0.0,
                            ),
                            "state_version": STATE_VERSION,
                            "formal_dp_guarantee": False,
                        }
                    )

            if data["pattern"] and entry.get("auto_action") == "allow":
                pattern_suppressions_raw = self.state.get("pattern_suppressions", {})
                if not isinstance(pattern_suppressions_raw, dict):
                    pattern_suppressions_raw = {}
                    self.state["pattern_suppressions"] = pattern_suppressions_raw
                pattern_suppressions = cast("dict[str, Any]", pattern_suppressions_raw)
                pattern_suppressions[key] = {
                    "status": "suppressed",
                    "confidence": _to_float(entry.get("confidence", 0.0), 0.0),
                }

        self._dirty = True
        self.save(force=True)
        return result

    def get_team_summary(self) -> dict[str, Any]:
        behavior_raw = self.state.get("team_behavior", {})
        if not isinstance(behavior_raw, dict):
            behavior_raw = {}
        behavior = cast("dict[str, Any]", behavior_raw)

        return {
            "total_findings_seen": max(0, _to_int(behavior.get("total_findings_seen", 0))),
            "total_findings_fixed": max(0, _to_int(behavior.get("total_findings_fixed", 0))),
            "total_findings_suppressed": max(
                0,
                _to_int(behavior.get("total_findings_suppressed", 0)),
            ),
            "mean_time_to_fix_hours": round(
                _to_float(behavior.get("mean_time_to_fix_hours", 0.0), 0.0),
                1,
            ),
            "fix_rate_by_severity": behavior.get("fix_rate_by_severity", {}),
            "learned_patterns": len(self.state.get("patterns", {})),
            "team_sync_patterns": len(self.state.get("team_sync", {})),
        }

    def get_privacy_safe_export(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        patterns_raw = self.state.get("patterns", {})
        if not isinstance(patterns_raw, dict):
            patterns_raw = {}
        patterns = cast("dict[str, Any]", patterns_raw)

        for key, entry in sorted(patterns.items()):
            if not isinstance(entry, dict):
                continue
            result.append(
                {
                    "pattern_hash": hashlib.sha256(str(key).encode("utf-8")).hexdigest(),
                    "seen": max(0, _to_int(entry.get("seen_count", 0))),
                    "fixed": max(0, _to_int(entry.get("fixed_count", 0))),
                    "suppressed": max(0, _to_int(entry.get("suppressed_count", 0))),
                    "confidence": round(
                        _to_float(entry.get("confidence", 0.0), 0.0),
                        6,
                    ),
                    "auto_action": str(entry.get("auto_action", "none")),
                    "schema_version": STATE_VERSION,
                }
            )
        return result

    def merge_team_sync(self, team_data: Any) -> int:
        if isinstance(team_data, dict):
            items: Iterable[Any] = team_data.values()
        elif isinstance(team_data, list):
            items = team_data
        else:
            message = "team sync payload must be a list or object"
            raise TypeError(message)

        team_sync_raw = self.state.get("team_sync", {})
        if not isinstance(team_sync_raw, dict):
            team_sync_raw = {}
            self.state["team_sync"] = team_sync_raw
        team_sync = cast("dict[str, Any]", team_sync_raw)

        merged = 0
        for item in items:
            if not isinstance(item, dict):
                continue

            key = str(item.get("pattern_hash", item.get("hash", ""))).strip().lower()
            if len(key) != 64 or any(ch not in "0123456789abcdef" for ch in key):
                continue

            target_raw = team_sync.setdefault(
                key,
                {"seen": 0, "fixed": 0, "suppressed": 0, "confidence": 0.0},
            )
            if not isinstance(target_raw, dict):
                target_raw = {"seen": 0, "fixed": 0, "suppressed": 0, "confidence": 0.0}
                team_sync[key] = target_raw
            target = cast("dict[str, Any]", target_raw)

            changed = False
            for field in ("seen", "fixed", "suppressed"):
                value = max(0, min(10_000_000, _to_int(item.get(field, 0))))
                if value:
                    target[field] = max(0, _to_int(target.get(field, 0))) + value
                    changed = True

            confidence = max(0.0, min(1.0, _to_float(item.get("confidence", 0.0), 0.0)))
            if confidence > _to_float(target.get("confidence", 0.0), 0.0):
                target["confidence"] = confidence
                changed = True

            if changed:
                merged += 1

        if merged:
            self._dirty = True
            self.save()
        return merged

    @staticmethod
    def _is_test_file(file_path: str) -> bool:
        return _is_test_file(file_path)

    @staticmethod
    def _is_test_file_pattern(files: list[str]) -> bool:
        return bool(files) and sum(1 for item in files if _is_test_file(item)) / len(files) > 0.8


__all__ = ["AdaptiveLearningEngine"]
