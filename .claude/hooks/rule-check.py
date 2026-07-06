#!/usr/bin/env python3
"""
PreToolUse hook: deep semantic rule check on outbound prose payloads via a
fresh Sonnet invocation. Reads ~/.claude/rules/*.md and ~/.claude/CLAUDE.md,
asks Sonnet whether the payload complies with every rule, and exit-2-blocks
the tool call on any violation.

This is the heavier complement to lint-outbound.py: cheap regexes catch the
deterministic typography and leak patterns; this catches the semantic stuff
(paraphrased Linear titles, inline-summarized internal context, drifted
TODO formats, missed conventions).

Gated tools: prose surfaces only.

- Bash: `git commit`, `gh pr create|edit`, `gh pr comment`, `gh issue
  create|edit|comment`, `gh api` with `body`/`title` fields.
- MCP: `mcp__linear__save_*`, `mcp__notion__notion-(create-pages|update-page
  |create-comment)`, `mcp__claude_ai_Slack__slack_(send_message|
  send_message_draft|schedule_message|create_canvas|update_canvas)`,
  `mcp__claude_ai_Gmail__create_draft`.

Source-code Edit/Write is intentionally NOT in this hook; lint-outbound.py's
regex layer handles the deterministic source-code rules at zero latency.

Override: include `<!-- rule-check: skip reason="..." -->` (HTML comment)
or `# rule-check: skip reason="..."` (line comment) anywhere in the
payload to bypass. Logged to ~/.claude/rule-check.log for audit.

Reliability posture:

- Timeouts and subprocess failures fail OPEN (allow, log). A broken or
  slow linter must never block a correct payload.
- Verdicts are cached by (rules, surface, payload) hash in
  ~/.claude/rule-check-cache.json so identical payloads always get
  identical verdicts despite the LLM being non-deterministic.
- Findings that hinge on character arithmetic (table padding, subject
  length, wrap width) are mechanically discarded; lint-outbound.py
  enforces those deterministically on the source text.

Subprocess invocation uses `claude --print --allowed-tools ""` so the
subprocess cannot make tool calls, which means PreToolUse hooks never
fire inside it: no recursion risk. The rules + payload travel inline as
the prompt; the model returns a schema-validated JSON verdict.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

RULES_DIR = Path.home() / ".claude" / "rules"
CLAUDE_MD = Path.home() / ".claude" / "CLAUDE.md"
LOG_FILE = Path.home() / ".claude" / "rule-check.log"
CACHE_FILE = Path.home() / ".claude" / "rule-check-cache.json"

SUBPROCESS_TIMEOUT_SEC = 80
MAX_PAYLOAD_CHARS = 40_000
CACHE_TTL_SEC = 7 * 24 * 3600
CACHE_MAX_ENTRIES = 500

SKIP_RE = re.compile(
    r"(?:<!--|#|//)\s*rule-check:\s*skip(?:\s+reason=\"([^\"]+)\")?",
    re.IGNORECASE,
)

GATED_MCP_RE = re.compile(
    r"^(?:"
    r"mcp__linear__save_.*"
    r"|mcp__notion__notion-(?:create-pages|update-page|create-comment)"
    r"|mcp__claude_ai_Slack__slack_(?:send_message|send_message_draft"
    r"|schedule_message|create_canvas|update_canvas)"
    r"|mcp__claude_ai_Gmail__create_draft"
    r")$"
)

HEREDOC_RE = re.compile(
    r"<<[-]?\s*['\"]?(\w+)['\"]?\s*\n(.*?)\n\s*\1\b",
    re.DOTALL,
)
FLAG_VALUE_RE = re.compile(
    r"(?:^|\s)(--?)(m|message|body|title)[=\s]+"
    r"(\"((?:[^\"\\]|\\.)*)\"|'((?:[^'\\]|\\.)*)')",
)
GH_API_FIELD_RE = re.compile(
    r"(?:^|\s)(?:-[fF]|--(?:raw-)?field)\s+(body|title)="
    r"(\"((?:[^\"\\]|\\.)*)\"|'((?:[^'\\]|\\.)*)')",
)
BODY_FILE_RE = re.compile(r"(?:^|\s)--body-file[=\s]+(\S+)")
# `git commit -F <path>` / `git commit --file <path>` reads the commit
# message from a file. Scoped to git commit only because `-F` collides
# with `gh api -F field=value` (handled separately by GH_API_FIELD_RE).
COMMIT_FILE_RE = re.compile(r"(?:^|\s)(?:-F|--file)[=\s]+(\S+)")

GH_API_AT_FILE_RE = re.compile(
    r"(?:^|\s)(?:-[fF]|--(?:raw-)?field)\s+(body|title)=@(\S+)"
)

CMD_SUBST_PREFIX_RE = re.compile(r"^\$[\(\{]")

# Heredocs that are stdin for a code interpreter (`python3 - <<'PY'`)
# carry source code, not outbound prose, and must not be rule-checked.
CODE_INTERPRETERS = frozenset(
    {
        "python",
        "python3",
        "node",
        "ruby",
        "perl",
        "php",
        "osascript",
        "psql",
        "sqlite3",
        "jq",
        "awk",
    }
)


def heredoc_feeds_interpreter(command: str, heredoc_start: int) -> bool:
    """True when the command word owning the heredoc at `heredoc_start`
    is a code interpreter."""
    prefix = command[:heredoc_start]
    segment = re.split(r"[|;&\n]|\$\(", prefix)[-1].strip()
    words = segment.split()
    first = os.path.basename(words[0]) if words else ""
    return first in CODE_INTERPRETERS


def _is_real_prose_value(value: str | None) -> bool:
    """Filter out flag-value extractions that are shell wrappers, not real
    prose. Catches the residue left after HEREDOC_RE substitution wipes a
    `$(cat <<'EOF' ... EOF)` heredoc invocation, which otherwise produces a
    phantom payload like `$(cat \\n)` that wastes a Sonnet call."""
    if not value or len(value) <= 4:
        return False
    if CMD_SUBST_PREFIX_RE.match(value.lstrip()):
        return False
    return True


VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["pass", "fail"]},
        "violations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "rule_file": {"type": "string"},
                    "rule_quote": {"type": "string"},
                    "payload_excerpt": {"type": "string"},
                    "suggested_fix": {"type": "string"},
                },
                "required": [
                    "rule_file",
                    "rule_quote",
                    "payload_excerpt",
                    "suggested_fix",
                ],
            },
        },
    },
    "required": ["verdict", "violations"],
}


def log(msg: str) -> None:
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except OSError:
        pass


def extract_bash_payloads(command: str) -> list[tuple[str, str]]:
    """Return (surface_label, text) tuples extracted from a Bash command."""
    if not re.search(
        r"\b(git\s+commit|gh\s+(pr|issue)\s+\w+|gh\s+api\b)",
        command,
    ):
        return []

    is_commit = bool(re.search(r"\bgit\s+commit\b", command))
    is_pr = bool(re.search(r"\bgh\s+pr\b", command))
    is_issue = bool(re.search(r"\bgh\s+issue\b", command))
    gh_surface = (
        "GitHub PR" if is_pr else "GitHub issue" if is_issue else "GitHub API"
    )
    surface = "git commit message" if is_commit else gh_surface

    out: list[tuple[str, str]] = []

    for m in HEREDOC_RE.finditer(command):
        if heredoc_feeds_interpreter(command, m.start()):
            continue
        out.append((f"{surface} heredoc<{m.group(1)}>", m.group(2)))

    redacted = HEREDOC_RE.sub("", command)
    for m in FLAG_VALUE_RE.finditer(redacted):
        flag = f"{m.group(1)}{m.group(2)}"
        value = m.group(4) if m.group(4) is not None else m.group(5)
        if _is_real_prose_value(value):
            # In a compound command (`git commit ... && gh pr create ...`),
            # label each flag by the command that owns it: -m/--message
            # are commit flags; --body/--title belong to gh. A PR title
            # must never be evaluated under the commit-subject lens.
            if m.group(2) in ("m", "message"):
                flag_surface = "git commit message" if is_commit else surface
            elif is_pr or is_issue:
                flag_surface = gh_surface
            else:
                flag_surface = surface
            out.append((f"{flag_surface} arg {flag}", value))
    for m in GH_API_FIELD_RE.finditer(redacted):
        flag = f"-f {m.group(1)}"
        value = m.group(3) if m.group(3) is not None else m.group(4)
        if _is_real_prose_value(value):
            out.append((f"{gh_surface} {flag}", value))

    for m in GH_API_AT_FILE_RE.finditer(redacted):
        path = m.group(2).strip("'\"")
        if path == "-":
            continue
        try:
            text = Path(os.path.expanduser(path)).read_text()
            if text:
                out.append((f"{gh_surface} -f {m.group(1)} @{path}", text))
        except OSError:
            pass

    for m in BODY_FILE_RE.finditer(redacted):
        path = m.group(1).strip("'\"")
        try:
            text = Path(os.path.expanduser(path)).read_text()
            if text:
                out.append((f"{gh_surface} --body-file {path}", text))
        except OSError:
            pass

    if is_commit:
        for m in COMMIT_FILE_RE.finditer(redacted):
            path = m.group(1).strip("'\"")
            try:
                text = Path(os.path.expanduser(path)).read_text()
                if text:
                    out.append((f"{surface} -F {path}", text))
            except OSError:
                pass

    return out


def walk_strings(obj, path: str = ""):
    if isinstance(obj, str):
        yield path or "<root>", obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            sub = f"{path}.{k}" if path else k
            yield from walk_strings(v, sub)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            sub = f"{path}[{i}]"
            yield from walk_strings(v, sub)


def extract_mcp_payloads(tool_name: str, tool_input: dict) -> list[tuple[str, str]]:
    surface = tool_name.split("__")[-1]
    out: list[tuple[str, str]] = []
    for label, value in walk_strings(tool_input):
        if not value or len(value) < 20:
            continue
        out.append((f"{surface} {label}", value))
    return out


def extract_payloads(tool_name: str, tool_input: dict) -> list[tuple[str, str]]:
    if tool_name == "Bash":
        cmd = tool_input.get("command", "")
        if isinstance(cmd, str):
            return extract_bash_payloads(cmd)
        return []
    if GATED_MCP_RE.match(tool_name):
        return extract_mcp_payloads(tool_name, tool_input)
    return []


def load_rules() -> str:
    parts: list[str] = []
    if CLAUDE_MD.exists():
        parts.append(f"=== CLAUDE.md ===\n{CLAUDE_MD.read_text()}")
    if RULES_DIR.exists():
        for path in sorted(RULES_DIR.glob("*.md")):
            parts.append(f"=== rules/{path.name} ===\n{path.read_text()}")
    return "\n\n".join(parts)


def build_prompt(rules: str, surface: str, payload: str) -> str:
    return f"""You are a strict rule-compliance checker. Read every rule below carefully, then evaluate the payload that is about to be sent to the surface shown. Block on any actual rule violation. Do not flag stylistic preferences not explicitly written in the rules.

