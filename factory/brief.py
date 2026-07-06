"""Offer Brief schema + completeness validation (Phase 2).

The factory's ONLY input is an approved Offer Brief from the Grand Slam Offer GPT.
This module defines that interface and refuses to proceed on an incomplete brief,
listing exactly what is missing so it can be sent back for completion.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any


# Fields the Grand Slam Offer GPT must supply. Value = human-readable label used in
# rejection messages. Order here is the order missing items are reported.
REQUIRED_FIELDS: dict[str, str] = {
    "offer_name": "Offer Name",
    "avatar": "Avatar",
    "main_problem": "Main Problem",
    "main_promise": "Main Promise",
    "core_product_type": "Core Product Type",
    "core_deliverables": "Core Deliverables",
    "bonus_deliverables": "Bonus Deliverables",
    "order_bump": "Order Bump",
    "future_upsells": "Future Upsells",
    "buyer_objections": "Buyer Objections",
    "roi_logic": "ROI Logic",
    "tone": "Tone",
    "ethical_boundaries": "Ethical Boundaries",
    "delivery_format": "Delivery Format",
}

# Fields where an empty list/collection is NOT acceptable (the offer is meaningless
# without at least one).
NON_EMPTY_LIST_FIELDS = {"core_deliverables", "buyer_objections"}

# List fields that MAY be empty by design (spec section 5).
OPTIONAL_LIST_FIELDS = {"bonus_deliverables", "future_upsells"}


@dataclass
class OfferBrief:
    offer_name: str = ""
    avatar: str = ""
    main_problem: str = ""
    main_promise: str = ""
    core_product_type: str = ""
    core_deliverables: list[Any] = field(default_factory=list)
    bonus_deliverables: list[Any] = field(default_factory=list)
    order_bump: Any = None
    future_upsells: list[Any] = field(default_factory=list)
    buyer_objections: list[Any] = field(default_factory=list)
    roi_logic: str = ""
    tone: str = ""
    ethical_boundaries: str = ""
    delivery_format: str = ""

    # Optional: the DM-automation tool this product uses (e.g. ManyChat, Chatfuel).
    # Blank falls back to the DM_TOOL default in config. Not required for validation.
    dm_tool: str = ""

    # Free-form extras from the Offer GPT are preserved but not required.
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OfferBrief":
        known = {f.name for f in fields(cls)} - {"extras"}
        kwargs = {k: v for k, v in data.items() if k in known}
        extras = {k: v for k, v in data.items() if k not in known}
        return cls(**kwargs, extras=extras)

    @classmethod
    def from_json_file(cls, path: str | Path) -> "OfferBrief":
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Offer brief not found: {p}")
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"Offer brief {p} is not valid JSON: {e}") from e
        if not isinstance(data, dict):
            raise ValueError(f"Offer brief {p} must be a JSON object, got {type(data).__name__}.")
        return cls.from_dict(data)

    def to_dict(self) -> dict[str, Any]:
        out = {name: getattr(self, name) for name in REQUIRED_FIELDS}
        if self.dm_tool:
            out["dm_tool"] = self.dm_tool
        if self.extras:
            out["extras"] = self.extras
        return out

    def validate(self) -> list[str]:
        """Return a list of human-readable problems. Empty list == brief is complete."""
        problems: list[str] = []
        for attr, label in REQUIRED_FIELDS.items():
            value = getattr(self, attr)
            if attr in NON_EMPTY_LIST_FIELDS:
                if not isinstance(value, list) or len(value) == 0:
                    problems.append(f"Missing or empty: {label} (needs at least one item).")
            elif attr in OPTIONAL_LIST_FIELDS:
                continue  # empty is allowed by design
            elif isinstance(value, (list, dict)):
                if len(value) == 0:
                    problems.append(f"Missing or empty: {label}.")
            elif value is None or (isinstance(value, str) and not value.strip()):
                problems.append(f"Missing: {label}.")
        return problems

    def is_complete(self) -> bool:
        return len(self.validate()) == 0


class IncompleteBriefError(ValueError):
    """Raised when a brief fails completeness validation, carrying the problem list."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        joined = "\n  - ".join(problems)
        super().__init__(
            "Offer Brief is incomplete. Send it back to the Grand Slam Offer GPT "
            f"with these missing items:\n  - {joined}"
        )


def load_and_require_complete(path: str | Path) -> OfferBrief:
    """Load a brief and raise IncompleteBriefError if it isn't production-ready."""
    brief = OfferBrief.from_json_file(path)
    problems = brief.validate()
    if problems:
        raise IncompleteBriefError(problems)
    return brief
