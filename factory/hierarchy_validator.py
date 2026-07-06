"""Phase 4 — Hierarchy Validator.

Two classes of check:
  * Structural (pure Python, deterministic): duplicate deliverables, missing deliverables.
  * Judgment (LLM): bonus stronger than core, order bump too valuable, generic content,
    unsupported claims, support-burden creep, promise misalignment.

Each finding carries a severity and a recommended fix. `validate()` aggregates all of
them so the pipeline can block on `blocking` findings before human approval.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from factory.brief import OfferBrief
from factory.llm import LLMClient
from factory.prompts.methodology import brief_context, system_prompt

logger = logging.getLogger("factory.hierarchy")

Severity = str  # "blocking" | "warning" | "info"


@dataclass
class Finding:
    check: str
    severity: Severity
    message: str
    recommended_fix: str = ""


@dataclass
class ValidationResult:
    findings: list[Finding] = field(default_factory=list)

    @property
    def blocking(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "blocking"]

    @property
    def ok(self) -> bool:
        return len(self.blocking) == 0

    def add(self, *findings: Finding) -> None:
        self.findings.extend(findings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "blocking_count": len(self.blocking),
            "findings": [f.__dict__ for f in self.findings],
        }


def _name_of(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("name") or item.get("title") or "").strip()
    return str(item).strip()


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


# --- Structural checks (deterministic) ---------------------------------------

def check_duplicates(core: list[Any], bonuses: list[Any]) -> list[Finding]:
    findings: list[Finding] = []
    names = [(_name_of(x), "core") for x in core] + [(_name_of(x), "bonus") for x in bonuses]
    names = [(n, src) for n, src in names if n]
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            (na, sa), (nb, sb) = names[i], names[j]
            if _similar(na, nb) >= 0.85:
                findings.append(Finding(
                    check="duplicate_deliverables",
                    severity="warning",
                    message=f"'{na}' ({sa}) and '{nb}' ({sb}) look like duplicates.",
                    recommended_fix="Merge them or differentiate the problem each one solves.",
                ))
    return findings


def check_missing(brief: OfferBrief, product_package: dict[str, Any],
                  core_deliverables: list[Any]) -> list[Finding]:
    findings: list[Finding] = []
    if not core_deliverables:
        findings.append(Finding(
            check="missing_deliverables", severity="blocking",
            message="No core deliverables were produced.",
            recommended_fix="Regenerate core deliverables from the brief; the core cannot ship empty.",
        ))
    if not product_package.get("modules"):
        findings.append(Finding(
            check="missing_deliverables", severity="blocking",
            message="Product package has no modules.",
            recommended_fix="Regenerate the product package.",
        ))
    if not product_package.get("quick_start_guide"):
        findings.append(Finding(
            check="missing_deliverables", severity="warning",
            message="No Quick Start Guide — speed-to-value suffers without a first-win path.",
            recommended_fix="Add a Quick Start Guide the buyer can complete in under 30 minutes.",
        ))
    return findings


# --- Judgment checks (LLM) ---------------------------------------------------

_JUDGE_SCHEMA = (
    'Respond with ONLY a JSON array. Each item: '
    '{"check": string, "severity": "blocking"|"warning"|"info", '
    '"message": string, "recommended_fix": string}. '
    "If nothing is wrong for a check, omit it. Empty array [] means all clear."
)


def check_hierarchy_ai(llm: LLMClient, brief: OfferBrief, assets: dict[str, Any]) -> list[Finding]:
    system = system_prompt("Hierarchy & Ethics Validator")
    payload = json.dumps({
        "product_package": assets.get("product_package"),
        "core_deliverables": assets.get("core_deliverables"),
        "bonus_deliverables": assets.get("bonus_deliverables"),
        "order_bump": assets.get("order_bump"),
        "content_sample": (assets.get("reels", {}) or {}).get("scripts", [])[:3],
    }, ensure_ascii=False)[:120_000]

    user = f"""{brief_context(brief)}

Audit the generated assets below against the hierarchy and ethics rules. Check specifically:
1. bonus_stronger_than_core — is any bonus more valuable/desirable than the core product?
2. order_bump_too_valuable — does the bump rival or replace the core?
3. generic_ai_content — is any content generic/templated rather than specific to THIS avatar/promise?
4. unsupported_claims — any misleading, exaggerated, unsupported, or fabricated income/health claims?
5. support_burden — any deliverable likely to spike buyer confusion or support tickets?
6. promise_misalignment — any deliverable not clearly serving the Main Promise?

GENERATED ASSETS:
{payload}

{_JUDGE_SCHEMA}"""
    try:
        raw = llm.generate_json(system, user)
    except Exception as e:  # noqa: BLE001
        logger.warning("AI hierarchy check failed, continuing with structural checks only: %s", e)
        return [Finding("ai_check", "info",
                        f"AI hierarchy check could not run ({e}).",
                        "Re-run the validator once the LLM is reachable.")]
    items = raw if isinstance(raw, list) else raw.get("findings", []) if isinstance(raw, dict) else []
    out: list[Finding] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        out.append(Finding(
            check=str(it.get("check", "ai_check")),
            severity=str(it.get("severity", "warning")),
            message=str(it.get("message", "")),
            recommended_fix=str(it.get("recommended_fix", "")),
        ))
    return out


def validate(brief: OfferBrief, assets: dict[str, Any], llm: LLMClient | None = None) -> ValidationResult:
    """Run all checks. Pass an LLM client to include judgment checks."""
    result = ValidationResult()
    core = assets.get("core_deliverables", []) or []
    bonuses = assets.get("bonus_deliverables", []) or []
    product_package = assets.get("product_package", {}) or {}

    result.add(*check_duplicates(core, bonuses))
    result.add(*check_missing(brief, product_package, core))
    if llm is not None:
        result.add(*check_hierarchy_ai(llm, brief, assets))
    return result
