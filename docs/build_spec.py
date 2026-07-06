"""Builder for the AI Product Production Factory — DETAILED technical specification.

Source of truth for the spec PDF. Never edit the PDF by hand — edit this script and run:
    python docs/build_spec.py

This is the implementation-level spec for Phases 1-4: every artifact schema, per-asset
generation contract, the hierarchy validator's methods, the pipeline/gate state machine,
CLI, output layout, config, and failure taxonomy. Phases 5-6 are summarized in an appendix.

Data-driven: content lives in the DATA_MODELS / ASSET_SPECS / VALIDATOR_CHECKS / etc.
structures and is rendered by small helpers, so the spec stays consistent and maintainable.
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable, ListFlowable, ListItem, PageBreak, Paragraph, SimpleDocTemplate,
    Spacer, Table, TableStyle,
)

OUT = Path(__file__).resolve().parent / "AI_Product_Production_Factory_Spec.pdf"

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
pdfmetrics.registerFont(TTFont("DejaVu", f"{FONT_DIR}/DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DejaVu-Bold", f"{FONT_DIR}/DejaVuSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("DejaVu-Oblique", f"{FONT_DIR}/DejaVuSans-Oblique.ttf"))
pdfmetrics.registerFont(TTFont("DejaVuMono", f"{FONT_DIR}/DejaVuSansMono.ttf"))
pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold",
                              italic="DejaVu-Oblique", boldItalic="DejaVu-Bold")

INK = colors.HexColor("#1b2733")
MUTED = colors.HexColor("#5b6b7b")
ACCENT = colors.HexColor("#2f6f6b")
ACCENT_DK = colors.HexColor("#234f4c")
RULE = colors.HexColor("#d6dde3")
CODE_BG = colors.HexColor("#f3f6f8")
ROW_ALT = colors.HexColor("#f7f9fa")

ss = getSampleStyleSheet()


def style(name, **kw):
    base = dict(fontName="DejaVu", textColor=INK, fontSize=10.5, leading=15)
    base.update(kw)
    return ParagraphStyle(name, **base)


S = {
    "title": style("t", fontName="DejaVu-Bold", fontSize=25, leading=29),
    "subtitle": style("st", fontSize=13, leading=18, textColor=ACCENT_DK),
    "h1": style("h1", fontName="DejaVu-Bold", fontSize=15, leading=19, textColor=ACCENT_DK,
                spaceBefore=16, spaceAfter=6),
    "h2": style("h2", fontName="DejaVu-Bold", fontSize=11.5, leading=15, textColor=INK,
                spaceBefore=10, spaceAfter=3),
    "body": style("b", spaceAfter=6),
    "bullet": style("bl", leading=14, spaceAfter=2),
    "cell": style("c", fontSize=8.5, leading=11.5),
    "cellb": style("cb", fontSize=8.5, leading=11.5, fontName="DejaVu-Bold"),
    "cellh": style("ch", fontSize=8.5, leading=11.5, fontName="DejaVu-Bold", textColor=colors.white),
    "mono": style("mono", fontName="DejaVuMono", fontSize=8, leading=11.5),
    "note": style("n", fontSize=9.5, leading=13, textColor=MUTED, fontName="DejaVu-Oblique"),
}

story: list = []


def h1(t): story.append(Paragraph(t, S["h1"]))
def h2(t): story.append(Paragraph(t, S["h2"]))
def p(t): story.append(Paragraph(t, S["body"]))
def note(t): story.append(Paragraph(t, S["note"]))
def sp(h=6): story.append(Spacer(1, h))
def pb(): story.append(PageBreak())
def rule(): story.append(HRFlowable(width="100%", thickness=0.6, color=RULE,
                                     spaceBefore=6, spaceAfter=6))


def bullets(items):
    li = [ListItem(Paragraph(t, S["bullet"]), leftIndent=12, value="•") for t in items]
    story.append(ListFlowable(li, bulletType="bullet", bulletColor=ACCENT,
                              bulletFontName="DejaVu", start="•", leftIndent=10))


def code(text):
    para = Paragraph(text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                     .replace("\n", "<br/>").replace(" ", "&nbsp;"), S["mono"])
    t = Table([[para]], colWidths=[6.7 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CODE_BG), ("BOX", (0, 0), (-1, -1), 0.5, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(t)
    sp(6)


def table(header, rows, widths, font="cell"):
    data = [[Paragraph(c, S["cellh"]) for c in header]]
    for r in rows:
        data.append([Paragraph(str(c), S[font]) for c in r])
    t = Table(data, colWidths=widths, repeatRows=1)
    ts = [("BACKGROUND", (0, 0), (-1, 0), ACCENT), ("LINEBELOW", (0, 0), (-1, 0), 0.6, ACCENT_DK),
          ("GRID", (0, 0), (-1, -1), 0.4, RULE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
          ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
    for i in range(1, len(data)):
        if i % 2 == 0:
            ts.append(("BACKGROUND", (0, i), (-1, i), ROW_ALT))
    t.setStyle(TableStyle(ts))
    story.append(t)
    sp(8)


def attr_block(title, rows):
    """Render a spec block: bold h2 + 2-col (attribute | value) table."""
    h2(title)
    data = [[Paragraph(k, S["cellb"]), Paragraph(v, S["cell"])] for k, v in rows]
    t = Table(data, colWidths=[1.35 * inch, 5.35 * inch])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, RULE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (0, -1), ROW_ALT),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    sp(8)


def model_table(name, fields):
    h2(f"{name}")
    table(["Field", "Type", "Notes"], fields, [1.7 * inch, 1.35 * inch, 3.65 * inch])


# ═══════════════════════════════════════════════════════════════════════════
#  CONTENT DATA
# ═══════════════════════════════════════════════════════════════════════════

DATA_MODELS = [
    ("OfferBrief (input)", [
        ["offer_name", "string", "Required. Slugs the output folder."],
        ["avatar", "string", "Required. Who the product is for."],
        ["main_problem", "string", "Required."],
        ["main_promise", "string", "Required. Gated at product_promise."],
        ["core_product_type", "string", "Required. e.g. mini-course, template pack."],
        ["core_deliverables", "list[str|obj]", "Required, ≥1 item."],
        ["bonus_deliverables", "list[str|obj]", "May be empty."],
        ["order_bump", "string|object", "Required; use 'none' if absent."],
        ["future_upsells", "list", "May be empty. Planned only."],
        ["buyer_objections", "list[str]", "Required, ≥1 item."],
        ["roi_logic", "string", "Required."],
        ["tone", "string", "Required. Voice for all copy."],
        ["ethical_boundaries", "string", "Required. Hard limits."],
        ["delivery_format", "string", "Required."],
        ["extras", "object", "Optional. Preserved, not validated."],
    ]),
    ("ProductPackage", [
        ["product_outline", "string", "2-4 sentence overview."],
        ["modules", "list[Module]", "Module = {title, outcome, lessons[]}."],
        ["modules[].lessons", "list[Lesson]", "Lesson = {title, teaching_point, format}."],
        ["worksheets", "list[{name,purpose}]", ""],
        ["templates", "list[{name,purpose}]", ""],
        ["quick_start_guide", "string", "First-win path, &lt;30 min."],
        ["customer_success_path", "list[{milestone, how_they_know_they_hit_it}]", ""],
        ["delivery_instructions", "string", "Matched to delivery_format."],
    ]),
    ("CoreDeliverable", [
        ["name", "string", ""],
        ["purpose", "string", "Job it does for the buyer."],
        ["format", "string", "Concrete artifact type."],
        ["problem_solved", "string", ""],
        ["completion_criteria", "string", "How buyer knows they're done."],
        ["delivery_asset", "string", "Artifact + how delivered."],
    ]),
    ("BonusDeliverable", [
        ["name", "string", ""],
        ["purpose", "string", "Acceleration or objection removal."],
        ["objection_removed", "string", "Ties to buyer_objections."],
        ["why_it_belongs_as_a_bonus", "string", "Why not core / not standalone."],
        ["delivery_asset", "string", ""],
    ]),
    ("OrderBump", [
        ["product", "string", "'none' if no bump."],
        ["copy", "string", "On-checkout copy, in Tone, ethical."],
        ["positioning", "string", "Why it's the obvious add-on; stays subordinate."],
        ["delivery_method", "string", ""],
    ]),
    ("ReelIdea", [
        ["index", "int", "1-based, unique across batches."],
        ["angle", "string", "Psychological angle, 2-4 words."],
        ["hook", "string", "Scroll-stopping opener."],
        ["core_idea", "string", "What the reel shows/says."],
        ["cta_keyword", "string", "Single DM keyword it drives to."],
    ]),
    ("ReelScript", [
        ["index", "int", "Matches source ReelIdea."],
        ["hook", "string", "Spoken + on-screen opener (0-3s)."],
        ["script", "string", "Full voiceover, line by line."],
        ["b_roll_or_visual_notes", "string", "On-screen per part."],
        ["on_screen_text", "list[str]", "Caption overlays in sequence."],
        ["spoken_cta", "string", "Closing line to the keyword."],
        ["cta_keyword", "string", ""],
    ]),
    ("CarouselOutline", [
        ["index", "int", ""],
        ["angle", "string", ""],
        ["hook_slide", "string", "Slide 1 headline."],
        ["slides", "list[{headline, body}]", "Body slides."],
        ["cta_slide", "string", "Final slide CTA."],
        ["cta_keyword", "string", ""],
    ]),
    ("SocialPost (pitch / nurture / objection / proof)", [
        ["index", "int", ""],
        ["post_type", "enum", "direct_pitch | nurture | objection | proof."],
        ["hook", "string", "First line."],
        ["body", "string", "Caption body."],
        ["cta", "string|null", "null for nurture."],
        ["cta_keyword", "string|null", ""],
        ["objection_addressed", "string?", "objection posts only."],
        ["proof_type", "enum?", "proof only: testimonial|result|process|screenshot_prompt."],
        ["proof_content", "string?", "proof only; screenshot_prompt = what to capture."],
    ]),
    ("StoryPrompt", [
        ["index", "int", ""],
        ["frame_type", "enum", "poll | question | quiz | real_countdown | dm_trigger."],
        ["prompt_text", "string", ""],
        ["sticker", "string", "Sticker/interaction to use."],
        ["cta_keyword", "string|null", ""],
    ]),
    ("CTACaption / DMKeywordPrompt / ManyChatCopy", [
        ["cta_captions", "list[{index, for_asset, caption, keyword}]", "for_asset: reel|carousel|post."],
        ["dm_keyword_prompts", "list[{keyword, triggered_by, intent, first_response_ref}]", ""],
        ["manychat", "{flow_name, trigger_keyword, steps[], handoff_condition}",
         "step = {order, message, quick_replies[], delay}."],
    ]),
    ("DMSequence", [
        ["keyword_list", "list[str]", "All keywords used across content."],
        ["initial_dm", "string", "Delivers promised value + qualifies."],
        ["follow_ups", "list[{order, message, send_after}]", ""],
        ["checkout_messages", "list[str]", ""],
        ["reminder_messages", "list[{order, message, send_after}]", ""],
        ["objection_responses", "list[{objection, response}]", "Maps buyer_objections."],
    ]),
    ("CheckoutAssets", [
        ["checkout_page_copy", "string", ""],
        ["product_description", "string", ""],
        ["bullet_stack", "list[str]", "Benefit bullets."],
        ["bonus_copy", "string", "Checkout bonus stack copy."],
        ["order_bump_copy", "string", ""],
        ["thank_you_page", "string", ""],
        ["delivery_email", "{subject, body}", ""],
        ["purchase_confirmation", "{subject, body}", ""],
        ["follow_up_emails", "list[{order, subject, body, send_after}]", ""],
        ["refund_instructions", "string", "Respects ethical_boundaries."],
    ]),
    ("Finding (validator output)", [
        ["check", "string", "Check identifier."],
        ["severity", "enum", "blocking | warning | info."],
        ["message", "string", "What's wrong."],
        ["recommended_fix", "string", "Actionable remedy."],
    ]),
]

# name, purpose, qty, batching, schema, constraints, funnel_role
ASSET_SPECS = [
    ("Reel Ideas", "Top-of-funnel hooks that pull the avatar toward the promise and set up a keyword.",
     "30", "3 batches of 10; start_index offsets the prompt so batches don't repeat angles.",
     "ReelIdea[]", "Vary angle across the set (pain, myth-bust, quick win, before/after, mistake, "
     "contrarian, day-in-life, results). Each maps to exactly one DM keyword.",
     "Attention → keyword capture."),
    ("Reel Scripts", "Shootable script for each idea.",
     "30", "Scripts generated per idea-batch (10 at a time) from the ideas array.",
     "ReelScript[]", "20-45s spoken. Hook in first 3s. Ethical CTA to comment/DM keyword. "
     "No unsupported claims.", "Attention → keyword capture."),
    ("Carousel Outlines", "Authority-building teaching carousels.",
     "15", "2 batches (~8 + 7).", "CarouselOutline[]",
     "One idea taught deeply per carousel; 6-10 slides; final slide CTA to keyword.",
     "Trust → keyword capture."),
    ("Direct Pitch Posts", "Posts that name the offer and outcome plainly.",
     "15", "2 batches.", "SocialPost[] (post_type=direct_pitch)",
     "Plain-spoken offer + outcome + CTA. No hype, no fake scarcity.", "Consideration → CTA."),
    ("Nurture Posts", "Relate and build trust; no ask.",
     "15", "2 batches.", "SocialPost[] (post_type=nurture)",
     "cta and cta_keyword are null. Story/relatability, ties to the avatar's world.", "Trust."),
    ("Objection Posts", "Dissolve one specific hesitation each.",
     "10", "1 batch.", "SocialPost[] (post_type=objection)",
     "Each post maps to one item in buyer_objections via objection_addressed.", "De-risk → CTA."),
    ("Proof Posts", "Show substantiable evidence.",
     "10", "1 batch.", "SocialPost[] (post_type=proof)",
     "proof_type ∈ {testimonial, result, process, screenshot_prompt}. Only claims that can be "
     "substantiated; screenshot_prompt states what real asset to capture — never fabricated.",
     "Credibility → CTA."),
    ("Story Prompts", "Quick engagement + keyword triggers for Stories.",
     "10", "1 batch.", "StoryPrompt[]",
     "frame_type drives the interaction; real_countdown only for genuine deadlines.", "Engagement."),
    ("CTA Captions", "Reusable caption CTAs per asset type.",
     "set", "1 call.", "cta_captions[]", "Map to reel/carousel/post; each names its keyword.",
     "Conversion nudge."),
    ("DM Keyword Prompts", "The keyword→intent map.",
     "set", "1 call.", "dm_keyword_prompts[]",
     "Each keyword ties to the content that triggers it and the DM entry point.", "Capture routing."),
    ("ManyChat Copy", "Automation flow copy for the DM tool.",
     "set", "1 call.", "manychat{}",
     "Steps with quick replies + delays; explicit handoff_condition to a human for nuance.",
     "Automated selling."),
    ("Product Package", "The core product itself.",
     "1", "1 call.", "ProductPackage",
     "Fully delivers main_promise; completable at a low-ticket price; no filler modules.",
     "The product."),
    ("Core Deliverables", "Each brief core deliverable, fully specified.",
     "= brief count", "1 call.", "CoreDeliverable[]",
     "Does not invent or drop deliverables; each has completion_criteria.", "Delivery."),
    ("Bonus Deliverables", "Each brief bonus, fully specified.",
     "= brief count", "1 call.", "BonusDeliverable[]",
     "Never more valuable/desirable than core; each removes a named objection.", "Objection removal."),
    ("Order Bump", "The checkout add-on.",
     "1", "1 call.", "OrderBump",
     "Complements, never replaces the core; small fraction of core price.", "AOV lift."),
    ("DM Automation Sequence", "The conversation that sells.",
     "1", "1 call.", "DMSequence",
     "Value-first, non-spammy; objection_responses map buyer_objections; human handoff implied.",
     "Selling. Gated: dm_automation."),
    ("Checkout Assets", "All checkout + delivery copy (10 sub-assets).",
     "1 bundle", "1-2 calls (may split page-copy from emails).", "CheckoutAssets",
     "Accurate to the product; ethical refund terms; delivery matches delivery_format.",
     "Conversion + delivery. Gated: checkout_copy."),
]

# check, method, trigger, severity, recommended_fix
VALIDATOR_CHECKS = [
    ("duplicate_deliverables", "Structural (difflib ratio ≥ 0.85 on names across core+bonus)",
     "Two deliverables read as near-identical", "warning", "Merge, or differentiate the problem each solves."),
    ("missing_deliverables", "Structural",
     "core_deliverables empty OR product_package.modules empty (blocking); no quick_start (warning)",
     "blocking / warning", "Regenerate the empty section (use --force)."),
    ("bonus_stronger_than_core", "AI judge (product_package + core + bonuses)",
     "A bonus is more valuable/desirable than the core", "warning→blocking",
     "Rebalance or demote the bonus; strengthen the core."),
    ("order_bump_too_valuable", "AI judge (order_bump + core)",
     "The bump rivals or could replace the core", "warning→blocking", "Shrink the bump's scope."),
    ("generic_ai_content", "AI judge (sample of content assets)",
     "Copy is templated / not specific to this avatar+promise", "warning",
     "Regenerate specified to the avatar and promise."),
    ("unsupported_claims", "AI judge (all copy; special focus health + income/ROI)",
     "Misleading, exaggerated, unsupported, or fabricated income/health claims", "blocking",
     "Remove or substantiate; caveat honestly."),
    ("support_burden", "AI judge (deliverables)",
     "A deliverable likely to spike confusion / support tickets", "warning", "Simplify the deliverable."),
    ("promise_misalignment", "AI judge (deliverables vs main_promise)",
     "A deliverable doesn't serve the Main Promise", "warning", "Retie to the promise or cut it."),
]

# stage, produces, gate
PIPELINE_STAGES = [
    ["1", "Brief load + completeness", "validated brief (Phase 2)", "— hard reject if incomplete"],
    ["2", "Brief confirm", "offer_brief.json", "offer_brief"],
    ["3", "Promise confirm", "— (surfaces promise)", "product_promise"],
    ["4", "Product package", "product_package.json/.md", "—"],
    ["5", "Core deliverables", "core_deliverables.json/.md", "core_deliverables"],
    ["6", "Bonus deliverables", "bonus_deliverables.json/.md", "bonus_deliverables"],
    ["7", "Order bump", "order_bump.json/.md", "order_bump"],
    ["8", "Content pack", "reels · carousels · posts · stories · ctas · keywords · manychat", "—"],
    ["9", "DM automation", "dm_automation.json/.md", "dm_automation"],
    ["10", "Checkout assets", "checkout.json/.md", "checkout_copy"],
    ["11", "Hierarchy validation", "hierarchy_validation.json/.md (Phase 4)",
     "hierarchy_validation · health_claims · roi_claims"],
    ["12", "Final", "final summary", "final_product"],
]

CLI = [
    ["validate --brief PATH", "Phase 2 check only; no API calls.",
     "'Brief is complete' or numbered missing list.", "0 ok · 1 incomplete"],
    ["generate --brief PATH [--force]", "Run the pipeline to the next pending gate.",
     "Writes assets; stops at first pending gate with review path.",
     "0 done · 3 paused at gate · 1 incomplete · 4 blocking findings"],
    ["approve --offer SLUG --gate GATE", "Approve one gate.", "Updates gates.json.", "0 · 2 bad gate"],
    ["reject --offer SLUG --gate GATE", "Reject one gate (blocks progression).", "Updates gates.json.", "0"],
    ["status --offer SLUG", "Show gate states.", "Gate table (pending/approved/rejected).", "0"],
    ["regenerate --brief PATH --stage NAME", "Force-regenerate one stage.", "Rewrites that stage's files.", "0"],
]

CONFIG = [
    ["CLAUDE_MODEL", "(blank)", "Optional. Pin a model, else use the Claude Code session default."],
    ["CLAUDE_TIMEOUT_SECONDS", "300", "Max wait per generation call."],
    ["LLM_MAX_TOKENS", "8000", "Per-call output ceiling."],
    ["LLM_TEMPERATURE", "0.7", "Lower for more deterministic runs."],
    ["OUTPUT_DIR", "output", "Per-offer asset folders."],
    ["BRIEFS_DIR", "briefs", "Input briefs."],
    ["METHODOLOGY_NOTES_PATH", "(blank)", "Optional file of your extracted course notes; injected as grounding."],
]

FAILURES = [
    ["Incomplete brief", "IncompleteBriefError", "Refuse to run; print the missing-field list. Exit 1."],
    ["LLM / network error", "LLMError", "Normalized + raised; already-generated stages stay cached on disk."],
    ["Bad JSON from model", "LLMError (after repair)", "Strip fences, extract outermost JSON; if still bad, error loudly."],
    ["Blocking validation", "GateBlocked (hierarchy)", "Stop before the gate; write fix list; re-run --force after edits."],
    ["Gate pending", "GateBlocked", "Pause (not an error). Print review path + approve command. Exit 3."],
]

# ═══════════════════════════════════════════════════════════════════════════
#  TITLE
# ═══════════════════════════════════════════════════════════════════════════
sp(40)
story.append(HRFlowable(width="38%", thickness=3, color=ACCENT, spaceAfter=14, hAlign="LEFT"))
story.append(Paragraph("AI Product Production Factory", S["title"]))
sp(6)
story.append(Paragraph("Detailed Technical Specification — Implementation Contract", S["subtitle"]))
sp(22)
meta = [
    ["Owner", "Jon — FascinateCopy"],
    ["Document", "Implementation-level specification (build directly against this)"],
    ["Version", "1.1 — Claude Code runtime; scope Phases 3–4"],
    ["Build scope", "Phases 3–4 (+ brief input contract): asset generation · hierarchy validation · gated approval"],
    ["Deferred", "Phases 5–6 (dashboard, weekly report) — Appendix A; need a live product's data"],
    ["Stack", "Python 3.11 · Claude Code CLI (Max login, no API key) · file-based gates"],
    ["Upstream / downstream", "Grand Slam Offer GPT  →  this system  →  Maria Wendt Sales Machine"],
]
mt = Table([[Paragraph(k, S["cellb"]), Paragraph(v, S["cell"])] for k, v in meta],
           colWidths=[1.7 * inch, 5.0 * inch])
mt.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
                        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                        ("LEFTPADDING", (0, 0), (0, -1), 0)]))
story.append(mt)
sp(16)
h2("Contents")
bullets([
    "1 Overview &amp; scope · 2 Architecture · 3 Asset hierarchy model",
    "4 Data models (every artifact schema)",
    "5 Offer Brief contract (Phase 2) · 6 Generation engine (Phase 3)",
    "7 Asset generation catalog — per-asset specs",
    "8 Hierarchy validator (Phase 4) · 9 Approval gates · 10 Pipeline",
    "11 CLI · 12 Output layout · 13 Configuration · 14 Failure taxonomy · 15 Non-functional",
    "16 Constraints · 17 Project structure · 18 Setup · 19 Human-only · 20 Roadmap · Appendix A (5–6)",
])
pb()

# ═══════════════════════════════════════════════════════════════════════════
#  1-3 (condensed front matter)
# ═══════════════════════════════════════════════════════════════════════════
h1("1. Overview &amp; Scope")
p("The Factory takes one input — an approved <b>Offer Brief</b> from the Grand Slam Offer GPT — and "
  "produces the complete, hierarchy-checked asset package needed to sell and deliver a low-ticket "
  "digital product through the Maria Wendt Sales Machine. Target: ~90% AI production, ~10% human "
  "review at defined gates. It never creates offers and never publishes; it generates and gates.")
p("<b>This build is Phases 1–4</b>: (1) methodology grounding, (2) the brief contract + validator, "
  "(3) the asset generation engine, (4) the hierarchy validator — brief in, full asset package out, "
  "gated for approval. <b>Phases 5–6</b> (live-campaign dashboard + weekly report) are deferred to "
  "Appendix A: they measure a running funnel and have no data to work on until a product is live.")

h1("2. Architecture")
p("A Python engine is the source of truth: it owns the brief contract, the generation prompts, the "
  "validator, the gate store, and output rendering. Approval is file-based (a JSON gate store), which "
  "is auditable and later swappable for a Google Sheet cell without changing pipeline code. Claude is "
  "Generation runs through the Claude Code CLI (claude -p) on the machine\u2019s logged-in Max "
  "account \u2014 no API key and no per-call billing.")
table(["Component", "Responsibility"],
      [["config.py", "Typed, .env-driven settings; fails loud on a missing key."],
       ["factory/brief.py", "Phase 2: OfferBrief schema + completeness validation + rejection."],
       ["factory/llm.py", "Claude client wrapper; JSON-mode + repair; normalized LLMError."],
       ["factory/prompts/*", "Phase 1 grounding + per-asset prompt builders."],
       ["factory/generators.py", "Phase 3: generate-and-normalize functions per asset."],
       ["factory/hierarchy_validator.py", "Phase 4: structural + AI checks → Findings."],
       ["factory/gates.py", "Gate store + state machine + GateBlocked."],
       ["factory/output.py", "Render each artifact to json (truth) + md (review)."],
       ["factory/pipeline.py", "Ordered, resumable, gated orchestration."],
       ["run.py", "CLI surface."]],
      [1.9 * inch, 4.8 * inch])

h1("3. Asset Hierarchy Model &amp; Invariants")
bullets([
    "<b>Core Product</b> ▸ <b>Core Deliverables</b> ▸ <b>Bonus Deliverables</b> ▸ <b>Order Bump</b> "
    "▸ <b>Future Upsells</b> (planned only) ▸ Content ▸ DM ▸ Checkout ▸ Delivery assets.",
    "Bonuses never outshine the core. The bump never replaces the core. Upsells are planned, not "
    "built, until validation. Every deliverable serves the promise. No duplicates.",
])
note("These invariants are enforced twice: as generation-time guardrails in every prompt, and as "
     "post-generation checks in the hierarchy validator (§8).")
pb()

# ═══════════════════════════════════════════════════════════════════════════
#  4. DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════
h1("4. Data Models")
p("Every generated artifact conforms to one of these schemas. Generators request strict JSON in "
  "these shapes; the output layer renders each to <font face='DejaVuMono'>&lt;name&gt;.json</font> "
  "(machine truth) and <font face='DejaVuMono'>&lt;name&gt;.md</font> (human review).")
for name, fields in DATA_MODELS:
    model_table(name, fields)
pb()

# ═══════════════════════════════════════════════════════════════════════════
#  5. OFFER BRIEF CONTRACT
# ═══════════════════════════════════════════════════════════════════════════
h1("5. Offer Brief Contract (Phase 2)")
p("Input is one JSON object matching OfferBrief (§4). Validation rules:")
bullets([
    "String fields must be present and non-blank.",
    "core_deliverables and buyer_objections must be lists with ≥1 item.",
    "bonus_deliverables and future_upsells may be empty lists.",
    "order_bump is required; the literal 'none' is valid.",
    "Unknown fields are preserved under extras and never block validation.",
])
p("<b>Rejection behaviour:</b> if any rule fails, the Factory raises IncompleteBriefError and returns "
  "a numbered list of exactly what's missing, to be sent back to the Grand Slam Offer GPT. No "
  "generation runs on an incomplete brief.")
h2("Rejection output (example)")
code("Offer Brief is incomplete. Send it back to the Grand Slam Offer GPT with these missing items:\n"
     "  - Missing: Main Promise.\n"
     "  - Missing or empty: Core Deliverables (needs at least one item).\n"
     "  - Missing: ROI Logic.")
h2("Minimal valid brief (example)")
code('{\n'
     '  "offer_name": "The 20-Minute Reels System",\n'
     '  "avatar": "Time-poor coaches with <5k followers",\n'
     '  "main_problem": "They post but nothing converts to DMs or sales",\n'
     '  "main_promise": "Book 5 sales conversations a week from Reels",\n'
     '  "core_product_type": "mini-course + templates",\n'
     '  "core_deliverables": ["Reel hook framework", "Keyword-to-DM setup"],\n'
     '  "bonus_deliverables": ["30 done-for-you hooks"],\n'
     '  "order_bump": "Caption pack ($9)",\n'
     '  "future_upsells": ["Group coaching"],\n'
     '  "buyer_objections": ["No time", "Tried Reels before, failed"],\n'
     '  "roi_logic": "One client pays back the price 50x",\n'
     '  "tone": "Warm, direct, no hype",\n'
     '  "ethical_boundaries": "No income guarantees",\n'
     '  "delivery_format": "Google Drive folder + PDF"\n'
     '}')
pb()

# ═══════════════════════════════════════════════════════════════════════════
#  6. GENERATION ENGINE
# ═══════════════════════════════════════════════════════════════════════════
h1("6. Generation Engine (Phase 3)")
h2("Prompt architecture")
p("Every generator builds a (system, user) pair. The <b>system</b> prompt is assembled once per role: "
  "role line + methodology grounding + hierarchy rules + ethics rules + (optional) injected course "
  "notes. The <b>user</b> prompt carries the approved brief as JSON, the task, the exact output schema, "
  "and a strict 'JSON only — no fences, no commentary' instruction.")
code("system = role + METHODOLOGY_BASE + HIERARCHY_RULES + ETHICS_RULES + [course_notes]\n"
     "user   = brief_context(brief) + task + output_schema + \"Respond with ONLY valid JSON\"")
h2("LLM call contract")
bullets([
    "Generation shells out to `claude -p --output-format json` on the Max login; the `.result` "
    "field is parsed. No API key. --bare is deliberately NOT used (it would force a key).",
    "generate() returns text; generate_json() strips ``` fences and parses; on failure it extracts "
    "the outermost JSON object/array; if that fails it raises LLMError.",
    "All provider/network errors are normalized to LLMError at the client boundary.",
])
h2("Batching &amp; volume")
p("High-volume content is generated in batches to protect quality and avoid truncation. Reel ideas "
  "use a start_index offset so batches don't repeat; scripts are generated per idea-batch. "
  "Normalizers tolerate {\"items\": [...]} wrappers and drop non-dict entries.")
h2("Idempotency &amp; resume")
p("Each stage writes <font face='DejaVuMono'>&lt;stage&gt;.json</font>. On re-run, an existing file is "
  "loaded instead of regenerated (no wasted tokens) unless --force is passed. This is what makes the "
  "gated pipeline cheap to resume after each approval.")
pb()

# ═══════════════════════════════════════════════════════════════════════════
#  7. ASSET GENERATION CATALOG
# ═══════════════════════════════════════════════════════════════════════════
h1("7. Asset Generation Catalog (per-asset specs)")
p("Each block is the contract for one generator: what it produces, how much, batching, output schema "
  "(see §4), the key constraints its prompt enforces, and its role in the funnel.")
for name, purpose, qty, batching, schema, constraints, role in ASSET_SPECS:
    attr_block(name, [
        ("Purpose", purpose),
        ("Quantity", qty),
        ("Batching", batching),
        ("Output schema", schema),
        ("Key constraints", constraints),
        ("Funnel role", role),
    ])
pb()

# ═══════════════════════════════════════════════════════════════════════════
#  8. HIERARCHY VALIDATOR
# ═══════════════════════════════════════════════════════════════════════════
h1("8. Hierarchy Validator (Phase 4)")
p("Runs after generation. Structural checks are deterministic Python; judgment checks call Claude with "
  "a validator system prompt and the generated assets, returning Finding[] (see §4). Aggregation: "
  "result.ok == (no blocking findings). The hierarchy_validation gate cannot be approved while any "
  "blocking finding stands — the pipeline writes the fix list and stops; fix, then re-run with --force.")
table(["Check", "Method", "Trigger", "Severity", "Recommended fix"],
      [[c, m, t, s, f] for c, m, t, s, f in VALIDATOR_CHECKS],
      [1.15 * inch, 1.55 * inch, 1.7 * inch, 0.85 * inch, 1.45 * inch])
h2("AI judge output contract")
code('[ { "check": "bonus_stronger_than_core", "severity": "warning",\n'
     '    "message": "...", "recommended_fix": "..." } ]   // [] = all clear')
pb()

# ═══════════════════════════════════════════════════════════════════════════
#  9. APPROVAL GATES
# ═══════════════════════════════════════════════════════════════════════════
h1("9. Approval Gates")
p("A gate is a named checkpoint. State lives in <font face='DejaVuMono'>_gates/gates.json</font> as "
  "gate → pending | approved | rejected. The pipeline writes a REVIEW__&lt;gate&gt;.md artifact at each "
  "gate and refuses to pass until the gate is approved (raises GateBlocked). Approving is one CLI "
  "command; the same interface can later read a Google Sheet cell instead of a file.")
table(["#", "Gate", "Guards", "Approve after reviewing…"],
      [["1", "offer_brief", "Right, complete input", "offer_brief.json"],
       ["2", "product_promise", "The transformation", "REVIEW__product_promise.md"],
       ["3", "core_deliverables", "Core complete & on-promise", "core_deliverables.md"],
       ["4", "bonus_deliverables", "Bonuses stay subordinate", "bonus_deliverables.md"],
       ["5", "order_bump", "Bump subordinate & logical", "order_bump.md"],
       ["6", "dm_automation", "On-brand, non-spammy DMs", "dm_automation.md"],
       ["7", "checkout_copy", "Accurate, ethical checkout", "checkout.md"],
       ["8", "hierarchy_validation", "No blocking issues", "hierarchy_validation.md"],
       ["9", "health_claims", "No unsupported health claims", "hierarchy_validation.md"],
       ["10", "roi_claims", "No unsupported income/ROI claims", "hierarchy_validation.md"],
       ["11", "final_product", "Whole package production-ready", "final summary"]],
      [0.35 * inch, 1.35 * inch, 2.2 * inch, 2.8 * inch])
note("Gate set is fixed; the live ordering is defined by the pipeline sequence in §10.")

# ═══════════════════════════════════════════════════════════════════════════
#  10. PIPELINE
# ═══════════════════════════════════════════════════════════════════════════
h1("10. Pipeline Sequence")
p("The orchestrator advances until the first pending gate, writes that gate's review file, and stops "
  "with instructions. Approve, re-run, and it resumes from cache. --force regenerates a stage.")
table(["#", "Stage", "Produces", "Gate before continuing"], PIPELINE_STAGES,
      [0.35 * inch, 1.55 * inch, 2.9 * inch, 1.9 * inch])
pb()

# ═══════════════════════════════════════════════════════════════════════════
#  11-15
# ═══════════════════════════════════════════════════════════════════════════
h1("11. CLI Reference")
table(["Command", "Does", "Output", "Exit codes"], CLI,
      [1.95 * inch, 1.55 * inch, 1.95 * inch, 1.25 * inch])

h1("12. Output Layout (per run)")
code("output/<offer-slug>/\n"
     "  offer_brief.json\n"
     "  product_package.json | .md      core_deliverables.json | .md\n"
     "  bonus_deliverables.json | .md   order_bump.json | .md\n"
     "  reels.json | .md   carousels.json | .md   posts.json | .md\n"
     "  story_prompts.json | .md   cta_captions.json | .md\n"
     "  dm_keyword_prompts.json | .md   manychat.json | .md\n"
     "  dm_automation.json | .md   checkout.json | .md\n"
     "  hierarchy_validation.json | .md\n"
     "  _gates/\n"
     "    gates.json\n"
     "    REVIEW__<gate>.md ...")

h1("13. Configuration Reference (.env)")
table(["Variable", "Default", "Meaning"], CONFIG, [2.0 * inch, 1.35 * inch, 3.35 * inch])

h1("14. Failure Taxonomy")
table(["Failure", "Type", "Behaviour"], FAILURES, [1.55 * inch, 1.75 * inch, 3.4 * inch])

h1("15. Non-Functional Notes")
bullets([
    "<b>Cost/volume:</b> a full product run is ~25–31 Claude Code calls. Covered by the Max "
    "subscription (no per-call API billing). Max supports 1–3 steady headless agents; heavier "
    "parallelism would need an API key instead.",
    "<b>Rate limits &amp; retries:</b> calls run sequentially; add exponential-backoff retry on 429/5xx "
    "(to build). Cached stages mean a mid-run failure never loses completed work.",
    "<b>Determinism:</b> temperature 0.7 is non-deterministic; lower it for reproducibility. Caching "
    "gives stable outputs across resume runs.",
])
pb()

# ═══════════════════════════════════════════════════════════════════════════
#  16-20
# ═══════════════════════════════════════════════════════════════════════════
h1("16. Constraints &amp; Ethics")
bullets([
    "Never invent offers; work strictly from the approved brief.",
    "Never replace the Sales Machine — only accelerate production feeding into it.",
    "No fake urgency/scarcity; deadlines and limits must be real.",
    "No misleading/exaggerated/unsupported claims; no fabricated income or health claims.",
    "No spammy automation; DMs deliver value and respect the recipient.",
    "Products must be genuinely valuable and production-ready.",
    "The brief's ethical_boundaries override defaults where stricter.",
])

h1("17. Project Structure")
code(
    "product-factory/\n"
    "├── run.py                     CLI\n"
    "├── config.py                  .env-driven settings (Claude only)\n"
    "├── requirements.txt           .env.example\n"
    "├── briefs/example_offer_brief.json\n"
    "├── docs/build_spec.py         regenerates this PDF\n"
    "├── factory/\n"
    "│   ├── brief.py               Phase 2\n"
    "│   ├── llm.py                 Claude client\n"
    "│   ├── generators.py          Phase 3\n"
    "│   ├── hierarchy_validator.py Phase 4\n"
    "│   ├── gates.py  output.py  pipeline.py\n"
    "│   └── prompts/  (methodology, product_package, content_pack, dm_automation, checkout)\n"
    "└── output/                    generated assets per offer\n"
)

h1("18. Setup &amp; Run (Windows / PowerShell)")
code("py -3.11 -m venv .venv\n"
     ".\\.venv\\Scripts\\Activate.ps1\n"
     "pip install -r requirements.txt\n"
     "npm install -g @anthropic-ai/claude-code   # then run `claude` once to log in\n"
     "Copy-Item .env.example .env      # no API key needed\n"
     "python run.py doctor             # verify Claude Code is installed + logged in\n"
     "python run.py validate --brief .\\briefs\\example_offer_brief.json\n"
     "python run.py generate --brief .\\briefs\\example_offer_brief.json\n"
     "python run.py approve  --offer <slug> --gate offer_brief\n"
     "python run.py generate --brief .\\briefs\\example_offer_brief.json   # resumes")
note("Verify at each step: (.venv) in the prompt; 'Brief is complete'; output\\<slug>\\ fills with "
     "json+md; the run stops at the first gate with a review path.")

h1("19. What Only You Can Do")
bullets([
    "Paste your Anthropic API key into .env (secrets never enter source or the tool).",
    "Provide a real approved Offer Brief from the Grand Slam Offer GPT (example ships for testing).",
    "Optionally paste extracted Maria Wendt course notes to ground generation.",
    "Authenticate delivery/marketing tools (Instagram, ManyChat, checkout, email, Google).",
    "Click the approval gates — the 10% human review.",
])

h1("20. Build Roadmap (Phases 1–4)")
table(["Stage", "Scope", "Status"],
      [["Engine spine", "config · brief · llm · pipeline · gates · output", "Done"],
       ["Generation v1", "product · core · bonus · bump · reels", "Done"],
       ["Generation v2", "carousels · post types · stories · CTAs · keywords · ManyChat", "Next"],
       ["DM + checkout", "DM sequence · all checkout/delivery assets", "Next"],
       ["Validator wiring", "AI checks on the full asset set", "Next"],
       ["Handoff", "HANDOFF.md — 1-hour fresh-machine setup", "Last"]],
      [1.35 * inch, 3.75 * inch, 1.6 * inch])
note("Deferred (needs a live product): Phase 5 dashboard, Phase 6 weekly report — see Appendix A.")
pb()

# ═══════════════════════════════════════════════════════════════════════════
#  APPENDIX A
# ═══════════════════════════════════════════════════════════════════════════
h1("Appendix A — Deferred: Phases 5–6")
p("Included for the full-project picture. Not built in this cycle — both measure a live campaign and "
  "have no data until a product is published and selling.")
h2("Phase 5 — Tracking Dashboard (Google Sheet from an xlsx builder)")
bullets(["Product · avatar · price · core deliverables · bonuses · order bump",
         "Content published · reel views · carousel engagement",
         "DMs · keyword triggers · checkout clicks",
         "Purchases · order-bump purchases · revenue · refund rate",
         "Support issues · customer feedback"])
h2("Phase 6 — Weekly Optimization Report (from dashboard data)")
bullets(["Best-performing content · highest-converting DMs · common objections",
         "Checkout improvements · bonus effectiveness · core product performance",
         "Kill / Improve / Scale recommendations",
         "Upsell-unlock recommendation (are validation criteria met yet?)"])
note("Trigger: first product live → build Phase 5 → accumulate data → build Phase 6.")


# --- build -------------------------------------------------------------------
def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("DejaVu", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(0.9 * inch, 0.55 * inch,
                      "AI Product Production Factory — Detailed Specification v1.1")
    canvas.drawRightString(LETTER[0] - 0.9 * inch, 0.55 * inch, f"Page {doc.page}")
    canvas.setStrokeColor(RULE)
    canvas.line(0.9 * inch, 0.72 * inch, LETTER[0] - 0.9 * inch, 0.72 * inch)
    canvas.restoreState()


SimpleDocTemplate(
    str(OUT), pagesize=LETTER, leftMargin=0.9 * inch, rightMargin=0.9 * inch,
    topMargin=0.8 * inch, bottomMargin=0.9 * inch,
    title="AI Product Production Factory — Detailed Technical Specification",
    author="FascinateCopy",
).build(story, onFirstPage=_footer, onLaterPages=_footer)
print(f"Wrote {OUT}")