Two hard constraints on YOUR findings:

1. NEVER flag anything that depends on counting characters or measuring widths: commit-subject length, PR-title length, line-wrap width, Markdown table column padding, alignment, or separator width. A deterministic linter enforces all of those outside this model. Character arithmetic from you is unreliable (you measure rendered width where source width is what matters) and any such finding will be mechanically discarded.
2. Resolve genuinely borderline judgment calls toward "pass". Only fail on violations you are certain about. If a rule's applicability to a payload is ambiguous (e.g., the bullet terminal-period rule, label-colon vs clause-colon), pass.

Pay particular attention to these common drift modes:

- Linear slugs (pattern `[A-Z]{{2,5}}-\\d+` like `BYB-1234` or `EPD-987`) appearing in source-code comments, docstrings, test names, or any code-evergreen surface. Forbidden by rules/git.md unless absolutely necessary. PR descriptions, commit messages, branch names, and Linear/Notion/Slack content are the right places.
- Internal or local-only paths leaking into external content: `~/nickolashkraus/`, `agent-os/`, `/Users/nickolas/`, references to private repos, daily-log paths, scratch notes. Forbidden by rules/general.md. Inline a summary instead.
- Linear issue references in PR `## References` blocks: titles after the colon must be VERBATIM Linear titles, not paraphrases or abbreviations. Rule in rules/git.md.
- Forbidden tokens in commit/PR contexts: em dashes, smart quotes (rules/typography.md), `Co-Authored-By:` in commits (rules/git.md), `Closes:`/`Fixes:`/`Resolves:` in PR descriptions (rules/git.md).
- Bare Linear-slug references that should be Markdown links (`[BYB-1234](url)`) in rendered Markdown surfaces (PR descriptions, review comments). Rule in rules/git.md. Bare slugs ARE correct in chat replies, commit messages, branch names, and source code.
- Hard line breaks within paragraphs in external content (PR bodies, Linear, Notion, Slack). Forbidden by rules/git.md; Markdown renderers handle wrapping. In-repo Markdown files (docs, CLAUDE.md, etc.) DO wrap at ~80 chars.
- Reference-style link shorthand `[label][]` or bare `[label]`. Forbidden by rules/typography.md.
- Paraphrased section headers or section content that drift from canonical Linear/PR/commit conventions.
- A lowercase word after a colon that ends a label or lead-in: bullets (`**Element**: lowercase`, `**Element** (note): lowercase`), line-initial link lead-ins (`[Link](url): lowercase`), and bold callouts (`**NOTE**: lowercase`). Do NOT flag a colon that joins two clauses inside a flowing sentence (`the entry was also stale: it declared ...`); lowercase is correct there. Non-alphabetic starts (paths, code spans, numbers, URLs) are naturally exempt. Rule in rules/typography.md.
- Period rule for bulleted list items (rules/typography.md): the DEFAULT is NO terminal period on a bullet. Only flag a MISSING period when the bullet item contains internal punctuation (e.g., multiple sentences, or a semicolon-joined clause) such that the lack of terminator hurts readability. A short single-clause bullet like `- Retried events are no-ops` is correct as-is; do not demand a period. Conversely, flag a SUPERFLUOUS terminal period only when the bullet is a simple short fragment.
- Smart quotes anywhere in the payload. Look for these EXACT characters: U+2018 (LEFT SINGLE QUOTATION MARK), U+2019 (RIGHT SINGLE QUOTATION MARK), U+201C (LEFT DOUBLE QUOTATION MARK), U+201D (RIGHT DOUBLE QUOTATION MARK). They are visually subtle but always forbidden. Examples of forbidden runs to spot: a curly opening quote followed by a word followed by a curly closing quote anywhere in prose, no matter how short. Flag every occurrence regardless of context. Rule in rules/typography.md.

