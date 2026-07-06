"""Human approval gates.

The spec requires manual approval before several stages. This implements a simple,
auditable, file-based gate: each gate has a status in `_gates/gates.json`. The pipeline
refuses to pass a gate until it's "approved". Approving = running the CLI `approve`
command (or flipping the JSON by hand). This same interface can later be backed by a
Google Sheet cell instead of a file, without changing pipeline code.
"""
from __future__ import annotations

import json
from pathlib import Path

# The gates from the spec, in workflow order.
GATE_ORDER: list[str] = [
    "offer_brief",
    "product_promise",
    "core_deliverables",
    "bonus_deliverables",
    "hierarchy_validation",
    "health_claims",
    "roi_claims",
    "dm_automation",
    "checkout_copy",
    "order_bump",
    "final_product",
]

PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"

# In `generate --auto`, every other gate is auto-approved; the pipeline stops ONLY at
# these. They're the substantive review moments: the full generated package + safety/claims
# report, and the final sign-off. Blocking validation halts regardless of this set.
CRITICAL_GATES = {"hierarchy_validation", "final_product"}


class GateStore:
    def __init__(self, base_dir: Path):
        self.dir = Path(base_dir) / "_gates"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "gates.json"
        self._state = self._load()

    def _load(self) -> dict[str, str]:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        return {g: PENDING for g in GATE_ORDER}

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")

    def status(self, gate: str) -> str:
        return self._state.get(gate, PENDING)

    def is_approved(self, gate: str) -> bool:
        return self.status(gate) == APPROVED

    def set(self, gate: str, status: str) -> None:
        if gate not in GATE_ORDER:
            raise ValueError(f"Unknown gate '{gate}'. Valid gates: {', '.join(GATE_ORDER)}")
        if status not in (PENDING, APPROVED, REJECTED):
            raise ValueError(f"Invalid status '{status}'.")
        self._state[gate] = status
        self._save()

    def approve(self, gate: str) -> None:
        self.set(gate, APPROVED)

    def snapshot(self) -> dict[str, str]:
        return dict(self._state)


class GateBlocked(Exception):
    """Raised when the pipeline hits a gate that isn't approved yet."""

    def __init__(self, gate: str, review_path: Path):
        self.gate = gate
        self.review_path = review_path
        super().__init__(
            f"Approval gate '{gate}' is pending. Review the drafts at:\n  {review_path}\n"
            f"Then approve with:  python run.py approve --offer <slug> --gate {gate}"
        )
