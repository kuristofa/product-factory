"""Simple local web interface for the AI Product Production Factory.

Wraps the existing engine — no rewrite. Pick a brief (or paste the GPT's offer to run
intake), start generation, watch progress, review at the two gates, download the PDF.
Runs in --auto mode so the team sees only the two meaningful review points.

Generation runs on this machine via the logged-in Claude Code CLI.

Run:  python app.py   (then open http://127.0.0.1:5000)
"""
from __future__ import annotations

import html
import logging
import re
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, request, send_file

from config import settings
from factory.brief import IncompleteBriefError, OfferBrief
from factory.gates import GateStore
from factory.llm import ClaudeNotAvailable, LLMError, preflight
from factory.output import slugify
from factory.pipeline import BlockingValidationError, GateBlocked, Pipeline

app = Flask(__name__)

GATE_LABELS = {
    "hierarchy_validation": "Quality & safety review",
    "final_product": "Final sign-off",
}
STAGE_LABELS = {
    "starting": "Starting…", "continuing": "Continuing…",
    "product_package": "Building the product package",
    "core_deliverables": "Writing core deliverables",
    "bonus_deliverables": "Writing bonuses",
    "order_bump": "Creating the order bump",
    "reels": "Generating 30 reels", "carousels": "Generating carousels",
    "posts": "Writing social posts", "story_prompts": "Writing story prompts",
    "cta_captions": "Writing CTA captions", "dm_keyword_prompts": "Mapping DM keywords",
    "manychat": "Writing the DM flow", "dm_automation": "Building DM automation",
    "checkout": "Writing checkout & delivery copy",
    "hierarchy_validation": "Running the quality check",
    "packaging": "Compiling your PDF…", "done": "Done",
}


def _read(p) -> str:
    try:
        return Path(p).read_text(encoding="utf-8")
    except OSError:
        return ""


def md_to_html(md: str) -> str:
    out, in_ul = [], False
    for line in md.splitlines():
        s = line.rstrip()
        def inl(t):
            t = html.escape(t)
            t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
            t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
            return t
        if s.startswith("### "):
            if in_ul: out.append("</ul>"); in_ul = False
            out.append(f"<h4>{inl(s[4:])}</h4>")
        elif s.startswith("## "):
            if in_ul: out.append("</ul>"); in_ul = False
            out.append(f"<h3>{inl(s[3:])}</h3>")
        elif s.startswith("# "):
            if in_ul: out.append("</ul>"); in_ul = False
            out.append(f"<h2>{inl(s[2:])}</h2>")
        elif s.strip() == "---":
            if in_ul: out.append("</ul>"); in_ul = False
            out.append("<hr>")
        elif s.lstrip().startswith(("- ", "* ")):
            if not in_ul: out.append("<ul>"); in_ul = True
            out.append(f"<li>{inl(s.lstrip()[2:])}</li>")
        elif not s.strip():
            if in_ul: out.append("</ul>"); in_ul = False
        else:
            if in_ul: out.append("</ul>"); in_ul = False
            out.append(f"<p>{inl(s)}</p>")
    if in_ul: out.append("</ul>")
    return "\n".join(out)


class RunManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.log_lines: list[str] = []
        self.reset()

    def reset(self):
        with self.lock:
            self.state = {"status": "idle", "offer": None, "brief_path": None, "stage": None,
                          "gate": None, "gate_label": None, "review_html": None,
                          "pdf": None, "error": None}

    def append_log(self, msg: str):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        with self.lock:
            self.log_lines.append(line)
            if len(self.log_lines) > 500:
                self.log_lines = self.log_lines[-500:]

    def clear_log(self):
        with self.lock:
            self.log_lines = []

    def _set(self, **kw):
        with self.lock:
            self.state.update(kw)

    def snapshot(self):
        with self.lock:
            snap = dict(self.state)
            snap["log"] = self.log_lines[-300:]
            return snap

    @property
    def busy(self):
        with self.lock:
            return self.state["status"] == "running"

    def start(self, brief_path: str, force: bool = False):
        if self.busy:
            return False, "A run is already in progress."
        try:
            b = OfferBrief.from_json_file(brief_path)
        except (FileNotFoundError, ValueError) as e:
            return False, str(e)
        problems = b.validate()
        if problems:
            return False, "Brief is incomplete: " + "; ".join(problems)
        slug = slugify(b.offer_name)
        self.clear_log()
        self.append_log(f"Starting: {b.offer_name}")
        self._set(status="running", offer=slug, brief_path=str(brief_path), stage="starting",
                  gate=None, gate_label=None, review_html=None, pdf=None, error=None)
        threading.Thread(target=self._run, args=(brief_path, force), daemon=True).start()
        return True, slug

    def _on_progress(self, msg):
        self._set(stage=msg)

    def _run(self, brief_path, force):
        try:
            pipe = Pipeline(brief_path, auto=True, force=force, on_progress=self._on_progress)
            pipe.run()
            self.append_log("Done — your PDF is ready.")
            self._set(status="complete", stage="done",
                      pdf=str(pipe.deliverable_pdf) if pipe.deliverable_pdf else None)
        except BlockingValidationError as e:
            self.append_log("Blocking issues found — review the report.")
            self._set(status="blocked", gate=e.gate, gate_label="Blocking issues found",
                      review_html=md_to_html(_read(e.review_path)))
        except GateBlocked as e:
            self.append_log(f"Paused for review: {GATE_LABELS.get(e.gate, e.gate)}")
            self._set(status="gate", gate=e.gate,
                      gate_label=GATE_LABELS.get(e.gate, e.gate),
                      review_html=md_to_html(_read(e.review_path)))
        except (ClaudeNotAvailable, LLMError) as e:
            self.append_log(f"Error: {e}")
            self._set(status="error", error=str(e))
        except Exception as e:  # noqa: BLE001
            self.append_log(f"Error: {type(e).__name__}: {e}")
            self._set(status="error", error=f"{type(e).__name__}: {e}")

    def approve(self, gate):
        st = self.snapshot()
        if st["status"] != "gate" or st["gate"] != gate:
            return False, "Not currently waiting on that gate."
        GateStore(settings.output_dir / st["offer"]).approve(gate)
        self.append_log(f"Approved: {GATE_LABELS.get(gate, gate)} — continuing.")
        self._set(status="running", stage="continuing", gate=None, gate_label=None, review_html=None)
        threading.Thread(target=self._run, args=(st["brief_path"], False), daemon=True).start()
        return True, "ok"

    def regenerate(self):
        st = self.snapshot()
        if not st["brief_path"]:
            return False, "Nothing to regenerate."
        return self.start(st["brief_path"], force=True)


mgr = RunManager()


class _TerminalLog(logging.Handler):
    """Feeds the engine's INFO logs into the UI terminal pane."""
    def emit(self, record):
        try:
            mgr.append_log(record.getMessage())
        except Exception:  # noqa: BLE001
            pass


_eng = logging.getLogger("factory")
_eng.setLevel(logging.INFO)
_eng.addHandler(_TerminalLog())


# ── API ──────────────────────────────────────────────────────────────────────

@app.get("/api/briefs")
def api_briefs():
    items = []
    for p in sorted(settings.briefs_dir.glob("*.json")):
        try:
            name = OfferBrief.from_json_file(p).offer_name or p.stem
        except Exception:  # noqa: BLE001
            name = p.stem
        items.append({"file": p.name, "name": name})
    return jsonify(items)


@app.post("/api/intake")
def api_intake():
    text = (request.json or {}).get("text", "").strip()
    if not text:
        return jsonify({"ok": False, "error": "Paste the GPT offer text first."}), 400
    try:
        preflight()
    except ClaudeNotAvailable as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    from factory.intake import run_intake
    from factory.llm import LLMClient
    scratch = settings.briefs_dir / "_intake_source.md"
    scratch.write_text(text, encoding="utf-8")
    try:
        path, brief = run_intake(LLMClient(settings), scratch, settings.briefs_dir)
    except (ValueError, RuntimeError, LLMError) as e:
        return jsonify({"ok": False, "error": f"Intake failed: {e}"}), 400
    finally:
        scratch.unlink(missing_ok=True)
    return jsonify({"ok": True, "file": path.name, "name": brief.offer_name,
                    "complete": brief.is_complete(),
                    "missing": brief.validate()})


