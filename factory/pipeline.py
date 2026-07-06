"""Pipeline orchestrator (Phases 1-4).

Runs the factory stage-by-stage. Each generation stage is resumable: if its output
already exists on disk it is loaded rather than regenerated (no wasted tokens) unless
force=True. The pipeline advances until the first PENDING gate, writes that gate's
review artifact, and stops with instructions. Approve, re-run, and it continues.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable

from config import Settings, settings
from factory import generators as gen
from factory import hierarchy_validator as hv
from factory import output as out
from factory.brief import OfferBrief, load_and_require_complete
from factory.gates import CRITICAL_GATES, GateBlocked, GateStore
from factory.llm import LLMClient, LLMError

logger = logging.getLogger("factory.pipeline")


class BlockingValidationError(GateBlocked):
    """Raised when Phase 4 finds blocking issues (distinct from a normal gate pause)."""


class Pipeline:
    def __init__(self, brief_path: str | Path, cfg: Settings | None = None,
                 force: bool = False, auto: bool = False, llm: LLMClient | None = None):
        self.cfg = cfg or settings
        self.force = force
        self.auto = auto
        self.brief: OfferBrief = load_and_require_complete(brief_path)  # Phase 2: hard reject
        self.writer = out.OutputWriter(self.cfg.output_dir, self.brief.offer_name)
        self.gates = GateStore(self.writer.root)
        self.llm = llm or LLMClient(self.cfg)
        self.assets: dict[str, Any] = {}

    # -- helpers --------------------------------------------------------------

    def _stage(self, name: str, generate: Callable[[], Any],
               render: Callable[[Any], str] | None = None) -> Any:
        cache = self.writer.root / f"{name}.json"
        if cache.exists() and not self.force:
            logger.info("Loading cached stage '%s'", name)
            data = json.loads(cache.read_text(encoding="utf-8"))
        else:
            try:
                data = generate()
            except LLMError as e:
                if getattr(e, "raw", None):
                    dbg = self.writer.root / "_debug"
                    dbg.mkdir(parents=True, exist_ok=True)
                    raw_path = dbg / f"{name}.raw.txt"
                    raw_path.write_text(e.raw, encoding="utf-8")
                    raise LLMError(
                        f"Stage '{name}' failed to return valid JSON (even after a retry). "
                        f"The raw model output was saved to: {raw_path}\n"
                        f"Re-run generate to try again, or inspect that file."
                    ) from e
                raise
            self.writer.write_json(name, data)
            if render is not None:
                self.writer.write_markdown(name, render(data))
        self.assets[name] = data
        return data

    def _gate(self, gate: str, review_markdown: str) -> None:
        review_path = self.writer.write_review(gate, review_markdown)
        if self.gates.is_approved(gate):
            logger.info("Gate '%s' already approved — continuing.", gate)
            return
        if self.auto and gate not in CRITICAL_GATES:
            self.gates.approve(gate)
            logger.info("Auto-approved gate '%s' (review saved at %s).", gate, review_path.name)
            return
        raise GateBlocked(gate, review_path)

    # -- run ------------------------------------------------------------------

    def run(self) -> dict[str, Any]:
        b = self.brief
        self.writer.write_json("offer_brief", b.to_dict())

        self._gate("offer_brief",
                   f"# Offer Brief Review\n\n```json\n{json.dumps(b.to_dict(), indent=2)}\n```")
        self._gate("product_promise",
                   f"# Product Promise Review\n\n**Main Promise:** {b.main_promise}\n\n"
                   f"**Avatar:** {b.avatar}\n\n**Problem:** {b.main_problem}\n\n"
                   f"**ROI logic:** {b.roi_logic}\n\nConfirm this is the transformation the product delivers.")

        # Product + commercial scaffolding
        self._stage("product_package", lambda: gen.gen_product_package(self.llm, b),
                    out.render_product_package)

        core = self._stage("core_deliverables", lambda: gen.gen_core_deliverables(self.llm, b),
                           lambda d: out.render_deliverables("Core Deliverables", d))
        self._gate("core_deliverables", out.render_deliverables("Core Deliverables — Review", core))

        bonuses = self._stage("bonus_deliverables", lambda: gen.gen_bonus_deliverables(self.llm, b),
                             lambda d: out.render_deliverables("Bonus Deliverables", d))
        self._gate("bonus_deliverables", out.render_deliverables("Bonus Deliverables — Review", bonuses))

        bump = self._stage("order_bump", lambda: gen.gen_order_bump(self.llm, b), out.render_order_bump)
        self._gate("order_bump", out.render_order_bump(bump))

        # Content pack (no gate; validated in Phase 4)
        self._stage("reels", lambda: gen.gen_reels(self.llm, b), out.render_reels)
        self._stage("carousels", lambda: gen.gen_carousels(self.llm, b), out.render_carousels)
        self._stage("posts", lambda: gen.gen_all_posts(self.llm, b), out.render_posts)
        self._stage("story_prompts", lambda: gen.gen_story_prompts(self.llm, b), out.render_story_prompts)
        self._stage("cta_captions", lambda: gen.gen_cta_captions(self.llm, b), out.render_cta_captions)

        keywords = gen.collect_keywords(self.assets)
        self._stage("dm_keyword_prompts",
                    lambda: gen.gen_dm_keyword_prompts(self.llm, b, keywords), out.render_dm_keyword_prompts)
        self._stage("manychat", lambda: gen.gen_manychat(self.llm, b, keywords), out.render_manychat)

        # DM automation + gate
        dm_seq = self._stage("dm_automation",
                             lambda: gen.gen_dm_automation(self.llm, b, keywords), out.render_dm_automation)
        self._gate("dm_automation", out.render_dm_automation(dm_seq))

        # Checkout + gate
        checkout = self._stage("checkout", lambda: gen.gen_checkout(self.llm, b), out.render_checkout)
        self._gate("checkout_copy", out.render_checkout(checkout))

        # Phase 4 — hierarchy validation + gates
        result = hv.validate(b, self.assets, llm=self.llm)
        self.writer.write_json("hierarchy_validation", result.to_dict())
        review = _render_validation(result)
        self.writer.write_markdown("hierarchy_validation", review)
        if not result.ok:
            blocked = "# BLOCKING issues — fix and re-run with --force\n\n" + review
            self.writer.write_review("hierarchy_validation", blocked)
            raise BlockingValidationError("hierarchy_validation",
                              self.writer.root / "_gates" / "REVIEW__hierarchy_validation.md")
        self._gate("hierarchy_validation", review)
        self._gate("health_claims", review + "\n\nConfirm: no unsupported HEALTH claims.")
        self._gate("roi_claims", review + "\n\nConfirm: no unsupported ROI/income claims.")

        self._gate("final_product", _render_final(self.assets, b))

        # Run complete — auto-build the single-file deliverable so the user doesn't have to.
        self.deliverable_pdf = None
        try:
            from factory.package import package
            _, pdf_path = package(self.writer.root, b.offer_name)
            self.deliverable_pdf = pdf_path
            logger.info("Packaged deliverable: %s", pdf_path)
        except Exception as e:  # noqa: BLE001 — assets are done; packaging is a bonus step
            logger.warning("Assets are complete, but the PDF couldn't be built (%s). "
                           "Run `python run.py package --offer %s` after `pip install -r "
                           "requirements.txt`.", e, self.writer.slug)

        logger.info("Pipeline complete. Assets in %s", self.writer.root)
        return self.assets


def _render_validation(result: hv.ValidationResult) -> str:
    lines = ["# Hierarchy Validation Report\n",
             f"**Status:** {'PASS' if result.ok else 'BLOCKED'} · "
             f"{len(result.findings)} findings ({len(result.blocking)} blocking)\n"]
    if not result.findings:
        lines.append("No issues found.")
    for f in result.findings:
        lines.append(f"### [{f.severity.upper()}] {f.check}\n{f.message}")
        if f.recommended_fix:
            lines.append(f"**Fix:** {f.recommended_fix}")
        lines.append("")
    return "\n".join(lines)


def _render_final(assets: dict[str, Any], brief: OfferBrief) -> str:
    posts = assets.get("posts", {})
    return (
        f"# Final Product Review — {brief.offer_name}\n\n"
        f"- Modules: {len(assets.get('product_package', {}).get('modules', []))}\n"
        f"- Core deliverables: {len(assets.get('core_deliverables', []))}\n"
        f"- Bonuses: {len(assets.get('bonus_deliverables', []))}\n"
        f"- Order bump: {assets.get('order_bump', {}).get('product', 'n/a')}\n"
        f"- Reel scripts: {len(assets.get('reels', {}).get('scripts', []))}\n"
        f"- Carousels: {len(assets.get('carousels', []))}\n"
        f"- Posts: {sum(len(v) for v in posts.values())}\n"
        f"- Story prompts: {len(assets.get('story_prompts', []))}\n"
        f"- Checkout assets: {'yes' if assets.get('checkout') else 'no'}\n\n"
        "Approve to mark the product package production-ready."
    )
