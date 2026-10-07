from __future__ import annotations

import ast
import importlib
import re
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum, StrEnum
from pathlib import Path
from types import ModuleType
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel

MODULES = [
    "seraph.core.contracts",
    "seraph.core.types",
    "seraph.evidence.acquisition",
    "seraph.evidence.licensing",
    "seraph.evidence.models",
    "seraph.evidence.normalization",
    "seraph.evidence.provenance",
    "seraph.evidence.quality",
    "seraph.evidence.registry",
    "seraph.evidence.selectors",
    "seraph.ontology.assertions",
    "seraph.ontology.capabilities",
    "seraph.ontology.entities",
    "seraph.ontology.events",
    "seraph.ontology.flows",
    "seraph.ontology.relations",
    "seraph.ontology.schema",
    "seraph.ontology.services",
    "seraph.ontology.world",
    "seraph.temporal.granularity",
    "seraph.temporal.index",
    "seraph.temporal.intervals",
    "seraph.temporal.models",
    "seraph.temporal.parsing",
    "seraph.temporal.query",
    "seraph.temporal.relations",
    "seraph.temporal.schema",
    "seraph.temporal.snapshot",
    "seraph.temporal.timeline",
    "seraph.temporal.versioning",
    "seraph.spatial.models",
    "seraph.spatial.query",
    "seraph.scenarios.models",
    "seraph.scenarios.shocks",
    "seraph.propagation.models",
    "seraph.continuity.models",
    "seraph.counterfactual.models",
    "seraph.uncertainty.models",
    "seraph.governance.assurance",
    "seraph.governance.claims",
    "seraph.governance.policy",
    "seraph.economics.models",
    "seraph.sources.base",
    "seraph.sources.repository_security.models",
]


def _namespace(modules: list[ModuleType]) -> dict[str, object]:
    namespace: dict[str, object] = {
        "Any": Any,
        "Literal": Literal,
        "Self": Self,
        "UTC": UTC,
        "date": date,
        "datetime": datetime,
        "time": time,
        "timedelta": timedelta,
        "Path": Path,
        "BaseModel": BaseModel,
        "Decimal": Decimal,
        "UUID": UUID,
        "Enum": Enum,
        "StrEnum": StrEnum,
        "Callable": Callable,
        "Iterable": Iterable,
        "Mapping": Mapping,
        "Sequence": Sequence,
    }
    for module in modules:
        namespace.update(vars(module))
    for name, module in tuple(sys.modules.items()):
        if name.startswith("seraph.") and isinstance(module, ModuleType):
            namespace.update(vars(module))
    return namespace


def _model_classes(modules: list[ModuleType]) -> list[type[BaseModel]]:
    found: dict[tuple[str, str], type[BaseModel]] = {}
    for module in modules:
        for value in vars(module).values():
            if isinstance(value, type) and issubclass(value, BaseModel) and value is not BaseModel:
                found[(value.__module__, value.__qualname__)] = value
    return sorted(found.values(), key=lambda cls: (cls.__module__, cls.__qualname__))


def _extract_missing(exc: Exception) -> str | None:
    match = re.search(r"name '([^']+)' is not defined", str(exc))
    return None if match is None else match.group(1)


def _source_modules(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).with_suffix("")
        parts = rel.parts[:-1] if rel.name == "__init__" else rel.parts
        module_name = "seraph" if not parts else "seraph." + ".".join(parts)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError):
            continue
        for node in tree.body:
            names: list[str] = []
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                names.append(node.name)
            elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                names.extend(target.id for target in targets if isinstance(target, ast.Name))
            for name in names:
                result.setdefault(name, module_name)
    return result


def _import_owner(name: str, source_index: dict[str, str], modules: list[ModuleType]) -> bool:
    owner = source_index.get(name)
    if owner is None:
        return False
    try:
        module = importlib.import_module(owner)
    except Exception:
        return False
    if module not in modules:
        modules.append(module)
    return hasattr(module, name)


def rebuild_all_models() -> None:
    loaded: list[ModuleType] = []
    errors: dict[tuple[str, str], Exception] = {}

    for module_name in MODULES:
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            errors[(module_name, "<import>")] = exc
            continue
        loaded.append(module)

    source_root = Path(__file__).resolve().parent
    source_index = _source_modules(source_root)

    pending_discoveries: set[str] = set()
    for _pass in range(12):
        namespace = _namespace(loaded)
        models = _model_classes(loaded)
        unresolved: list[tuple[type[BaseModel], Exception]] = []
        discovered = False

        for model in models:
            try:
                model.model_rebuild(
                    force=True,
                    raise_errors=True,
                    _types_namespace=namespace,
                )
            except Exception as exc:
                unresolved.append((model, exc))
                missing = _extract_missing(exc)
                if missing and missing not in pending_discoveries:
                    pending_discoveries.add(missing)
                    if _import_owner(missing, source_index, loaded):
                        discovered = True

        if not unresolved:
            return
        if not discovered:
            namespace = _namespace(loaded)
            final_unresolved: list[tuple[type[BaseModel], Exception]] = []
            for model, _ in unresolved:
                try:
                    model.model_rebuild(
                        force=True,
                        raise_errors=True,
                        _types_namespace=namespace,
                    )
                except Exception as exc:
                    final_unresolved.append((model, exc))
            if not final_unresolved:
                return
            details = "\n".join(
                f"- {model.__module__}.{model.__qualname__}: {type(exc).__name__}: {exc}"
                for model, exc in final_unresolved
            )
            optional_imports = "\n".join(
                f"- {name}: {type(exc).__name__}: {exc}"
                for (name, marker), exc in sorted(errors.items())
                if marker == "<import>"
            )
            suffix = (
                f"\nOptional module import failures:\n{optional_imports}"
                if optional_imports
                else ""
            )
            raise RuntimeError(
                f"Pydantic model rebuild did not converge.\nUnresolved models:\n{details}{suffix}"
            ) from final_unresolved[0][1]