@app.post("/api/intake-file")
def api_intake_file():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "No file received."}), 400
    suffix = Path(f.filename).suffix.lower()
    if suffix not in (".pdf", ".md", ".txt", ".json"):
        return jsonify({"ok": False, "error": "Please upload a .pdf, .md, .txt, or .json file."}), 400
    try:
        preflight()
    except ClaudeNotAvailable as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    from factory.intake import run_intake
    from factory.llm import LLMClient
    scratch = settings.briefs_dir / f"_intake_upload{suffix}"
    f.save(str(scratch))
    try:
        path, brief = run_intake(LLMClient(settings), scratch, settings.briefs_dir)
    except ValueError as e:
        msg = str(e)
        if "empty" in msg.lower():
            msg = ("Couldn't read any text from this file. If it's a scanned PDF (an image of "
                   "text), it needs OCR — export a text PDF, or paste the text instead.")
        return jsonify({"ok": False, "error": msg}), 400
    except (RuntimeError, LLMError) as e:
        return jsonify({"ok": False, "error": f"Intake failed: {e}"}), 400
    finally:
        scratch.unlink(missing_ok=True)
    return jsonify({"ok": True, "file": path.name, "name": brief.offer_name,
                    "complete": brief.is_complete(), "missing": brief.validate()})


@app.post("/api/start")
def api_start():
    file = (request.json or {}).get("file", "")
    ok, msg = mgr.start(str(settings.briefs_dir / file))
    return jsonify({"ok": ok, "message": msg})


@app.post("/api/approve")
def api_approve():
    gate = (request.json or {}).get("gate", "")
    ok, msg = mgr.approve(gate)
    return jsonify({"ok": ok, "message": msg})


@app.post("/api/regenerate")
def api_regenerate():
    ok, msg = mgr.regenerate()
    return jsonify({"ok": ok, "message": msg})


@app.get("/api/status")
def api_status():
    st = mgr.snapshot()
    st["stage_label"] = STAGE_LABELS.get(st.get("stage"), st.get("stage"))
    return jsonify(st)


@app.get("/api/download")
def api_download():
    st = mgr.snapshot()
    if not st.get("pdf") or not Path(st["pdf"]).exists():
        return "No PDF available yet.", 404
    return send_file(st["pdf"], as_attachment=True, download_name="Product_Package.pdf")