Surface-specific lens:

- `git commit message`: imperative subject, no terminal period, no Co-Authored-By; bare Linear slug in subject is correct. Subject length and body wrap width are enforced deterministically elsewhere; do NOT count characters. When the subject matches `SLUG: Exact Issue Title` (e.g., `BYB-1345: Membership Upgrade Creates Duplicate Active Subscriptions in Stripe`), that rule supersedes the generic subject rules; it has NO length cap and keeps the issue title's capitalization. Conventional Commits carve-out (rules/git.md): when the subject matches `type(scope): description` with a lowercase type (feat, fix, docs, test, chore, refactor, etc.), the repo convention wins. The lowercase type, lowercase description, and lowercase-after-colon form are all CORRECT; do not flag any of them and do not demand `Fix(...)` capitalization.
- `GitHub PR` body or comment: single line per paragraph (no hard wraps), Markdown links for Linear refs, verbatim Linear titles in References, no Closes/Fixes/Resolves, no internal paths. A PR title (`--title`) is NOT a commit subject: it has no length limit and no imperative-mood requirement beyond rules/git.md's own PR-title rules. Never flag Markdown table padding or column alignment (deterministic linter territory).
- Trivial PR bodies are allowed to be a single declarative sentence (rules/git.md explicitly permits "Service should not be publicly available." or "Routine version bump to pick up upstream type fixes." as valid trivial bodies). Do NOT demand a leading verb on these. Only flag the "lead with a declarative verb" rule for longer PR bodies and for openers like `This PR adds...` or `In this PR, I...`.
- `Linear issue` (`save_issue`): standard sections (Overview, Acceptance Criteria, Implementation Details, References), Title Case for issue titles, no extra newlines for human readability.
- `Notion page`: same prose conventions; references via real links.
- `Slack message`: typography rules; tabular data should be TSV.

