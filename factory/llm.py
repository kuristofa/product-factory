"""Generation runtime: Claude Code CLI (headless / print mode).

Generation runs through `claude -p ... --output-format json` on the machine's
logged-in Claude account (Max subscription). No API key, no `anthropic` SDK.

We deliberately do NOT pass --bare: bare mode skips the OAuth/keychain read and
would force an API key, defeating the point of using the Max login. Without --bare,
the run uses the interactive session's auth.

Each call returns the model's text (the `.result` field of the JSON envelope).
generate_json() strips fences and parses. All failures normalize to LLMError.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import time
from typing import Any

from config import Settings, settings

logger = logging.getLogger("factory.llm")

# Claude Code's default agentic tools. For pure generation we remove all of them from
# context so Claude answers directly rather than attempting tool use.
_NO_TOOLS = ("Task,Bash,Glob,Grep,LS,Read,Edit,MultiEdit,Write,NotebookEdit,"
             "WebFetch,WebSearch,TodoWrite,BashOutput,KillShell,ExitPlanMode,SlashCommand")


class LLMError(RuntimeError):
    """Wraps generation failures with a consistent type. May carry the raw model output."""

    def __init__(self, message: str, raw: str | None = None):
        super().__init__(message)
        self.raw = raw


class ClaudeNotAvailable(LLMError):
    """The `claude` CLI is missing or not logged in."""


def preflight() -> None:
    """Fail early and clearly if the Claude Code CLI isn't usable."""
    if shutil.which("claude") is None:
        raise ClaudeNotAvailable(
            "The 'claude' command was not found. Install Claude Code "
            "(npm install -g @anthropic-ai/claude-code) and log in with your Max account "
            "(run `claude` once interactively), then try again."
        )


class LLMClient:
    def __init__(self, cfg: Settings | None = None, max_retries: int = 3):
        self.cfg = cfg or settings
        self.max_retries = max_retries
        self._checked = False

    def _ensure(self) -> None:
        if not self._checked:
            preflight()
            self._checked = True

    def generate(self, system: str, user: str, **_: Any) -> str:
        """Run one headless Claude Code invocation and return its text result."""
        self._ensure()
        # This is a pure text-generation task: Claude needs no tools. Removing them from
        # context (via --disallowedTools bare names) stops Claude Code from attempting
        # tool use, which otherwise triggers error_max_turns in a one-turn run.
        system_full = system + (
            "\n\nIMPORTANT: Respond directly with the requested content only. Do not use any "
            "tools, do not search the web, and do not read or write files."
        )
        cmd = [
            "claude", "-p", user,
            "--append-system-prompt", system_full,
            "--output-format", "json",
            "--disallowedTools", _NO_TOOLS,
            "--permission-mode", "dontAsk",
            "--max-turns", "4",
        ]
        if self.cfg.model:
            cmd += ["--model", self.cfg.model]

        last_err: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                proc = subprocess.run(
                    cmd, capture_output=True, text=True,
                    encoding="utf-8", errors="replace",
                    timeout=self.cfg.timeout_seconds,
                )
                if proc.returncode != 0:
                    raise LLMError(_cli_error(proc))
                return _extract_result(proc.stdout)
            except LLMError as e:
                last_err = e
                if attempt < self.max_retries and _is_transient(str(e)):
                    wait = 2 ** attempt
                    logger.warning("Claude call failed (attempt %d/%d): %s — retrying in %ds",
                                   attempt, self.max_retries, e, wait)
                    time.sleep(wait)
                    continue
                break
            except subprocess.TimeoutExpired as e:
                last_err = LLMError(f"Claude call timed out after {self.cfg.timeout_seconds}s.")
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
                    continue
                break
        raise last_err if isinstance(last_err, LLMError) else LLMError(str(last_err))

    def generate_json(self, system: str, user: str, **kw) -> Any:
        raw = self.generate(system, user, **kw)
        try:
            return _parse_json(raw)
        except LLMError:
            # One self-heal attempt: re-ask for strictly JSON, feeding back the bad output.
            logger.warning("Reply was not valid JSON — retrying once with a JSON-only nudge.")
            nudge = (user + "\n\nYour previous reply could not be parsed as JSON. "
                     "Return ONLY the raw JSON value now — no prose, no markdown, no code fences.")
            raw2 = self.generate(system, nudge, **kw)
            try:
                return _parse_json(raw2)
            except LLMError as e:
                raise LLMError(str(e), raw=raw2 or raw) from e


def _cli_error(proc: subprocess.CompletedProcess) -> str:
    err = (proc.stderr or proc.stdout or "").strip()
    low = err.lower()
    if any(t in low for t in ("not logged in", "unauthorized", "authentication", "log in", "login")):
        return ("Claude Code is not logged in. Run `claude` once interactively and sign in "
                "with your Max account, then retry.")
    # Try to surface a clean reason from a JSON result envelope.
    try:
        env = json.loads(proc.stdout or "")
        if isinstance(env, dict) and env.get("is_error"):
            subtype = env.get("subtype", "error")
            if subtype == "error_max_turns":
                return ("Claude Code hit its turn limit (it tried to use a tool). This usually "
                        "means tools weren't disabled for the call — update to the latest build.")
            return f"Claude Code error ({subtype}): {str(env.get('result', ''))[:300]}"
    except (json.JSONDecodeError, TypeError):
        pass
    return f"Claude Code exited {proc.returncode}: {err[:500]}"


def _extract_result(stdout: str | None) -> str:
    """Pull the text out of the --output-format json envelope."""
    if not stdout:
        raise LLMError("Claude Code produced no output.")
    stdout = stdout.strip()
    try:
        env = json.loads(stdout)
    except json.JSONDecodeError:
        # Some versions may print plain text despite the flag; accept it.
        if stdout:
            return stdout
        raise LLMError("Claude Code returned empty output.")
    if isinstance(env, dict):
        if env.get("is_error"):
            raise LLMError(f"Claude Code reported an error: {env.get('result', 'unknown')}")
        result = env.get("result")
        if isinstance(result, str) and result.strip():
            return result.strip()
    raise LLMError("Claude Code JSON envelope had no 'result' text.")


def _is_transient(msg: str) -> bool:
    m = msg.lower()
    return any(t in m for t in ("rate", "429", "overloaded", "timeout", "timed out",
                                "connection", "503", "500", "temporarily"))


def _parse_json(raw: str) -> Any:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = min((cleaned.find(c) for c in "[{" if cleaned.find(c) != -1), default=-1)
        end = max(cleaned.rfind("]"), cleaned.rfind("}"))
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError as e:
                raise LLMError(f"Model did not return parseable JSON: {e}") from e
        raise LLMError("Model did not return parseable JSON.")
