import json

from typing import Any


class JsonFormatter:
    """Serialize scan results to JSON."""

    def __init__(self, indent: int = 2):
        self.indent = indent

    def format(self, scan_result: dict[str, Any]) -> str:
        """Return a JSON string from the scan result dict."""
        # Ensure no NaN / Infinity (JSON spec does not allow them)
        clean = self._sanitize(scan_result)
        return json.dumps(clean, indent=self.indent, ensure_ascii=False, default=str)

    def _sanitize(self, obj: Any) -> Any:
        """Recursively replace NaN/Inf with None and ensure serializability."""
        import math

        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        if isinstance(obj, dict):
            return {k: self._sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._sanitize(v) for v in obj]
        return obj

    def write(self, scan_result: dict[str, Any], path: str) -> None:
        """Write JSON directly to a file."""
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.format(scan_result))