Return ONLY a JSON object matching this exact shape:

{{"verdict": "pass" or "fail", "violations": [{{"rule_file": "rules/X.md", "rule_quote": "exact quote from the rule", "payload_excerpt": "the offending substring from the payload", "suggested_fix": "concrete fix instruction"}}]}}

If the payload is compliant, return `{{"verdict": "pass", "violations": []}}`. Only set verdict to "fail" when there is at least one real violation. Do not invent rules; quote only from the rule files below.

=== RULES ===

{rules}

=== PAYLOAD (destined for: {surface}) ===

{payload}
"""


def run_check(rules: str, surface: str, payload: str) -> tuple[str, list[dict]]:
    """Spawn `claude --bare` to evaluate payload. Returns (verdict, violations)."""
    if len(payload) > MAX_PAYLOAD_CHARS:
        payload = payload[:MAX_PAYLOAD_CHARS] + "\n\n[... truncated ...]"

    prompt = build_prompt(rules, surface, payload)
    try:
        result = subprocess.run(
            [
                "claude",
                "--print",
                "--model",
                "sonnet",
                "--allowed-tools",
                "",
                "--output-format",
                "json",
                "--json-schema",
                json.dumps(VERDICT_SCHEMA),
            ],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired:
        # Fail OPEN. A linter timing out must never block a correct
        # payload; the log preserves the event for audit. "soft-pass"
        # (vs "pass") keeps the verdict out of the cache so a later
        # identical payload still gets a real check.
        log(f"TIMEOUT_FAIL_OPEN surface={surface}")
        return ("soft-pass", [])

    if result.returncode != 0:
        log(f"NONZERO_EXIT rc={result.returncode} stderr={result.stderr[:500]}")
        return ("soft-pass", [])

    raw = result.stdout.strip()
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError:
        log(f"BAD_ENVELOPE_JSON raw={raw[:500]}")
        return ("soft-pass", [])

    structured = envelope.get("structured_output")
    if isinstance(structured, dict):
        verdict_obj = structured
    else:
        result_text = envelope.get("result", "")
        if isinstance(result_text, str) and result_text.strip():
            text = result_text.strip()
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            try:
                verdict_obj = json.loads(text)
            except json.JSONDecodeError:
                log(f"BAD_RESULT_JSON text={text[:500]}")
                return ("soft-pass", [])
        else:
            log("EMPTY_VERDICT envelope had no structured_output or result")
            return ("soft-pass", [])

    verdict = verdict_obj.get("verdict", "pass")
    violations = verdict_obj.get("violations", []) or []
    return (verdict, violations)


FORBIDDEN_CHAR_CLASSES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("‘’“”", ("smart quote", "curly", "quotation mark")),
    ("—", ("em dash", "em-dash")),
)


WIDTH_ARITHMETIC_RE = re.compile(
    r"separator row|extra dash|\bdashes\b"
    r"|column[^.\n]{0,30}width|width[^.\n]{0,30}column"
    r"|\bpadded\b|\bpadding\b|chars? wide|characters wide"
    r"|\b\d+\s+(?:vs\.?|versus)\s+\d+"
    r"|50 characters|72 characters|exceeds? \d+ char"
    r"|subject[^.\n]{0,30}\b\d+ char",
    re.IGNORECASE,
)


def _is_width_arithmetic_violation(v: dict) -> bool:
    """Drop model findings that hinge on character counting (table column
    padding, subject length, wrap width). lint-outbound.py enforces those
    deterministically on the raw source text; the model's arithmetic is
    unreliable (it measures rendered width, miscounts by one, and gives
    different answers for the same payload) and was the dominant
    false-positive class. Only the model's own prose is inspected, not
    payload_excerpt, so a finding ABOUT a table (e.g., a bare slug in a
    cell) is not swallowed by the table's dashes."""
    blob = " ".join(str(v.get(k, "")) for k in ("rule_quote", "suggested_fix"))
    return bool(WIDTH_ARITHMETIC_RE.search(blob))


