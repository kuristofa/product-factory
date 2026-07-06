"""Output layer: render generated assets to organized, human-readable files.

Everything goes under output/<offer-slug>/. Raw JSON is always written (source of
truth, machine-readable) plus a Markdown rendering for human review at each gate.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "offer").lower()).strip("-")
    return s or "offer"


class OutputWriter:
    def __init__(self, base_output_dir: Path, offer_name: str):
        self.slug = slugify(offer_name)
        self.root = Path(base_output_dir) / self.slug
        self.root.mkdir(parents=True, exist_ok=True)

    # -- raw json (source of truth) -------------------------------------------

    def write_json(self, name: str, data: Any) -> Path:
        path = self.root / f"{name}.json"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    # -- markdown renderings for review ---------------------------------------

    def write_markdown(self, name: str, markdown: str) -> Path:
        path = self.root / f"{name}.md"
        path.write_text(markdown, encoding="utf-8")
        return path

    def write_review(self, gate: str, markdown: str) -> Path:
        """Write the review artifact a human reads before approving a gate."""
        review_dir = self.root / "_gates"
        review_dir.mkdir(parents=True, exist_ok=True)
        path = review_dir / f"REVIEW__{gate}.md"
        path.write_text(markdown, encoding="utf-8")
        return path


# --- markdown renderers -------------------------------------------------------

def render_product_package(pkg: dict[str, Any]) -> str:
    lines = ["# Product Package\n", pkg.get("product_outline", ""), "\n## Modules\n"]
    for i, m in enumerate(pkg.get("modules", []), 1):
        lines.append(f"### Module {i}: {m.get('title','')}")
        lines.append(f"*Outcome:* {m.get('outcome','')}\n")
        for lesson in m.get("lessons", []):
            lines.append(f"- **{lesson.get('title','')}** ({lesson.get('format','')}): "
                         f"{lesson.get('teaching_point','')}")
        lines.append("")
    if pkg.get("worksheets"):
        lines.append("## Worksheets")
        lines += [f"- **{w.get('name','')}** — {w.get('purpose','')}" for w in pkg["worksheets"]]
        lines.append("")
    if pkg.get("templates"):
        lines.append("## Templates")
        lines += [f"- **{t.get('name','')}** — {t.get('purpose','')}" for t in pkg["templates"]]
        lines.append("")
    lines.append("## Quick Start Guide\n" + str(pkg.get("quick_start_guide", "")))
    lines.append("\n## Customer Success Path")
    for ms in pkg.get("customer_success_path", []):
        lines.append(f"- **{ms.get('milestone','')}** — {ms.get('how_they_know_they_hit_it','')}")
    lines.append("\n## Delivery Instructions\n" + str(pkg.get("delivery_instructions", "")))
    return "\n".join(lines)


def render_deliverables(title: str, items: list[dict[str, Any]]) -> str:
    lines = [f"# {title}\n"]
    for it in items:
        lines.append(f"## {it.get('name', it.get('title',''))}")
        for k, v in it.items():
            if k in ("name", "title"):
                continue
            label = k.replace("_", " ").title()
            lines.append(f"- **{label}:** {v}")
        lines.append("")
    return "\n".join(lines)


def render_order_bump(bump: dict[str, Any]) -> str:
    return (
        "# Order Bump\n\n"
        f"**Product:** {bump.get('product','')}\n\n"
        f"**Copy:**\n{bump.get('copy','')}\n\n"
        f"**Positioning:** {bump.get('positioning','')}\n\n"
        f"**Delivery Method:** {bump.get('delivery_method','')}\n"
    )


def render_reels(reels: dict[str, Any]) -> str:
    lines = ["# Reels\n", "## Ideas\n"]
    for idea in reels.get("ideas", []):
        lines.append(f"**#{idea.get('index','')} [{idea.get('angle','')}]** — "
                     f"Hook: {idea.get('hook','')}  \nIdea: {idea.get('core_idea','')}  "
                     f"→ keyword `{idea.get('cta_keyword','')}`\n")
    lines.append("\n## Scripts\n")
    for s in reels.get("scripts", []):
        lines.append(f"### Reel #{s.get('index','')}")
        lines.append(f"*Hook:* {s.get('hook','')}\n")
        lines.append(str(s.get("script", "")))
        if s.get("on_screen_text"):
            lines.append("\n*On-screen text:* " + " | ".join(s["on_screen_text"]))
        lines.append(f"\n*CTA:* {s.get('spoken_cta','')} → `{s.get('cta_keyword','')}`\n")
    return "\n".join(lines)


def render_carousels(items: list[dict[str, Any]]) -> str:
    lines = ["# Carousels\n"]
    for c in items:
        lines.append(f"## #{c.get('index','')} [{c.get('angle','')}]")
        lines.append(f"*Slide 1:* {c.get('hook_slide','')}")
        for i, s in enumerate(c.get("slides", []), 2):
            lines.append(f"*Slide {i}:* **{s.get('headline','')}** — {s.get('body','')}")
        lines.append(f"*Final:* {c.get('cta_slide','')} → `{c.get('cta_keyword','')}`\n")
    return "\n".join(lines)


def render_posts(posts: dict[str, list]) -> str:
    lines = ["# Social Posts\n"]
    for ptype, items in posts.items():
        lines.append(f"## {ptype.replace('_', ' ').title()}\n")
        for pst in items:
            lines.append(f"**#{pst.get('index','')}** — {pst.get('hook','')}")
            lines.append(pst.get("body", ""))
            if pst.get("objection_addressed"):
                lines.append(f"*Objection:* {pst['objection_addressed']}")
            if pst.get("proof_type"):
                lines.append(f"*Proof ({pst['proof_type']}):* {pst.get('proof_content','')}")
            if pst.get("cta"):
                lines.append(f"*CTA:* {pst['cta']} → `{pst.get('cta_keyword','')}`")
            lines.append("")
    return "\n".join(lines)


def render_story_prompts(items: list[dict[str, Any]]) -> str:
    lines = ["# Story Prompts\n"]
    for s in items:
        kw = f" → `{s['cta_keyword']}`" if s.get("cta_keyword") and s["cta_keyword"] != "null" else ""
        lines.append(f"- **#{s.get('index','')} [{s.get('frame_type','')}]** {s.get('prompt_text','')} "
                     f"({s.get('sticker','')}){kw}")
    return "\n".join(lines)


def render_cta_captions(items: list[dict[str, Any]]) -> str:
    lines = ["# CTA Captions\n"]
    for c in items:
        lines.append(f"- **[{c.get('for_asset','')}]** {c.get('caption','')} → `{c.get('keyword','')}`")
    return "\n".join(lines)


def render_dm_keyword_prompts(items: list[dict[str, Any]]) -> str:
    lines = ["# DM Keyword Map\n"]
    for k in items:
        lines.append(f"### `{k.get('keyword','')}`")
        lines.append(f"- Triggered by: {k.get('triggered_by','')}")
        lines.append(f"- Intent: {k.get('intent','')}")
        lines.append(f"- First response: {k.get('first_response_ref','')}\n")
    return "\n".join(lines)


def render_manychat(m: dict[str, Any]) -> str:
    tool = m.get("tool") or "DM Automation"
    lines = [f"# {tool} Flow — {m.get('flow_name','')}\n",
             f"**Trigger keyword:** `{m.get('trigger_keyword','')}`\n"]
    for step in m.get("steps", []):
        qr = ", ".join(step.get("quick_replies", []))
        lines.append(f"**Step {step.get('order','')}** ({step.get('delay','')}): {step.get('message','')}")
        if qr:
            lines.append(f"  ↳ quick replies: {qr}")
    lines.append(f"\n**Handoff to human when:** {m.get('handoff_condition','')}")
    return "\n".join(lines)


def render_dm_automation(d: dict[str, Any]) -> str:
    lines = ["# DM Automation Sequence\n",
             f"**Keywords:** {', '.join(d.get('keyword_list', []))}\n",
             "## Initial DM\n" + str(d.get("initial_dm", "")), "\n## Follow-ups"]
    for f in d.get("follow_ups", []):
        lines.append(f"- ({f.get('send_after','')}) {f.get('message','')}")
    lines.append("\n## Checkout messages")
    lines += [f"- {m}" for m in d.get("checkout_messages", [])]
    lines.append("\n## Reminders")
    for r in d.get("reminder_messages", []):
        lines.append(f"- ({r.get('send_after','')}) {r.get('message','')}")
    lines.append("\n## Objection responses")
    for o in d.get("objection_responses", []):
        lines.append(f"- **{o.get('objection','')}** — {o.get('response','')}")
    return "\n".join(lines)


def render_checkout(c: dict[str, Any]) -> str:
    lines = ["# Checkout & Delivery Assets\n",
             "## Checkout Page Copy\n" + str(c.get("checkout_page_copy", "")),
             "\n## Product Description\n" + str(c.get("product_description", "")),
             "\n## Bullet Stack"]
    lines += [f"- {b}" for b in c.get("bullet_stack", [])]
    lines.append("\n## Bonus Copy\n" + str(c.get("bonus_copy", "")))
    lines.append("\n## Order Bump Copy\n" + str(c.get("order_bump_copy", "")))
    lines.append("\n## Thank You Page\n" + str(c.get("thank_you_page", "")))
    for key, title in [("delivery_email", "Delivery Email"),
                       ("purchase_confirmation", "Purchase Confirmation")]:
        e = c.get(key, {}) or {}
        lines.append(f"\n## {title}\n**Subject:** {e.get('subject','')}\n\n{e.get('body','')}")
    lines.append("\n## Follow-up Emails")
    for e in c.get("follow_up_emails", []):
        lines.append(f"\n**({e.get('send_after','')}) {e.get('subject','')}**\n\n{e.get('body','')}")
    lines.append("\n## Refund Instructions\n" + str(c.get("refund_instructions", "")))
    return "\n".join(lines)
