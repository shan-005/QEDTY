"""seraph.ufic.semantics — v2.0.1 Semantic & Causal Context Engine

Fixes in v2.0.1:
- Added apply_to_finding() helper to wire conformal fields into Finding objects.
- Conformal priors are now properly bounded [0,1].
- Causal annotations include blast_radius_score for scheduler consumption.
"""

from __future__ import annotations

import logging
import re

from dataclasses import dataclass, field
from typing import Any


logger = logging.getLogger("seraph.ufic.semantics")


@dataclass
class SemanticAdjustment:
    blast_radius_multiplier: float = 1.0
    reason: str = ""
    confidence_interval: tuple[float, float] = (0.0, 1.0)
    confidence_level: float = 0.95
    causal_impact: dict[str, Any] = field(default_factory=dict)
    recommended_action: str = "none"

    def to_ontology_action(self, finding_id: str) -> dict[str, Any]:
        return {
            "id": f"action:semantic:{finding_id}",
            "type": "SemanticAction",
            "attributes": {
                "blast_radius_multiplier": self.blast_radius_multiplier,
                "reason": self.reason,
                "confidence_interval": self.confidence_interval,
                "causal_impact": self.causal_impact,
                "recommended_action": self.recommended_action,
            },
        }

    def apply_to_finding(self, finding: Any) -> None:
        """v2.0.1 FIX: Wire conformal and semantic fields into a Finding object.

        The CLI expects:
          finding.conformal_lower
          finding.conformal_upper
          finding.blast_radius (dict with blast_radius_score)
          finding.causal_rank
        """
        lower, upper = self.confidence_interval
        # Ensure bounds
        lower = max(0.0, min(1.0, lower))
        upper = max(0.0, min(1.0, upper))

        try:
            finding.conformal_lower = lower
            finding.conformal_upper = upper
        except (AttributeError, TypeError):
            # Frozen dataclass — use object.__setattr__
            object.__setattr__(finding, "conformal_lower", lower)
            object.__setattr__(finding, "conformal_upper", upper)

        # Merge blast radius if present
        existing_blast = getattr(finding, "blast_radius", None)
        if existing_blast is None:
            blast = {
                "blast_radius_score": int(self.blast_radius_multiplier * 100),
                "reason": self.reason,
                "causal_impact": self.causal_impact,
            }
            try:
                finding.blast_radius = blast
            except (AttributeError, TypeError):
                object.__setattr__(finding, "blast_radius", blast)
        elif isinstance(existing_blast, dict):
            existing_blast["blast_radius_score"] = int(self.blast_radius_multiplier * 100)
            existing_blast["semantic_reason"] = self.reason

        # Set causal rank hint if action is escalate
        if self.recommended_action == "escalate":
            try:
                finding.causal_rank = 1
            except (AttributeError, TypeError):
                object.__setattr__(finding, "causal_rank", 1)


