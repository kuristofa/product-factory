"""Phase 3 prompts: the full content marketing pack.

Every builder returns (system, user). Volume assets are generated in batches so
quality stays high and output doesn't truncate. Output schemas match spec section 4.
"""
from __future__ import annotations

import json

from factory.brief import OfferBrief
from factory.prompts.methodology import brief_context, system_prompt

_JSON_ARRAY = "Respond with ONLY valid JSON (a JSON array). No markdown, no fences, no commentary."
_JSON_OBJ = "Respond with ONLY valid JSON (a JSON object). No markdown, no fences, no commentary."

_POST_GUIDE = {
    "direct_pitch": ("Name the offer and the outcome plainly. End with a CTA to the keyword. "
                     "No hype, no fake scarcity.",
                     '"cta": string, "cta_keyword": string'),
    "nurture": ("Relate and build trust; tell a story tied to the avatar's world. NO ask. "
                'Set "cta" and "cta_keyword" to null.',
                '"cta": null, "cta_keyword": null'),
    "objection": ("Dissolve exactly one hesitation. Map each post to one item in buyer_objections "
                  'via "objection_addressed". End with a soft CTA to the keyword.',
                  '"cta": string, "cta_keyword": string, "objection_addressed": string'),
    "proof": ("Show substantiable evidence only. Set proof_type to one of "
              "testimonial|result|process|screenshot_prompt. For screenshot_prompt, proof_content "
              "states what REAL asset to capture — never fabricate results.",
              '"cta": string, "cta_keyword": string, '
              '"proof_type": "testimonial|result|process|screenshot_prompt", "proof_content": string'),
}


def build_reel_ideas(brief: OfferBrief, count: int, start_index: int = 1) -> tuple[str, str]:
    system = system_prompt("Content Strategist")
    user = f"""{brief_context(brief)}

Generate {count} DISTINCT Instagram Reel ideas that pull the Avatar toward the Main Promise
and set up a keyword DM. Vary the angle (pain, myth-bust, quick win, before/after, mistake,
contrarian, day-in-life, results). These are ideas #{start_index}-#{start_index + count - 1}.

{_JSON_ARRAY}
Each item: {{ "index": int (starting {start_index}), "angle": "2-4 words",
"hook": "scroll-stopping opener", "core_idea": "1-2 sentences", "cta_keyword": "single word" }}"""
    return system, user


def build_reel_scripts(brief: OfferBrief, ideas_batch: list[dict]) -> tuple[str, str]:
    system = system_prompt("Short-Form Scriptwriter")
    user = f"""{brief_context(brief)}

Write a complete, shootable Reel script for EACH idea below (20-45s spoken). No fake urgency,
no unsupported claims.

REEL IDEAS:
{json.dumps(ideas_batch, indent=2, ensure_ascii=False)}

{_JSON_ARRAY}
Each item: {{ "index": int (match source), "hook": "spoken+on-screen opener (0-3s)",
"script": "full line-by-line voiceover", "b_roll_or_visual_notes": "on-screen per part",
"on_screen_text": ["caption overlays"], "spoken_cta": "closing line to keyword", "cta_keyword": string }}"""
    return system, user


def build_carousels(brief: OfferBrief, count: int, start_index: int = 1) -> tuple[str, str]:
    system = system_prompt("Carousel Author")
    user = f"""{brief_context(brief)}

Generate {count} authority-building carousel outlines (#{start_index}-#{start_index + count - 1}).
Each teaches ONE idea deeply across 6-10 slides and ends with a CTA to a keyword.

{_JSON_ARRAY}
Each item: {{ "index": int (from {start_index}), "angle": "2-4 words",
"hook_slide": "slide 1 headline", "slides": [{{ "headline": string, "body": string }}],
"cta_slide": "final CTA slide", "cta_keyword": string }}"""
    return system, user


def build_posts(brief: OfferBrief, post_type: str, count: int, start_index: int = 1) -> tuple[str, str]:
    guide, extra = _POST_GUIDE[post_type]
    system = system_prompt("Social Copywriter")
    user = f"""{brief_context(brief)}

Generate {count} {post_type.replace('_', ' ')} posts (#{start_index}-#{start_index + count - 1}).
{guide}

{_JSON_ARRAY}
Each item: {{ "index": int (from {start_index}), "post_type": "{post_type}",
"hook": "first line", "body": "caption body", {extra} }}"""
    return system, user


def build_story_prompts(brief: OfferBrief, count: int) -> tuple[str, str]:
    system = system_prompt("Stories Strategist")
    user = f"""{brief_context(brief)}

Generate {count} Instagram Story prompts for engagement and keyword triggers.
frame_type is one of poll|question|quiz|real_countdown|dm_trigger. Use real_countdown ONLY for
genuine deadlines.

{_JSON_ARRAY}
Each item: {{ "index": int, "frame_type": "poll|question|quiz|real_countdown|dm_trigger",
"prompt_text": string, "sticker": "sticker/interaction to use", "cta_keyword": "string or null" }}"""
    return system, user


def build_cta_captions(brief: OfferBrief) -> tuple[str, str]:
    system = system_prompt("CTA Copywriter")
    user = f"""{brief_context(brief)}

Generate a reusable set of CTA captions, spanning reel, carousel, and post uses. Each names its keyword.

{_JSON_ARRAY}
Each item: {{ "index": int, "for_asset": "reel|carousel|post", "caption": string, "keyword": string }}"""
    return system, user


def build_dm_keyword_prompts(brief: OfferBrief, keywords: list[str]) -> tuple[str, str]:
    system = system_prompt("DM Router")
    user = f"""{brief_context(brief)}

Build the keyword-to-intent map for these keywords collected from the content:
{json.dumps(sorted(set(k for k in keywords if k)), ensure_ascii=False)}

{_JSON_ARRAY}
Each item: {{ "keyword": string, "triggered_by": "which content drives it",
"intent": "what the user wants when they send it", "first_response_ref": "what the initial DM should deliver" }}"""
    return system, user


def build_manychat(brief: OfferBrief, keywords: list[str]) -> tuple[str, str]:
    from factory.prompts.methodology import resolve_dm_tool
    tool = resolve_dm_tool(brief)
    system = system_prompt("Automation Copywriter")
    user = f"""{brief_context(brief)}

Write the DM-automation flow copy for the primary keyword funnel, formatted for **{tool}**
(the product's DM-automation tool). Value-first, non-spammy. Include an explicit
handoff_condition where a human should take over.
Primary keywords available: {json.dumps(sorted(set(k for k in keywords if k)), ensure_ascii=False)}

{_JSON_OBJ}
Schema: {{ "tool": "{tool}", "flow_name": string, "trigger_keyword": string,
"steps": [{{ "order": int, "message": string, "quick_replies": [string], "delay": "e.g. 0m, 1h" }}],
"handoff_condition": "when a human takes over" }}"""
    return system, user
