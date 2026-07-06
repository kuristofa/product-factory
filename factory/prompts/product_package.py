"""Phase 3 prompts: the product itself and its commercial scaffolding.

Product Package, Core Deliverables, Bonus Deliverables, Order Bump.
Each returns (system, user). Structured outputs are requested as strict JSON.
"""
from __future__ import annotations

from factory.brief import OfferBrief
from factory.prompts.methodology import brief_context, system_prompt

_JSON_ONLY = (
    "Respond with ONLY valid JSON. No markdown, no code fences, no commentary before or after."
)


def build_product_package(brief: OfferBrief) -> tuple[str, str]:
    system = system_prompt("Product Architect")
    user = f"""{brief_context(brief)}

Design the complete product package for the CORE PRODUCT described above.
The product must fully deliver the Main Promise and be genuinely completable by the Avatar.

{_JSON_ONLY}

Use exactly this schema:
{{
  "product_outline": "2-4 sentence overview of what the product is and the transformation it delivers",
  "modules": [
    {{
      "title": "string",
      "outcome": "the specific result the buyer has after this module",
      "lessons": [
        {{ "title": "string", "teaching_point": "the one thing this lesson lands", "format": "video|text|walkthrough" }}
      ]
    }}
  ],
  "worksheets": [ {{ "name": "string", "purpose": "what completing it produces for the buyer" }} ],
  "templates": [ {{ "name": "string", "purpose": "the manual work it removes" }} ],
  "quick_start_guide": "step-by-step first-win path the buyer can complete in under 30 minutes",
  "customer_success_path": [
    {{ "milestone": "string", "how_they_know_they_hit_it": "observable signal of progress" }}
  ],
  "delivery_instructions": "how the buyer accesses and consumes this, matched to the brief's Delivery Format"
}}

Constraints: keep scope tight enough to be production-ready and completable at a low-ticket price.
Do not pad with filler modules. Every module must advance the Main Promise.
Worksheets and templates are supporting materials for the modules only — do NOT introduce a new
named template/worksheet that duplicates a core deliverable or that acts as an extra bonus, and make
sure delivery_instructions never references a count that doesn't match what you listed.
For customer_success_path, each milestone's "how_they_know_they_hit_it" must be about the buyer
COMPLETING a step or having a finished piece of the system — never about an external result
(subscribers, sales, followers) arriving, which cannot be guaranteed."""
    return system, user


def build_core_deliverables(brief: OfferBrief) -> tuple[str, str]:
    system = system_prompt("Deliverables Designer")
    user = f"""{brief_context(brief)}

Expand each Core Deliverable listed in the brief into a fully specified deliverable.
Do not invent new core deliverables and do not drop any from the brief.

{_JSON_ONLY}

Return a JSON array. For each core deliverable:
{{
  "name": "string",
  "purpose": "what job it does for the buyer",
  "format": "concrete format (PDF checklist, Notion template, video, etc.)",
  "problem_solved": "the specific buyer problem it removes",
  "completion_criteria": "how the buyer knows they've finished/used it correctly",
  "delivery_asset": "the exact artifact to produce and how it's delivered"
}}"""
    return system, user


def build_bonus_deliverables(brief: OfferBrief) -> tuple[str, str]:
    system = system_prompt("Bonus Designer")
    user = f"""{brief_context(brief)}

Expand each Bonus Deliverable from the brief. Bonuses REMOVE a specific buyer objection or
ACCELERATE a result. A bonus must never be more valuable or more desirable than the core product.

{_JSON_ONLY}

Return a JSON array. For each bonus:
{{
  "name": "string",
  "purpose": "the acceleration or objection-removal it provides",
  "objection_removed": "the exact hesitation this dissolves (tie to the brief's Buyer Objections where possible)",
  "why_it_belongs_as_a_bonus": "why this is a bonus and NOT part of the core / NOT a standalone product",
  "delivery_asset": "the exact artifact to produce and how it's delivered"
}}

If the brief lists no bonuses, return an empty array []."""
    return system, user


def build_order_bump(brief: OfferBrief) -> tuple[str, str]:
    system = system_prompt("Order Bump Strategist")
    user = f"""{brief_context(brief)}

Specify the Order Bump. It must COMPLEMENT the core product as a logical, low-friction add-on
("yes, and also this") priced at a small fraction of the core. It must never replace or overshadow
the core product.

{_JSON_ONLY}

Return this JSON object:
{{
  "product": "what the bump is",
  "copy": "the on-checkout bump copy (2-4 sentences, in the brief's Tone, ethical — no fake urgency)",
  "positioning": "why it's the obvious add-on right now, and how it stays subordinate to the core",
  "delivery_method": "how it's delivered alongside the core product"
}}

If the brief's Order Bump field is empty or 'none', return {{"product": "none", "copy": "", "positioning": "", "delivery_method": ""}}."""
    return system, user