SEMANTIC_RULES: dict[str, dict[str, dict[str, Any]]] = {
    "exec": {
        "java": {
            "action": "suppress",
            "reason": "Java Runtime.exec is process spawning, not code injection",
            "conformal_prior": (0.02, 0.08),
            "causal_annotation": "process_spawn_not_injection",
        },
        "go": {
            "action": "suppress",
            "reason": "Go os/exec is process spawning",
            "conformal_prior": (0.01, 0.05),
            "causal_annotation": "process_spawn_not_injection",
        },
        "python": {
            "framework_exceptions": ["ansible", "airflow"],
            "conformal_prior": (0.10, 0.35),
            "causal_annotation": "framework_may_justify",
        },
        "javascript": {
            "intent_exceptions": ["build_script", "development_environment"],
            "conformal_prior": (0.05, 0.20),
            "causal_annotation": "dev_context_lowers_risk",
        },
    },
    "eval": {
        "python": {
            "framework_exceptions": ["airflow"],
            "conformal_prior": (0.15, 0.45),
            "causal_annotation": "framework_may_justify",
        },
        "javascript": {
            "intent_exceptions": ["build_script"],
            "conformal_prior": (0.10, 0.30),
            "causal_annotation": "dev_context_lowers_risk",
        },
    },
    "__import__": {
        "python": {
            "path_exceptions": [r"__init__\.py$"],
            "conformal_prior": (0.01, 0.10),
            "causal_annotation": "lazy_loading_standard",
        }
    },
    "child_process": {
        "javascript": {
            "intent_exceptions": ["build_script", "development_environment", "test"],
            "conformal_prior": (0.05, 0.18),
            "causal_annotation": "dev_context_lowers_risk",
        }
    },
    "innerHTML": {
        "javascript": {
            "intent_exceptions": ["test", "documentation", "build_script"],
            "conformal_prior": (0.08, 0.25),
            "causal_annotation": "dev_context_lowers_risk",
        }
    },
    "dangerouslySetInnerHTML": {
        "javascript": {
            "intent_exceptions": ["test", "documentation", "build_script"],
            "conformal_prior": (0.20, 0.50),
            "causal_annotation": "react_explicit_danger",
        }
    },
    "sql_injection": {
        "python": {
            "framework_exceptions": ["django", "sqlalchemy"],
            "conformal_prior": (0.60, 0.95),
            "causal_annotation": "direct_sql_high_risk",
        },
        "java": {
            "framework_exceptions": ["spring-boot"],
            "conformal_prior": (0.55, 0.90),
            "causal_annotation": "direct_sql_high_risk",
        },
        "javascript": {
            "conformal_prior": (0.50, 0.88),
            "causal_annotation": "direct_sql_high_risk",
        },
    },
    "hardcoded_secret": {
        "_global": {
            "conformal_prior": (0.70, 0.99),
            "causal_annotation": "credential_exposure_critical",
        }
    },
    "missing_auth": {
        "_global": {
            "conformal_prior": (0.65, 0.95),
            "causal_annotation": "absence_of_control_high_impact",
        }
    },
    "missing_rls": {
        "_global": {
            "conformal_prior": (0.55, 0.90),
            "causal_annotation": "absence_of_control_high_impact",
        }
    },
}

CREDENTIAL_SUPPRESSIONS = [
    r"test",
    r"mock",
    r"example",
    r"docs?/",
    r"testhelper",
    r"docker-compose",
    r"\.env\.example",
    r"fixture",
    r"stub",
    r"fake",
    r"sample",
    r"_test\.",
    r"\.spec\.",
    r"\.stories\.",
    r"storybook",
]


