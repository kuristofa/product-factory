# AI Product Production Factory — Phases 3 & 4

Brief in → full, hierarchy-checked asset package out, gated for human approval.
It does **not** create offers (that's the Grand Slam Offer GPT) and it does **not** publish.
CLI only for now.

**Generation runs through the Claude Code CLI on your logged-in Max account — there is no API key.**

See `docs/AI_Product_Production_Factory_Spec.pdf` for the full spec.

---

## ⚠ What you need first — the Offer Brief

**This engine does not create offers. Its only input is an approved Offer Brief that comes
from the Grand Slam Offer GPT.** The order is always:

```
Grand Slam Offer GPT  →  (approved Offer Brief)  →  THIS engine  →  Maria Wendt Sales Machine
```

So before you run anything for a real product:

1. Run your **Grand Slam Offer GPT** and get its approved offer output (copy it, or save it as
   `.md` / `.txt` / `.pdf`).
2. **Turn it into a brief — the easy way:** point `intake` at that file and the engine structures
   it into the JSON brief for you (no hand-typing JSON):
   ```powershell
   python run.py intake --from .\gpt_offer.md
   ```
   It writes a brief into `briefs\`, validates it, and tells you if the GPT left any field blank.
   *(Reading a `.pdf` needs `pdfplumber`; `.md`/`.txt` work out of the box.)*
   **Or do it by hand:** copy `briefs\example_offer_brief.json`, fill in your offer, save it.
3. Confirm it's complete:
   ```powershell
   python run.py validate --brief .\briefs\your_brief.json
   ```

Required fields: `offer_name`, `avatar`, `main_problem`, `main_promise`, `core_product_type`,
`core_deliverables` (≥1), `bonus_deliverables`, `order_bump`, `future_upsells`,
`buyer_objections` (≥1), `roi_logic`, `tone`, `ethical_boundaries`, `delivery_format`.

**Optional — `dm_tool`:** the DM-automation tool this product uses (e.g. `ManyChat`, `Chatfuel`,
`InstaChamp`). The DM flow is generated for whatever you set here. If a brief omits it, the engine
uses the `DM_TOOL` default in `.env` (ManyChat out of the box). Set it per product in the brief.

**Just testing the engine?** The included `example_offer_brief.json` is a ready-made stand-in,
so you can run the whole pipeline without the GPT to see how it works.

---

## For non-technical users

Set up once with **`Setup.bat`** (double-click), then everyone uses **`Start.bat`** daily —
no terminal, no commands. See `READ ME FIRST.txt`. The steps below are the manual/developer path.

---

## 1. One-time setup (Windows / PowerShell)

**a. Install Claude Code and log in** (this is what powers generation):
```powershell
npm install -g @anthropic-ai/claude-code
claude            # run once, sign in with your Max account, then close it
```

**b. Set up the project:**
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env      # no key needed; defaults are fine
```

**c. Verify everything's ready:**
```powershell
python run.py doctor
```
**Expect:** ✓ Claude Code CLI found, ✓ logged in and responding, ✓ You're ready to run.
If it says "not logged in," run `claude` once interactively and sign in.

---

## Easiest way to run it: the app (native window)

Instead of the command line, use the built-in interface — it opens as its own **desktop app
window** (no browser, no URL). Pick a brief, **drag in** the GPT's offer file (PDF/`.md`/`.txt`) or
paste its text and it builds the brief, click **Start**, watch progress, approve at the two review
points, and download the PDF.

On Windows, just double-click **`Start.bat`** — it launches the app window for you. Or from a
terminal:
```powershell
python desktop.py
```
(If a machine can't open a native window for any reason, it automatically falls back to opening in
your browser. You can also run the browser version directly with `python app.py`.)

The app runs generation exactly like the CLI (on this machine's Claude Code login) and stops at only
the two gates that need a human: the **quality & safety review** and the **final sign-off**. The rest
of this README is the command-line equivalent, for power use and scripting.

---

## 2. Validate a brief (no Claude account needed)

```powershell
python run.py validate --brief .\briefs\example_offer_brief.json
```
**Expect:** `Brief is complete: The 20-Minute Reels System`.
If incomplete, it lists exactly which fields are missing (exit code 1).

---

## 3. Run the pipeline (start here)

**`generate` is the command that starts and drives everything.** It works until it reaches an
approval gate, stops, and waits for you. You approve, run `generate` again to continue, repeat.

There are two ways to run it:

### Recommended: `--auto` (stops at only 2 gates)
Auto-approves the routine gates and stops only where your judgment actually matters —
`hierarchy_validation` (review the full generated package + the safety/claims report) and
`final_product` (sign-off). This turns an 11-stop loop into 2.

```powershell
# 1. Start — generates everything, stops at hierarchy_validation
python run.py generate --brief .\briefs\example_offer_brief.json --auto

# 2. Read output\<slug>\hierarchy_validation.md, then approve it
python run.py approve  --offer the-20-minute-reels-system --gate hierarchy_validation

# 3. Continue — stops at final_product
python run.py generate --brief .\briefs\example_offer_brief.json --auto

# 4. Read the final summary, approve, done
python run.py approve  --offer the-20-minute-reels-system --gate final_product
python run.py generate --brief .\briefs\example_offer_brief.json --auto   # prints Complete
```

Every time it pauses it prints the exact `approve` command to copy, so there's nothing to
memorize. All the auto-approved assets are still written to disk (`.md` files) — you can read
or regenerate any of them; auto just means the pipeline didn't stop for a formal sign-off.

### Strict: plain `generate` (stops at all 11 gates)
Drop `--auto` to review every stage one at a time — same loop, more stops. Use this the first
time through, or when you want to inspect each asset as it's produced.

```powershell
python run.py generate --brief .\briefs\example_offer_brief.json
```

The first two gates (`offer_brief`, `product_promise`) use **no Claude calls** in either mode,
so you can rehearse the flow for free; real generation begins after `product_promise`.

Check progress any time:
```powershell
python run.py status --offer the-20-minute-reels-system
```

> A blocking validation issue always halts the run — even in `--auto` — and prints what to fix.

When the last gate (`final_product`) is approved, `generate` prints **Complete** and every asset
is in `output\the-20-minute-reels-system\`.


---

## 4. Where the output lives

```
output\<offer-slug>\
  offer_brief.json
  product_package.json | .md      core_deliverables.json | .md
  bonus_deliverables.json | .md   order_bump.json | .md
  reels.json | .md   carousels.json | .md   posts.json | .md
  story_prompts.json | .md   cta_captions.json | .md
  dm_keyword_prompts.json | .md   manychat.json | .md
  dm_automation.json | .md   checkout.json | .md
  hierarchy_validation.json | .md
  _gates\  gates.json  REVIEW__<gate>.md
```
`.json` is the machine truth; `.md` is the human-readable review of the same content.

### Your deliverable — one PDF, built automatically
**When a run completes, the engine automatically compiles every asset into a single
`Product_Package.pdf` (and `.md`) at the top of the offer folder.** That's the file to open and
hand off — everything else in the folder is working files you can ignore.

The final `generate` prints the exact path to it. To rebuild it manually at any time:
```powershell
python run.py package --offer the-20-minute-reels-system
```

---

## 5. Commands

| Command | What it does |
| --- | --- |
| `python run.py doctor` | Check Claude Code is installed + logged in |
| `python run.py intake --from PATH` | Turn a GPT `.md`/`.txt`/`.pdf` offer into a structured brief |
| `python run.py validate --brief PATH` | Phase 2 completeness check (no Claude call) |
| `python run.py generate --brief PATH [--auto] [--force]` | Run to the next gate. `--auto` stops at only 2 gates; `--force` regenerates cached stages |
| `python run.py approve --offer SLUG --gate GATE` | Approve a gate |
| `python run.py reject --offer SLUG --gate GATE` | Reject a gate |
| `python run.py status --offer SLUG` | Show gate states |
| `python run.py package --offer SLUG` | Combine all assets into one `.md` + `.pdf` deliverable |
| `python run.py regenerate --brief PATH --stage NAME` | Force-regenerate one stage |

Exit codes: `0` done · `1` incomplete brief · `2` bad args / setup · `3` paused at a gate · `4` blocking validation.

---

## 6. Notes

- **No API key, no per-call billing** — generation is covered by your Max subscription via Claude Code.
- **Non-techy reviewers** can validate briefs, click through gates, and read the `.md` outputs
  without their own Claude login. Only the machine doing the *generating* needs to be logged in.
- **Resumable:** each stage caches to disk; approving a gate and re-running does not regenerate
  finished stages. Use `--force` to regenerate.
- **Self-healing output:** if a generation reply isn't clean JSON, the engine retries once asking
  for JSON only. If it still fails, it saves the raw reply to `output\<slug>\_debug\<stage>.raw.txt`
  and stops with a clear message — nothing is silently lost.
- **Ground it in your own material:** set `METHODOLOGY_NOTES_PATH` in `.env`.
- A full product run is ~25–31 Claude Code calls.