def load_cache() -> dict:
    try:
        data = json.loads(CACHE_FILE.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_cache(cache: dict) -> None:
    now = time.time()
    entries = {
        k: v
        for k, v in cache.items()
        if isinstance(v, dict) and now - v.get("ts", 0) < CACHE_TTL_SEC
    }
    if len(entries) > CACHE_MAX_ENTRIES:
        oldest_first = sorted(entries.items(), key=lambda kv: kv[1].get("ts", 0))
        entries = dict(oldest_first[-CACHE_MAX_ENTRIES:])
    try:
        tmp = CACHE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(entries))
        tmp.replace(CACHE_FILE)
    except OSError:
        pass


def cache_key(rules_digest: str, surface: str, payload: str) -> str:
    return hashlib.sha256(
        f"{rules_digest}\0{surface}\0{payload}".encode()
    ).hexdigest()


def _is_phantom_char_violation(v: dict, payload: str) -> bool:
    """Drop model findings about forbidden characters that the payload does
    not actually contain. The deep-check prompt primes the model to hunt for
    smart quotes and em dashes, and it occasionally hallucinates them in
    straight-quoted text, re-rendering the excerpt with the curly characters
    it imagined. Character presence is mechanically checkable, so the model's
    claim is only accepted when the codepoints exist in the raw payload."""
    blob = " ".join(
        str(v.get(k, "")) for k in ("rule_quote", "payload_excerpt", "suggested_fix")
    ).lower()
    excerpt = v.get("payload_excerpt", "")
    for chars, keywords in FORBIDDEN_CHAR_CLASSES:
        about_class = any(kw in blob for kw in keywords) or any(
            c in excerpt for c in chars
        )
        if about_class and not any(c in payload for c in chars):
            return True
    return False