@app.get("/api/ready")
def api_ready():
    """Non-blocking readiness check so a non-techy user gets a plain message, not an error."""
    import shutil
    import subprocess
    if shutil.which("claude") is None:
        return jsonify({"ready": False,
                        "message": "This machine isn't fully set up yet — Claude Code isn't "
                                   "installed. Ask whoever set this up to finish setup."})
    try:
        r = subprocess.run(
            ["claude", "-p", "reply with OK", "--output-format", "json", "--max-turns", "2",
             "--disallowedTools", "Task,Bash,Read,Write,WebFetch,WebSearch,TodoWrite",
             "--permission-mode", "dontAsk"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
        if r.returncode == 0 and "ok" in (r.stdout or "").lower():
            return jsonify({"ready": True, "message": ""})
        low = (r.stderr + r.stdout).lower()
        if "log in" in low or "login" in low or "auth" in low:
            return jsonify({"ready": False,
                            "message": "Claude Code isn't signed in on this machine. Ask whoever "
                                       "set this up to sign in."})
        return jsonify({"ready": False, "message": "Claude Code isn't responding. Ask whoever set "
                                                    "this up to check it."})
    except Exception:  # noqa: BLE001
        return jsonify({"ready": False,
                        "message": "Couldn't reach Claude Code on this machine. Ask whoever set "
                                   "this up to check it."})


@app.get("/")
def index():
    return PAGE


PAGE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI-powered Product Production Factory</title>
<style>
:root{
--ink:#1b2733;--muted:#5b6b7b;--accent:#2f6f6b;--accentdk:#234f4c;--rule:#d6dde3;
--bg:#f7f9fa;--card:#ffffff;--input:#ffffff;--review-bg:#fcfdfd;--code-bg:#eef2f3;
--sec-bg:#eef2f3;--sec-hover:#e2e8ea;--err-bg:#fbeeee;--err-ink:#8a2f2f;--err-rule:#e6c9c9;
--term-bg:#0f141a;--term-ink:#bfe0d9;--drag-bg:#eef6f5;--spin:#cfe0de}
@media (prefers-color-scheme: dark){:root{
--ink:#e6edf2;--muted:#93a3b0;--accent:#3f9188;--accentdk:#6cc0b6;--rule:#2c353e;
--bg:#12171c;--card:#1b2229;--input:#232b33;--review-bg:#161c22;--code-bg:#2a333c;
--sec-bg:#2a333c;--sec-hover:#333d47;--err-bg:#2a1a1a;--err-ink:#f0b4b4;--err-rule:#5a3535;
--term-bg:#0b0f14;--term-ink:#bfe0d9;--drag-bg:#1f2a29;--spin:#3a4a48}}
*{box-sizing:border-box}
body{font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;color:var(--ink);margin:0;background:var(--bg)}
.wrap{max-width:820px;margin:0 auto;padding:28px 20px 60px}
h1{font-size:22px;margin:0 0 4px}.sub{color:var(--muted);margin:0 0 24px;font-size:14px}
.card{background:var(--card);border:1px solid var(--rule);border-radius:12px;padding:20px;margin-bottom:18px}
.card h2{font-size:15px;margin:0 0 12px;color:var(--accentdk)}
label{display:block;font-size:13px;color:var(--muted);margin:0 0 6px}
select,textarea{width:100%;font:inherit;padding:10px;border:1px solid var(--rule);border-radius:8px;background:var(--input);color:var(--ink)}
textarea{min-height:120px;resize:vertical}
button{font:inherit;font-weight:600;border:0;border-radius:8px;padding:11px 18px;cursor:pointer;background:var(--accent);color:#fff}
button:hover{filter:brightness(1.08)}button:disabled{opacity:.5;cursor:default}
button.secondary{background:var(--sec-bg);color:var(--ink)}button.secondary:hover{background:var(--sec-hover);filter:none}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.hidden{display:none}
.spinner{width:16px;height:16px;border:3px solid var(--spin);border-top-color:var(--accent);border-radius:50%;animation:spin 1s linear infinite;display:inline-block;vertical-align:middle}
@keyframes spin{to{transform:rotate(360deg)}}
.review{max-height:52vh;overflow:auto;border:1px solid var(--rule);border-radius:8px;padding:16px;background:var(--review-bg);font-size:14px;line-height:1.5}
.review h2{font-size:17px;color:var(--accentdk)}.review h3{font-size:15px}.review h4{font-size:13px}
.review code{background:var(--code-bg);padding:1px 5px;border-radius:4px;font-size:12px}
.review hr{border:0;border-top:1px solid var(--rule);margin:12px 0}
.err{color:var(--err-ink);background:var(--err-bg);border:1px solid var(--err-rule);padding:12px;border-radius:8px;font-size:14px}
.ok{color:var(--accentdk);font-weight:600}
.divider{text-align:center;color:var(--muted);font-size:12px;margin:14px 0}
.dl{display:inline-block;text-decoration:none}
small.hint{color:var(--muted);font-size:12px}
.dropzone{border:2px dashed var(--rule);border-radius:10px;padding:22px;text-align:center;color:var(--muted);transition:.15s}
.dropzone.drag{border-color:var(--accent);background:var(--drag-bg)}
.dropzone p{margin:4px 0}
.terminal{background:var(--term-bg);color:var(--term-ink);font-family:Consolas,Menlo,Monaco,monospace;font-size:12px;line-height:1.55;padding:12px 14px;border-radius:8px;height:190px;overflow:auto;white-space:pre-wrap;word-break:break-word;border:1px solid var(--rule)}
.banner{background:#fff6e6;border:1px solid #f0d9a8;color:#8a6a2f;padding:12px 14px;border-radius:8px;margin-bottom:16px;font-size:14px}
@media (prefers-color-scheme: dark){.banner{background:#2b2412;border-color:#5a4a22;color:#e8cf96}}
</style></head>
<body><div class="wrap">
<h1>AI-powered Product Production Factory</h1>
<p class="sub">Brief in → full asset package out, reviewed and compiled into one PDF.</p>
<div id="banner" class="banner hidden"></div>

<div id="setup" class="card">
  <h2>Start a product</h2>
  <label>Pick an existing brief</label>
  <div class="row">
    <select id="briefSelect" style="flex:1"></select>
    <button id="startBtn">Start</button>
  </div>
  <div class="divider">— or drop a file —</div>
  <div id="dropzone" class="dropzone">
    <p><strong>Drag a PDF, .md, or .txt here</strong></p>
    <p class="hint">the offer from your Grand Slam Offer GPT</p>
    <button id="chooseBtn" class="secondary" type="button">Choose file</button>
    <input id="fileInput" type="file" accept=".pdf,.md,.txt,.json" hidden>
    <div id="dropMsg" class="hint" style="margin-top:10px"></div>
  </div>
  <div class="divider">— or paste —</div>
  <label>Paste your Grand Slam Offer GPT output, and I'll build the brief</label>
  <textarea id="offerText" placeholder="Paste the offer here…"></textarea>
  <div class="row" style="margin-top:10px">
    <button id="intakeBtn" class="secondary">Structure into a brief</button>
    <span id="intakeMsg" class="hint"></span>
  </div>
</div>

<div id="progress" class="card hidden">
  <h2>Working…</h2>
  <div class="row"><span class="spinner"></span><span id="stageText">Starting…</span></div>
  <small class="hint">A full run makes ~25 Claude Code calls and takes a few minutes. You can leave this open.</small>
</div>

<div id="review" class="card hidden">
  <h2 id="reviewTitle">Review</h2>
  <div id="reviewBody" class="review"></div>
  <div class="row" style="margin-top:14px">
    <button id="approveBtn">Approve &amp; continue</button>
    <button id="regenBtn" class="secondary">Regenerate from scratch</button>
  </div>
</div>

<div id="done" class="card hidden">
  <h2 class="ok">✓ Done</h2>
  <p>Your complete product package is ready as a single PDF.</p>
  <a class="dl" href="/api/download"><button>Download PDF</button></a>
  <button id="newBtn" class="secondary" style="margin-left:8px">Start another</button>
</div>

<div id="errorCard" class="card hidden"><div class="err" id="errorText"></div>
  <button id="retryBtn" class="secondary" style="margin-top:12px">Back</button></div>

<div id="termCard" class="card hidden">
  <h2>Activity log</h2>
  <pre id="term" class="terminal"></pre>
</div>

</div>
<script>
const $=id=>document.getElementById(id);
let curGate=null;
async function jget(u){return (await fetch(u)).json();}
async function jpost(u,b){return (await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b||{})})).json();}

async function loadBriefs(){
  const items=await jget('/api/briefs');
  const sel=$('briefSelect');sel.innerHTML='';
  if(!items.length){const o=document.createElement('option');o.textContent='(no briefs yet — paste an offer below)';o.value='';sel.appendChild(o);}
  items.forEach(it=>{const o=document.createElement('option');o.value=it.file;o.textContent=it.name+'  ('+it.file+')';sel.appendChild(o);});
}
function show(id){['setup','progress','review','done','errorCard'].forEach(x=>$(x).classList.toggle('hidden',x!==id));}

$('intakeBtn').onclick=async()=>{
  const text=$('offerText').value.trim();
  if(!text){$('intakeMsg').textContent='Paste the offer first.';return;}
  $('intakeBtn').disabled=true;$('intakeMsg').innerHTML='<span class="spinner"></span> Structuring…';
  const r=await jpost('/api/intake',{text});
  $('intakeBtn').disabled=false;
  if(!r.ok){$('intakeMsg').textContent=r.error;return;}
  await loadBriefs();$('briefSelect').value=r.file;
  $('intakeMsg').textContent=r.complete?('✓ Built "'+r.name+'" — ready to start.'):('Built, but missing: '+(r.missing||[]).join(', '));
};
const dz=$('dropzone'), fi=$('fileInput');
$('chooseBtn').onclick=()=>fi.click();
fi.onchange=()=>{if(fi.files[0])uploadFile(fi.files[0]);};
['dragenter','dragover'].forEach(ev=>dz.addEventListener(ev,e=>{e.preventDefault();e.stopPropagation();dz.classList.add('drag');}));
['dragleave','drop'].forEach(ev=>dz.addEventListener(ev,e=>{e.preventDefault();e.stopPropagation();dz.classList.remove('drag');}));
dz.addEventListener('drop',e=>{const f=e.dataTransfer&&e.dataTransfer.files[0];if(f)uploadFile(f);});
async function uploadFile(file){
  $('dropMsg').innerHTML='<span class="spinner"></span> Reading & structuring '+file.name+'…';
  const fd=new FormData();fd.append('file',file);
  let r;try{r=await (await fetch('/api/intake-file',{method:'POST',body:fd})).json();}
  catch(err){$('dropMsg').textContent='Upload failed.';return;}
  if(!r.ok){$('dropMsg').textContent=r.error;return;}
  await loadBriefs();$('briefSelect').value=r.file;
  $('dropMsg').innerHTML=r.complete?('✓ Built <strong>'+r.name+'</strong> — click Start above.'):('Built, but missing: '+(r.missing||[]).join(', '));
}

$('startBtn').onclick=async()=>{
  const file=$('briefSelect').value;
  if(!file){$('intakeMsg').textContent='Pick or build a brief first.';return;}
  const r=await jpost('/api/start',{file});
  if(!r.ok){show('errorCard');$('errorText').textContent=r.message;return;}
  show('progress');poll();
};
$('approveBtn').onclick=async()=>{await jpost('/api/approve',{gate:curGate});show('progress');poll();};
$('regenBtn').onclick=async()=>{await jpost('/api/regenerate',{});show('progress');poll();};
$('newBtn').onclick=()=>{$('termCard').classList.add('hidden');show('setup');loadBriefs();};
$('retryBtn').onclick=()=>{$('termCard').classList.add('hidden');show('setup');loadBriefs();};

function renderTerm(s){
  const log=(s.log||[]).join('\n');
  const el=$('term');
  const atBottom=el.scrollHeight-el.scrollTop-el.clientHeight<40;
  el.textContent=log;
  if(atBottom)el.scrollTop=el.scrollHeight;
  $('termCard').classList.toggle('hidden',!log);
}
let polling=false;
async function poll(){
  if(polling)return;polling=true;
  const t=setInterval(async()=>{
    const s=await jget('/api/status');
    renderTerm(s);
    if(s.status==='running'){show('progress');$('stageText').textContent=s.stage_label||'Working…';}
    else if(s.status==='gate'){clearInterval(t);polling=false;curGate=s.gate;
      show('review');$('reviewTitle').textContent=s.gate_label||'Review';$('reviewBody').innerHTML=s.review_html||'';}
    else if(s.status==='blocked'){clearInterval(t);polling=false;curGate=s.gate;
      show('review');$('reviewTitle').textContent='⚠ Issues found — review, then regenerate';$('reviewBody').innerHTML=s.review_html||'';}
    else if(s.status==='complete'){clearInterval(t);polling=false;show('done');}
    else if(s.status==='error'){clearInterval(t);polling=false;show('errorCard');$('errorText').textContent=s.error||'Something went wrong.';}
  },1500);
}
async function checkReady(){
  try{const r=await jget('/api/ready');
    if(!r.ready){const b=$('banner');b.textContent='⚠ '+r.message;b.classList.remove('hidden');}
  }catch(e){}
}
loadBriefs();
checkReady();
</script></body></html>"""


if __name__ == "__main__":
    print("\n  AI-powered Product Production Factory")
    print("  Open:  http://127.0.0.1:5000\n")
    app.run(host="127.0.0.1", port=5000, threaded=True)