class SemanticEngine:
    def __init__(self, ontology: Any | None = None) -> None:
        self.ontology = ontology
        self.credential_patterns = [re.compile(p, re.IGNORECASE) for p in CREDENTIAL_SUPPRESSIONS]

    def evaluate(
        self,
        finding_id: str,
        rule_id: str,
        language: str,
        file_path: str,
        context: str = "",
        topology: dict[str, Any] | None = None,
    ) -> SemanticAdjustment:
        adjustment = SemanticAdjustment()
        path_lower = file_path.lower()
        context_lower = context.lower()

        # 1. Credential / Secret Context
        if self._is_credential_rule(rule_id):
            cred_adj = self._evaluate_credential_context(path_lower, context_lower)
            if cred_adj.blast_radius_multiplier < 1.0:
                return cred_adj

        # 2. Language Semantic Rules
        semantic_adj = self._evaluate_semantic_rules(
            rule_id, language, path_lower, context_lower, topology
        )
        if semantic_adj.blast_radius_multiplier < 1.0 or semantic_adj.reason:
            adjustment = semantic_adj

        # 3. Topology-aware causal adjustment
        if topology:
            causal_adj = self._apply_topology_causality(rule_id, file_path, topology)
            if causal_adj.blast_radius_multiplier < adjustment.blast_radius_multiplier:
                adjustment.blast_radius_multiplier = causal_adj.blast_radius_multiplier
                adjustment.reason = f"{adjustment.reason}; {causal_adj.reason}".strip("; ")
                adjustment.causal_impact.update(causal_adj.causal_impact)

        # 4. Calibrate conformal interval
        adjustment.confidence_interval = self._calibrate_confidence(
            rule_id, language, adjustment.blast_radius_multiplier, adjustment.reason
        )

        # 5. Determine recommended action
        adjustment.recommended_action = self._action_from_multiplier(
            adjustment.blast_radius_multiplier
        )

        # 6. Write to ontology if available
        if self.ontology is not None:
            self._write_to_ontology(finding_id, adjustment)

        return adjustment

    def get_semantic_adjustment(
        self, rule_id: str, language: str, file_path: str, context: str = ""
    ) -> dict[str, Any]:
        adj = self.evaluate(
            finding_id=f"legacy:{rule_id}",
            rule_id=rule_id,
            language=language,
            file_path=file_path,
            context=context,
        )
        return {
            "blast_radius_multiplier": adj.blast_radius_multiplier,
            "reason": adj.reason,
            "confidence_interval": adj.confidence_interval,
            "causal_impact": adj.causal_impact,
            "recommended_action": adj.recommended_action,
        }

    def _is_credential_rule(self, rule_id: str) -> bool:
        rid = rule_id.lower()
        return any(
            k in rid
            for k in ("secret", "credential", "password", "token", "api_key", "private_key")
        )

    def _evaluate_credential_context(
        self, path_lower: str, context_lower: str
    ) -> SemanticAdjustment:
        for pat in self.credential_patterns:
            if pat.search(path_lower) or pat.search(context_lower):
                return SemanticAdjustment(
                    blast_radius_multiplier=0.05,
                    reason="Test/mock credential context",
                    confidence_interval=(0.01, 0.12),
                    confidence_level=0.95,
                    causal_impact={
                        "exploit_path": "none",
                        "blast_radius_reduction": 0.95,
                        "reason": "credential_in_test_context",
                    },
                    recommended_action="suppress",
                )
        return SemanticAdjustment()

    def _evaluate_semantic_rules(
        self,
        rule_id: str,
        language: str,
        path_lower: str,
        context_lower: str,
        topology: dict[str, Any] | None,
    ) -> SemanticAdjustment:
        rule_key = rule_id.lower()
        for key, lang_map in SEMANTIC_RULES.items():
            if key not in rule_key:
                continue

            lang_rules = lang_map.get(language, lang_map.get("_global", {}))
            if not lang_rules:
                continue

            prior = lang_rules.get("conformal_prior", (0.0, 1.0))
            causal_ann = lang_rules.get("causal_annotation", "")

            if lang_rules.get("action") == "suppress":
                return SemanticAdjustment(
                    blast_radius_multiplier=0.0,
                    reason=lang_rules.get("reason", "Semantic suppression"),
                    confidence_interval=prior,
                    causal_impact={"exploit_path": "none", "annotation": causal_ann},
                    recommended_action="suppress",
                )

            for fw in lang_rules.get("framework_exceptions", []):
                if fw in path_lower or fw in context_lower:
                    return SemanticAdjustment(
                        blast_radius_multiplier=0.1,
                        reason=f"Framework exception: {fw}",
                        confidence_interval=(max(0.0, prior[0] * 0.5), min(1.0, prior[1] * 0.5)),
                        causal_impact={"framework_justification": fw, "annotation": causal_ann},
                        recommended_action="suppress",
                    )

            for intent in lang_rules.get("intent_exceptions", []):
                if intent in path_lower or intent in context_lower:
                    return SemanticAdjustment(
                        blast_radius_multiplier=0.2,
                        reason=f"Intent exception: {intent}",
                        confidence_interval=(max(0.0, prior[0] * 0.6), min(1.0, prior[1] * 0.6)),
                        causal_impact={"intent_context": intent, "annotation": causal_ann},
                        recommended_action="investigate",
                    )

            for path_pat in lang_rules.get("path_exceptions", []):
                if re.search(path_pat, path_lower):
                    return SemanticAdjustment(
                        blast_radius_multiplier=0.1,
                        reason=f"Path exception: {path_pat}",
                        confidence_interval=(max(0.0, prior[0] * 0.4), min(1.0, prior[1] * 0.4)),
                        causal_impact={"path_justification": path_pat, "annotation": causal_ann},
                        recommended_action="suppress",
                    )

        return SemanticAdjustment()

    def _apply_topology_causality(
        self, rule_id: str, file_path: str, topology: dict[str, Any]
    ) -> SemanticAdjustment:
        boundaries = topology.get("boundaries", [])
        api_surface = topology.get("api_surface", [])
        adj = SemanticAdjustment()

        auth_boundaries = [b for b in boundaries if b.get("boundary_type") == "auth"]
        if auth_boundaries:
            auth_files = set()
            for b in auth_boundaries:
                auth_files.update(b.get("entry_points", []))
            if any(str(a).lower() in file_path.lower() for a in auth_files) and (
                "auth" in rule_id.lower() or "secret" in rule_id.lower()
            ):
                adj.blast_radius_multiplier = 1.5
                adj.reason = "Finding in auth boundary — cascade risk"
                adj.causal_impact = {
                    "boundary_compromise": True,
                    "cascade_probability": 0.85,
                    "affected_routes": "all",
                }
                return adj

        for api in api_surface:
            if (
                api.get("file", "").lower() in file_path.lower()
                and "missing_auth" in rule_id.lower()
            ):
                adj.blast_radius_multiplier = 1.3
                adj.reason = "Public API endpoint lacks auth — direct exposure"
                adj.causal_impact = {
                    "exposure": "public",
                    "cascade_probability": 0.70,
                    "affected_routes": api.get("file"),
                }
                return adj

        if auth_boundaries and "missing_auth" not in rule_id.lower():
            adj.blast_radius_multiplier = 0.85
            adj.reason = "Behind auth boundary — reduced exploitability"
            adj.causal_impact = {"exposure": "authenticated", "cascade_probability": 0.30}

        return adj

    def _calibrate_confidence(
        self, rule_id: str, language: str, multiplier: float, reason: str
    ) -> tuple[float, float]:
        lower, upper = 0.0, 1.0
        for key, lang_map in SEMANTIC_RULES.items():
            if key in rule_id.lower():
                lang_rules = lang_map.get(language, lang_map.get("_global", {}))
                prior = lang_rules.get("conformal_prior")
                if prior:
                    lower, upper = prior
                    break

        if multiplier == 0.0:
            return (max(0.0, lower), min(1.0, upper * 0.3))
        elif multiplier <= 0.1:
            return (max(0.0, lower), min(1.0, upper * 0.5))
        elif multiplier <= 0.3:
            return (max(0.0, lower + 0.05), min(1.0, upper * 0.7))
        elif multiplier >= 1.2:
            return (max(0.0, lower + 0.75), 1.0)
        else:
            return (max(0.0, lower), min(1.0, upper))

    def _action_from_multiplier(self, multiplier: float) -> str:
        if multiplier == 0.0:
            return "suppress"
        elif multiplier <= 0.2:
            return "investigate"
        elif multiplier >= 1.2:
            return "escalate"
        else:
            return "none"

    def _write_to_ontology(self, finding_id: str, adjustment: SemanticAdjustment) -> None:
        if self.ontology is None:
            return
        ont = self.ontology
        action_obj = adjustment.to_ontology_action(finding_id)
        if hasattr(ont, "add_object"):
            ont.add_object(action_obj)
        if hasattr(ont, "add_link"):
            ont.add_link(
                {
                    "source": finding_id,
                    "target": action_obj["id"],
                    "relation": "has_semantic_action",
                    "confidence": adjustment.confidence_interval[1],
                }
            )
