"""Phase 3 prompt: the DM automation sequence (the conversation that sells).

Output schema matches spec section 4 (DMSequence). Gated behind dm_automation.
"""
from __future__ import annotations

from factory.brief import OfferBrief
from factory.prompts.methodology import brief_context, system_prompt


def build_dm_automation(brief: OfferBrief, keywords: list[str]) -> tuple[str, str]:
    system = system_prompt("DM Automation Strategist")
    kw = sorted(set(k for k in keywords if k))
    user = f"""{brief_context(brief)}

Write the full automated DM sequence that turns a keyword into a sale. Value-first and non-spammy;
the recipient always gets what the content promised. objection_responses must map the brief's
Buyer Objections. A human takes over anything nuanced.

Keywords in play: {kw}

Respond with ONLY valid JSON (an object). No markdown, no fences, no commentary.
Schema:
{{
  "keyword_list": [string],
  "initial_dm": "delivers the promised value + qualifies",
  "follow_ups": [{{ "order": int, "message": string, "send_after": "e.g. 1h, 1d" }}],
  "checkout_messages": [string],
  "reminder_messages": [{{ "order": int, "message": string, "send_after": string }}],
  "objection_responses": [{{ "objection": string, "response": string }}]
}}"""
    return system, user