def main() -> int:
    if os.environ.get("CLAUDE_RULE_CHECK_DISABLE") == "1":
        return 0

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}
    if not isinstance(tool_input, dict):
        return 0

    items = extract_payloads(tool_name, tool_input)
    if not items:
        return 0

    rules = load_rules()
    if not rules:
        return 0

    # CLAUDE_RULE_CHECK_NO_CACHE=1 forces live checks (used by eval.py so
    # it measures the model, not the cache).
    use_cache = os.environ.get("CLAUDE_RULE_CHECK_NO_CACHE") != "1"
    cache = load_cache() if use_cache else {}
    cache_dirty = False
    # The digest covers the rule files AND this hook's own source: the
    # prompt template lives in the source, so a prompt edit must
    # invalidate cached verdicts just like a rule edit does.
    try:
        hook_source = Path(__file__).read_text()
    except OSError:
        hook_source = ""
    rules_digest = hashlib.sha256((rules + hook_source).encode()).hexdigest()[:16]

    all_violations: list[tuple[str, dict]] = []
    for surface, text in items:
        if not isinstance(text, str) or len(text.strip()) < 5:
            continue
        skip_match = SKIP_RE.search(text)
        if skip_match:
            reason = skip_match.group(1) or "no reason given"
            log(f"SKIP tool={tool_name} surface={surface} reason={reason}")
            continue
        # Identical payloads get identical verdicts: the deep check is
        # LLM-backed and non-deterministic, so a payload that passed once
        # must not fail on a later identical invocation (and vice versa).
        key = cache_key(rules_digest, surface, text)
        cached = cache.get(key)
        if isinstance(cached, dict):
            verdict = cached.get("verdict", "pass")
            violations = cached.get("violations", []) or []
            cached_note = " (cached)"
        else:
            verdict, violations = run_check(rules, surface, text)
            cached_note = ""
            if use_cache and verdict in ("pass", "fail"):
                cache[key] = {
                    "verdict": verdict,
                    "violations": violations,
                    "ts": time.time(),
                }
                cache_dirty = True
        if verdict == "fail":
            for v in violations:
                if _is_phantom_char_violation(v, text):
                    log(
                        f"PHANTOM tool={tool_name} surface={surface} "
                        f"dropped char finding: {v.get('rule_quote', '')[:80]}"
                    )
                    continue
                if _is_width_arithmetic_violation(v):
                    log(
                        f"ARITHMETIC tool={tool_name} surface={surface} "
                        f"dropped width finding: {v.get('rule_quote', '')[:80]}"
                    )
                    continue
                all_violations.append((surface, v))
        log(
            f"CHECK tool={tool_name} surface={surface} verdict={verdict} "
            f"violations={len(violations)}{cached_note}"
        )

    if cache_dirty:
        save_cache(cache)

    if not all_violations:
        return 0

    sys.stderr.write(
        "Deep rule-check violations. Fix the payload and retry. For a genuine "
        'false positive, add `<!-- rule-check: skip reason="..." -->` to the '
        "payload (logged for audit).\n\n"
    )
    for surface, v in all_violations:
        rule_file = v.get("rule_file", "?")
        rule_quote = v.get("rule_quote", "")
        excerpt = v.get("payload_excerpt", "")[:300]
        fix = v.get("suggested_fix", "")
        sys.stderr.write(f"  [{surface}] {rule_file}\n")
        sys.stderr.write(f"    rule:    {rule_quote}\n")
        sys.stderr.write(f"    payload: {excerpt}\n")
        sys.stderr.write(f"    fix:     {fix}\n\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
