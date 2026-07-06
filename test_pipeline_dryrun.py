"""Dry-run the full Phases 1-4 pipeline with a mock LLM (no API key, no tokens).

Exercises: real generators + batching loops, keyword collection, every gate's
block/approve/resume, cache-based resume, and all output renderers.
"""
import dataclasses
import json
import re
import shutil
from pathlib import Path

import config
from factory.gates import GateBlocked
from factory.pipeline import BlockingValidationError, Pipeline

OUT = Path("/tmp/pf_out")
if OUT.exists():
    shutil.rmtree(OUT)
cfg = dataclasses.replace(config.settings, output_dir=OUT)


def _count(user, default):
    m = re.search(r"Generate (\d+)", user)
    return int(m.group(1)) if m else default


def _start(user):
    m = re.search(r"#(\d+)-", user)
    return int(m.group(1)) if m else 1


class MockLLM:
    def __init__(self):
        self.calls = 0

    def generate(self, system, user, **kw):
        return "mock"

    def generate_json(self, system, user, **kw):
        self.calls += 1
        u = user
        if "Audit the generated assets" in u:
            return []  # validator: all clear
        if '"checkout_page_copy"' in u:
            return {"checkout_page_copy": "Buy now copy", "product_description": "desc",
                    "bullet_stack": ["b1", "b2"], "bonus_copy": "bonus", "order_bump_copy": "bump",
                    "thank_you_page": "thanks",
                    "delivery_email": {"subject": "Your access", "body": "link"},
                    "purchase_confirmation": {"subject": "Confirmed", "body": "ok"},
                    "follow_up_emails": [{"order": 1, "subject": "Hi", "body": "b", "send_after": "1d"}],
                    "refund_instructions": "Email us within 14 days."}
        if '"objection_responses"' in u and '"initial_dm"' in u:
            return {"keyword_list": ["REELS"], "initial_dm": "Hey!",
                    "follow_ups": [{"order": 1, "message": "still there?", "send_after": "1h"}],
                    "checkout_messages": ["Here's the link"],
                    "reminder_messages": [{"order": 1, "message": "last call", "send_after": "1d"}],
                    "objection_responses": [{"objection": "No time", "response": "20 min/day"}]}
        if '"handoff_condition"' in u and '"flow_name"' in u:
            return {"flow_name": "Reels Funnel", "trigger_keyword": "REELS",
                    "steps": [{"order": 1, "message": "Hi", "quick_replies": ["Yes"], "delay": "0m"}],
                    "handoff_condition": "buyer asks a pricing question"}
        if '"first_response_ref"' in u:
            return [{"keyword": "REELS", "triggered_by": "reel 1", "intent": "wants system",
                     "first_response_ref": "send the guide"}]
        if '"for_asset"' in u:
            return [{"index": i, "for_asset": "reel", "caption": f"c{i}", "keyword": "REELS"}
                    for i in range(1, 5)]
        if '"frame_type"' in u:
            return [{"index": i, "frame_type": "poll", "prompt_text": f"p{i}", "sticker": "poll",
                     "cta_keyword": "REELS"} for i in range(1, _count(u, 10) + 1)]
        if '"hook_slide"' in u:
            s = _start(u)
            return [{"index": s + i, "angle": "quick win", "hook_slide": "h",
                     "slides": [{"headline": "hd", "body": "bd"}], "cta_slide": "cta",
                     "cta_keyword": "HOOKS"} for i in range(_count(u, 8))]
        if '"post_type": "' in u:
            pt = re.search(r'"post_type": "(\w+)"', u).group(1)
            s = _start(u)
            out = []
            for i in range(_count(u, 8)):
                item = {"index": s + i, "post_type": pt, "hook": "h", "body": "b",
                        "cta": None if pt == "nurture" else "cta",
                        "cta_keyword": None if pt == "nurture" else "PROOF"}
                if pt == "objection":
                    item["objection_addressed"] = "No time"
                if pt == "proof":
                    item["proof_type"] = "testimonial"
                    item["proof_content"] = "client win"
                out.append(item)
            return out
        if "shootable Reel script" in u:
            ideas = json.loads(re.search(r"REEL IDEAS:\n(.*?)\n\nRespond", u, re.S).group(1))
            return [{"index": it["index"], "hook": "h", "script": "s",
                     "b_roll_or_visual_notes": "n", "on_screen_text": ["t"],
                     "spoken_cta": "dm me", "cta_keyword": it.get("cta_keyword", "REELS")}
                    for it in ideas]
        if '"core_idea"' in u:
            s = _start(u)
            return [{"index": s + i, "angle": "pain", "hook": "h", "core_idea": "idea",
                     "cta_keyword": f"REELS"} for i in range(_count(u, 10))]
        if '"product_outline"' in u:
            return {"product_outline": "o", "modules": [{"title": "M1", "outcome": "out",
                    "lessons": [{"title": "L1", "teaching_point": "tp", "format": "video"}]}],
                    "worksheets": [{"name": "w", "purpose": "p"}],
                    "templates": [{"name": "t", "purpose": "p"}],
                    "quick_start_guide": "start here",
                    "customer_success_path": [{"milestone": "m", "how_they_know_they_hit_it": "s"}],
                    "delivery_instructions": "drive folder"}
        if '"completion_criteria"' in u:
            return [{"name": "CD1", "purpose": "p", "format": "pdf", "problem_solved": "ps",
                     "completion_criteria": "cc", "delivery_asset": "da"}]
        if '"objection_removed"' in u:
            return [{"name": "B1", "purpose": "p", "objection_removed": "No time",
                     "why_it_belongs_as_a_bonus": "w", "delivery_asset": "da"}]
        if '"delivery_method"' in u:
            return {"product": "Caption pack", "copy": "add it", "positioning": "subordinate",
                    "delivery_method": "email"}
        raise AssertionError(f"MockLLM: unrecognized prompt:\n{u[:300]}")


mock = MockLLM()
gates_seen = []
for _ in range(20):  # advance through gates
    pipe = Pipeline("briefs/example_offer_brief.json", cfg=cfg, force=False, llm=mock)
    try:
        pipe.run()
        print("\n✓ PIPELINE COMPLETED")
        break
    except BlockingValidationError as e:
        print(f"BLOCKING at {e.gate} (unexpected in dry-run)")
        break
    except GateBlocked as e:
        gates_seen.append(e.gate)
        pipe.gates.approve(e.gate)
        print(f"  gate reached + approved: {e.gate}")

slug = pipe.writer.slug
root = OUT / slug
files = sorted(f.name for f in root.glob("*.json"))
reviews = sorted(f.name for f in (root / "_gates").glob("REVIEW__*.md"))
print(f"\nGates passed ({len(gates_seen)}): {gates_seen}")
print(f"\nAsset JSON files ({len(files)}):\n  " + "\n  ".join(files))
print(f"\nLLM calls total: {mock.calls}")

# resume test: fresh pipeline, all gates approved, caches present -> zero new calls
before = mock.calls
pipe2 = Pipeline("briefs/example_offer_brief.json", cfg=cfg, force=False, llm=mock)
pipe2.run()
print(f"\nResume run: {mock.calls - before} new LLM calls (expect 0 — all cached), completed OK")

# spot-check a rendered markdown file
sample = (root / "checkout.md").read_text()
print(f"\ncheckout.md renders ({len(sample)} chars), starts: {sample[:60]!r}")
print("counts:",
      "reels", len(json.loads((root/'reels.json').read_text())['scripts']),
      "| carousels", len(json.loads((root/'carousels.json').read_text())),
      "| posts", {k: len(v) for k, v in json.loads((root/'posts.json').read_text()).items()})
