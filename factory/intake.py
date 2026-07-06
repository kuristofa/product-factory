"""Intake: turn the Grand Slam Offer GPT's raw output into a structured Offer Brief.

The GPT hands you markdown / text / PDF, not JSON. This reads that file, extracts its
text, and asks Claude (via the same Claude Code runtime) to map it onto the OfferBrief
schema. The result is written to briefs/ and then validated like any other brief.
"""
from __future__ import annotations

import json
from pathlib import Path

from factory.brief import REQUIRED_FIELDS, OfferBrief
from factory.llm import LLMClient, LLMError
from factory.prompts.methodology import system_prompt


def extract_text(path: str | Path) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Intake source not found: {p}")
    suffix = p.suffix.lower()
    if suffix in (".md", ".txt", ""):
        return p.read_text(encoding="utf-8", errors="replace")
    if suffix == ".json":
        # already structured — pass through as text; the model will normalize it
        return p.read_text(encoding="utf-8", errors="replace")
    if suffix == ".pdf":
        try:
            import pdfplumber
        except ImportError as e:
            raise RuntimeError(
                "Reading a PDF brief needs pdfplumber. Install it (pip install pdfplumber) "
                "or save the GPT output as .md / .txt instead."
            ) from e
        with pdfplumber.open(str(p)) as pdf:
            return "\n\n".join((page.extract_text() or "") for page in pdf.pages).strip()
    raise ValueError(f"Unsupported intake format '{suffix}'. Use .md, .txt, .pdf, or .json.")


def _fields_doc() -> str:
    return "\n".join(f"- {attr}: {label}" for attr, label in REQUIRED_FIELDS.items())


def structure_brief(llm: LLMClient, raw_text: str) -> dict:
    system = system_prompt("Offer Brief Intake Specialist")
    user = f"""Below is the raw output of the Grand Slam Offer GPT for one offer. Convert it into a
structured Offer Brief JSON object. Extract only what the text actually says — do NOT invent an
offer, price, promise, or deliverables. If the text genuinely does not contain a required field,
use an empty string "" (or [] for list fields) so validation can flag it.

Required fields (JSON keys on the left):
{_fields_doc()}

List fields: core_deliverables, bonus_deliverables, future_upsells, buyer_objections.
order_bump may be a string; use "none" if the offer has no bump.
Optional: if the offer names a DM-automation tool (e.g. ManyChat, Chatfuel, InstaChamp), include it
as "dm_tool"; otherwise omit that key.

RAW OFFER OUTPUT:
\"\"\"
{raw_text.strip()}
\"\"\"

Respond with ONLY the JSON object. No markdown, no fences, no commentary."""
    data = llm.generate_json(system, user)
    if not isinstance(data, dict):
        raise LLMError("Intake did not return a JSON object.")
    return data


def run_intake(llm: LLMClient, source: str | Path, briefs_dir: Path,
               out_name: str | None = None) -> tuple[Path, OfferBrief]:
    """Extract → structure → write to briefs/. Returns (path, brief). Caller validates."""
    raw = extract_text(source)
    if not raw.strip():
        raise ValueError("The intake source appears to be empty.")
    data = structure_brief(llm, raw)
    brief = OfferBrief.from_dict(data)

    briefs_dir.mkdir(parents=True, exist_ok=True)
    from factory.output import slugify
    stem = out_name or (slugify(brief.offer_name) if brief.offer_name else Path(source).stem)
    out_path = briefs_dir / f"{stem}.json"
    out_path.write_text(json.dumps(brief.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path, brief
