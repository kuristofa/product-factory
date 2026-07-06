#!/usr/bin/env python3
"""AI Product Production Factory — CLI (Phases 1-4).

Commands:
  validate    --brief PATH                 Phase 2 completeness check (no API calls)
  generate    --brief PATH [--force]       Run the pipeline to the next pending gate
  approve     --offer SLUG --gate GATE      Approve a gate
  reject      --offer SLUG --gate GATE      Reject a gate
  status      --offer SLUG                  Show gate states
  regenerate  --brief PATH --stage NAME     Force-regenerate one stage

Exit codes: 0 ok/done · 1 incomplete brief · 2 bad gate/args · 3 paused at gate · 4 blocking findings
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from config import settings
from factory.brief import IncompleteBriefError, OfferBrief, load_and_require_complete
from factory.gates import APPROVED, GATE_ORDER, GateBlocked, GateStore, PENDING, REJECTED
from factory.llm import ClaudeNotAvailable, LLMError, preflight
from factory.output import slugify
from factory.pipeline import BlockingValidationError, Pipeline

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("run")


def _offer_root(slug: str) -> Path:
    return settings.output_dir / slug


def cmd_doctor(args) -> int:
    import shutil
    import subprocess
    print("Checking your setup...\n")
    ok = True
    claude = shutil.which("claude")
    if claude:
        print(f"  ✓ Claude Code CLI found: {claude}")
    else:
        print("  ✗ Claude Code CLI not found.")
        print("    Install:  npm install -g @anthropic-ai/claude-code")
        ok = False
    if claude:
        try:
            r = subprocess.run(["claude", "-p", "reply with the single word OK",
                                "--output-format", "json", "--max-turns", "2",
                                "--disallowedTools",
                                "Task,Bash,Glob,Grep,LS,Read,Edit,Write,WebFetch,WebSearch,TodoWrite",
                                "--permission-mode", "dontAsk"],
                               capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=120)
            if r.returncode == 0 and "ok" in r.stdout.lower():
                print("  ✓ Claude Code is logged in and responding.")
            elif "log in" in (r.stderr + r.stdout).lower() or "auth" in (r.stderr + r.stdout).lower():
                print("  ✗ Claude Code is installed but not logged in.")
                print("    Run `claude` once interactively and sign in with your Max account.")
                ok = False
            else:
                print(f"  ? Claude Code responded unexpectedly: {(r.stderr or r.stdout)[:200]}")
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ Could not run Claude Code: {e}")
            ok = False
    print("\n" + ("✓ You're ready to run." if ok else "✗ Fix the items above, then re-run `python run.py doctor`."))
    return 0 if ok else 2


def cmd_validate(args) -> int:
    try:
        brief = OfferBrief.from_json_file(args.brief)
    except (FileNotFoundError, ValueError) as e:
        print(f"✗ {e}")
        return 2
    problems = brief.validate()
    if problems:
        print("✗ Brief is incomplete. Missing items:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"✓ Brief is complete: {brief.offer_name}")
    return 0


def cmd_generate(args) -> int:
    try:
        pipe = Pipeline(args.brief, force=args.force, auto=getattr(args, "auto", False))
    except IncompleteBriefError as e:
        print(f"✗ {e}")
        return 1
    except (FileNotFoundError, ValueError) as e:
        print(f"✗ {e}")
        return 2
    try:
        pipe.run()
    except BlockingValidationError as e:
        print(f"\n■ Paused — hierarchy validation found blocking issues.\n  Review: {e.review_path}")
        print("  Fix the assets, then re-run generate with --force.")
        return 4
    except GateBlocked as e:
        print(f"\n■ Paused at gate '{e.gate}'.\n  Review: {e.review_path}")
        print(f"  Approve with:  python run.py approve --offer {pipe.writer.slug} --gate {e.gate}")
        print("  Then re-run generate to continue.")
        return 3
    pdf = getattr(pipe, "deliverable_pdf", None)
    if pdf:
        print(f"\n✓ Complete. All gates approved.\n"
              f"  → Open this one file: {pdf}\n"
              f"  (Everything else in output\\{pipe.writer.slug}\\ is working files you can ignore.)")
    else:
        print(f"\n✓ Complete. All gates approved. Assets in: {pipe.writer.root}\n"
              f"  Build the combined PDF with:  python run.py package --offer {pipe.writer.slug}")
    return 0


def _set_gate(args, status: str) -> int:
    store = GateStore(_offer_root(args.offer))
    try:
        store.set(args.gate, status)
    except ValueError as e:
        print(f"✗ {e}")
        return 2
    print(f"✓ Gate '{args.gate}' set to {status} for offer '{args.offer}'.")
    return 0


def cmd_approve(args) -> int:
    return _set_gate(args, APPROVED)


def cmd_reject(args) -> int:
    return _set_gate(args, REJECTED)


def cmd_status(args) -> int:
    root = _offer_root(args.offer)
    if not root.exists():
        print(f"✗ No output found for offer '{args.offer}' at {root}")
        return 2
    store = GateStore(root)
    snap = store.snapshot()
    mark = {APPROVED: "✓", REJECTED: "✗", PENDING: "·"}
    print(f"Gate status for '{args.offer}':")
    for g in GATE_ORDER:
        s = snap.get(g, PENDING)
        print(f"  {mark.get(s, '?')} {g:<22} {s}")
    return 0


def cmd_intake(args) -> int:
    from factory.intake import run_intake
    from factory.llm import LLMClient
    try:
        preflight()
    except ClaudeNotAvailable as e:
        print(f"✗ {e}")
        return 2
    try:
        path, brief = run_intake(LLMClient(settings), args.source, settings.briefs_dir, args.name)
    except (FileNotFoundError, ValueError, RuntimeError, LLMError) as e:
        print(f"✗ Intake failed: {e}")
        return 2
    print(f"✓ Structured brief written to: {path}")
    problems = brief.validate()
    if problems:
        print("  Note — the GPT output was missing some fields; fill these in before generating:")
        for p in problems:
            print(f"    - {p}")
        return 1
    print(f"  Brief is complete. Next:  python run.py generate --brief {path} --auto")
    return 0


def cmd_package(args) -> int:
    import json as _json
    from factory.package import package
    root = _offer_root(args.offer)
    if not root.exists():
        print(f"✗ No output found for offer '{args.offer}' at {root}")
        return 2
    ob = root / "offer_brief.json"
    offer_name = args.offer
    if ob.exists():
        try:
            offer_name = _json.loads(ob.read_text(encoding="utf-8")).get("offer_name", args.offer)
        except (ValueError, OSError):
            pass
    md_path, pdf_path = package(root, offer_name)
    print(f"✓ Combined deliverable written:\n  {md_path}\n  {pdf_path}")
    return 0


def cmd_regenerate(args) -> int:
    try:
        brief = load_and_require_complete(args.brief)
    except IncompleteBriefError as e:
        print(f"✗ {e}")
        return 1
    root = _offer_root(slugify(brief.offer_name))
    stages = [s.strip() for s in args.stage.split(",") if s.strip()]
    for st in stages:
        cleared = False
        for ext in (".json", ".md"):
            f = root / f"{st}{ext}"
            if f.exists():
                f.unlink()
                cleared = True
        print(f"Cleared cached stage '{st}'." if cleared else f"Stage '{st}' had no cache.")
    print("Regenerating cleared stage(s); all other stages are reused from cache...")
    # IMPORTANT: do NOT force — only the cleared stages are missing, so only they regenerate.
    args.force = False
    args.auto = getattr(args, "auto", True)
    return cmd_generate(args)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="run.py", description="AI Product Production Factory")
    sub = p.add_subparsers(dest="command", required=True)

    v = sub.add_parser("validate"); v.add_argument("--brief", required=True); v.set_defaults(func=cmd_validate)
    d = sub.add_parser("doctor"); d.set_defaults(func=cmd_doctor)
    it = sub.add_parser("intake")
    it.add_argument("--from", dest="source", required=True,
                    help="The GPT's offer output: .md, .txt, .pdf, or .json")
    it.add_argument("--name", default=None, help="Optional output filename stem")
    it.set_defaults(func=cmd_intake)
    pk = sub.add_parser("package"); pk.add_argument("--offer", required=True)
    pk.set_defaults(func=cmd_package)
    g = sub.add_parser("generate"); g.add_argument("--brief", required=True)
    g.add_argument("--force", action="store_true")
    g.add_argument("--auto", action="store_true",
                   help="Auto-approve routine gates; stop only at hierarchy_validation and final_product.")
    g.set_defaults(func=cmd_generate)
    a = sub.add_parser("approve"); a.add_argument("--offer", required=True)
    a.add_argument("--gate", required=True); a.set_defaults(func=cmd_approve)
    r = sub.add_parser("reject"); r.add_argument("--offer", required=True)
    r.add_argument("--gate", required=True); r.set_defaults(func=cmd_reject)
    s = sub.add_parser("status"); s.add_argument("--offer", required=True); s.set_defaults(func=cmd_status)
    rg = sub.add_parser("regenerate"); rg.add_argument("--brief", required=True)
    rg.add_argument("--stage", required=True,
                    help="Stage name, or comma-separated names, to regenerate (others reused).")
    rg.add_argument("--auto", action="store_true", default=True)
    rg.set_defaults(func=cmd_regenerate)
    return p


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except BrokenPipeError:
        return 0  # output was piped to something like `head`; not an error


if __name__ == "__main__":
    sys.exit(main())
