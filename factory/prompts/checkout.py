"""Phase 3 prompt: all checkout + delivery assets (10 sub-assets).

Output schema matches spec section 4 (CheckoutAssets). Gated behind checkout_copy.
"""
from __future__ import annotations

from factory.brief import OfferBrief
from factory.prompts.methodology import brief_context, system_prompt


def build_checkout(brief: OfferBrief) -> tuple[str, str]:
    system = system_prompt("Checkout &amp; Lifecycle Copywriter")
    user = f"""{brief_context(brief)}

Write all checkout and delivery assets for this low-ticket product. Accurate to the product,
ethical (honest refund terms, no fake urgency), delivery matched to the brief's Delivery Format.

Respond with ONLY valid JSON (an object). No markdown, no fences, no commentary.
Schema:
{{
  "checkout_page_copy": "full checkout page copy",
  "product_description": "short store/checkout description",
  "bullet_stack": [ "benefit bullet", ... ],
  "bonus_copy": "the bonus stack copy shown at checkout",
  "order_bump_copy": "the order bump copy at checkout",
  "thank_you_page": "post-purchase thank-you page copy",
  "delivery_email": {{ "subject": string, "body": string }},
  "purchase_confirmation": {{ "subject": string, "body": string }},
  "follow_up_emails": [ {{ "order": int, "subject": string, "body": string, "send_after": "e.g. 1d" }} ],
  "refund_instructions": "clear, honest refund instructions respecting ethical_boundaries"
}}"""
    return system, user
