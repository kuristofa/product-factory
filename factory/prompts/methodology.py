"""Shared grounding injected into every generation prompt.

This encodes the *general, publicly-known* mechanics of an Instagram low-ticket
funnel (Reels -> keyword-triggered DM automation -> low-ticket checkout, with
launch/"buying frenzy" momentum mechanics). It does NOT reproduce any paid course
content. To ground generation in your own extracted course notes, set
METHODOLOGY_NOTES_PATH in .env; their contents are appended below at runtime.
"""
from __future__ import annotations

import json
from pathlib import Path

from config import settings
from factory.brief import OfferBrief

# --- General methodology (safe, non-proprietary) -----------------------------

METHODOLOGY_BASE = """\
SALES MACHINE — OPERATING MODEL (general mechanics)

Funnel shape:
  Organic Reels/content -> comment or DM keyword -> automated DM sequence (via the product's
  DM-automation tool) -> value + soft pitch -> low-ticket checkout -> instant digital delivery
  -> optional order bump -> (later, only after validation) upsell/downsell/cross-sell.

Core principles:
- The core product carries the transformation. Everything else supports it, never outshines it.
- Content earns attention and trust; the DM does the selling; checkout removes friction.
- Low-ticket = impulse-friendly price with an obvious, immediate ROI the buyer can feel.
- "Buying frenzy" momentum comes from genuine demand signals (real results, real deadlines,
  real limited cohorts), NEVER from fabricated countdowns or fake scarcity.
- Speed-to-value: the buyer should get a win fast (Quick Start Guide, first easy deliverable).

Content roles:
- Reels: hook -> value -> soft CTA to a keyword.
- Carousels: teach one idea deeply, build authority.
- Direct pitch posts: name the offer and the outcome plainly.
- Nurture posts: relate, build trust, no ask.
- Objection posts: dissolve one specific hesitation each.
- Proof posts: show real evidence (results, testimonials, process) — only claims that can be substantiated.
- Story prompts: quick engagement + keyword triggers.

DM automation roles:
- Keyword captures intent -> initial DM delivers promised value + qualifies -> follow-ups nudge ->
  checkout message -> reminders -> objection responses. Human takes over anything nuanced.
"""

# --- Hierarchy rules (Phase 4 lives here as generation-time guardrails too) ---

HIERARCHY_RULES = """\
NON-NEGOTIABLE HIERARCHY RULES:
1. Bonuses must NEVER be more valuable or more desirable than the core product.
   Bonuses remove a specific objection or accelerate a result; they are not standalone products.
2. The order bump COMPLEMENTS the core product; it must never replace it or overshadow it.
   It is a small, logical add-on ("yes, and also this") at a fraction of the core price.
3. Upsells/downsells/cross-sells are PLANNED ONLY at this stage. Do not fully build them until
   validation criteria are met. Reference them as future, not present, assets.
4. Every deliverable must serve a defined purpose tied to the approved core promise.
   No filler. If a deliverable doesn't advance the promise, it doesn't belong.
5. No duplicate deliverables. Each solves a distinct problem.
"""

# --- Ethics guardrails (Constraints section of the spec) ---------------------

ETHICS_RULES = """\
ETHICAL MARKETING GUARDRAILS (hard constraints):
- No fake urgency or fake scarcity. Deadlines and limits must be real.
- No misleading, exaggerated, or unsupported claims.
- No fabricated earnings/income claims and no implied "typical results." Any income or ROI
  language must be framed as potential/illustrative and be honestly caveated.
- No unsubstantiated health claims. Route anything health-adjacent to human review.
- No spammy automation. DMs provide value and respect the recipient; easy opt-out implied.
- Products must be genuinely valuable and production-ready.
Respect the brief's stated Ethical Boundaries above all.
"""


def load_notes() -> str:
    """Return the user's extracted course notes if configured, else empty string."""
    p: Path | None = settings.methodology_notes_path
    if not p:
        return ""
    if not p.exists():
        return f"\n[Note: METHODOLOGY_NOTES_PATH is set to {p} but the file was not found.]\n"
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return ""


def methodology_block() -> str:
    notes = load_notes()
    block = f"{METHODOLOGY_BASE}\n\n{HIERARCHY_RULES}\n\n{ETHICS_RULES}"
    if notes.strip():
        block += (
            "\n\nGROUNDING NOTES (from the operator's own extracted course material — "
            "treat as the authoritative source where it conflicts with the general model above):\n"
            f"{notes.strip()}\n"
        )
    return block


def brief_context(brief: OfferBrief) -> str:
    """A compact, faithful rendering of the approved brief for prompt injection."""
    d = brief.to_dict()
    return "APPROVED OFFER BRIEF:\n" + json.dumps(d, indent=2, ensure_ascii=False)


def resolve_dm_tool(brief: OfferBrief) -> str:
    """The DM-automation tool for this product: brief field, else the config default."""
    return (brief.dm_tool or "").strip() or settings.dm_tool


def system_prompt(role: str) -> str:
    """Assemble the standard system prompt for a given generator role."""
    return (
        f"You are the {role} inside an AI Product Production Factory for low-ticket "
        "digital products sold via an Instagram organic sales machine.\n\n"
        f"{methodology_block()}\n\n"
        "You produce production-ready assets, not drafts-of-drafts. You never invent the offer — "
        "you work strictly from the approved brief. Write in the brief's specified Tone. "
        "Be concrete and specific to THIS avatar and THIS promise; avoid generic, templated, "
        "could-be-any-product copy."
    )
