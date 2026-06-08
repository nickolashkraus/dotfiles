#!/usr/bin/env python3
"""
Eval harness for ~/.claude/hooks/rule-check.py.

Feeds curated tool-call payloads to the hook subprocess, captures exit code
and stderr, and reports precision/recall/F1 plus per-case outcomes. Each
case asserts an expected verdict (pass|fail) and, when fail, the rule files
the violation should cite.

Run: python3 .claude/evals/rule-check/eval.py [--parallel N] [--filter sub]

Tests are isolated to the deep layer (rule-check.py) only; the cheap
regex layer (lint-outbound.py) is bypassed by invoking rule-check.py
directly via stdin, so we measure the deep layer in isolation.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HOOK = Path.home() / ".claude" / "hooks" / "rule-check.py"


def heredoc(body: str, tag: str = "EOF") -> str:
    return f"<<'{tag}'\n{body}\n{tag}"


def bash(cmd: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": cmd}}


def mcp(tool: str, **inp) -> dict:
    return {"tool_name": tool, "tool_input": inp}


TESTS: list[dict] = [
    # ---- Clean payloads (should pass) ----
    {
        "id": "clean_commit_subject_only",
        "category": "TN",
        "payload": bash("git commit -m 'Fix bug in user login flow'"),
        "expected": "pass",
    },
    {
        "id": "clean_commit_with_linear_slug",
        "category": "TN",
        "payload": bash(
            "git commit -m 'BYB-1234: Membership Upgrade Creates Duplicate Active Subscriptions in Stripe'"
        ),
        "expected": "pass",
    },
    {
        "id": "clean_pr_body_overview",
        "category": "TN",
        "payload": bash(
            "gh pr create --title 'Add membership upgrade gate' --body "
            + heredoc(
                "## Overview\n\nAdds a feature flag gate for the membership upgrade flow.\n\n"
                "## Implementation Details\n\nIntroduces a Postgres column `upgrade_eligible` "
                "on `members` and a service-layer accessor that reads it.\n\n"
                "## References\n\n"
                "- [BYB-1234](https://linear.app/x/BYB-1234): Add Membership Upgrade Gate\n"
            )
        ),
        "expected": "pass",
    },
    {
        "id": "trivial_pr_body_single_sentence",
        "category": "TN",
        "payload": bash(
            "gh pr create --title 'Bump pyright to 1.1.405' --body 'Routine version bump to pick up upstream type fixes.'"
        ),
        "expected": "pass",
    },
    {
        "id": "clean_linear_issue",
        "category": "TN",
        "payload": mcp(
            "mcp__linear__save_issue",
            title="Add Idempotency Key to Webhook Handler",
            description=(
                "## Overview\n\n"
                "Adds idempotency-key support to the Stripe webhook handler so retried "
                "deliveries do not double-record events.\n\n"
                "## Acceptance Criteria\n\n"
                "- Retried events with the same idempotency key are no-ops\n"
                "- Metrics emit on dedup hit\n\n"
                "## Implementation Details\n\n"
                "Stores the key in a new `webhook_events.idempotency_key` column with a "
                "unique index.\n\n"
                "## References\n\n"
                "- [Stripe webhook idempotency](https://stripe.com/docs/webhooks)\n"
            ),
        ),
        "expected": "pass",
    },
    {
        "id": "clean_slack_draft",
        "category": "TN",
        "payload": mcp(
            "mcp__claude_ai_Slack__slack_send_message_draft",
            channel="proj-payments",
            text="Heads up. Cutting the payments release at 3pm today; reply if you have a blocking PR.",
        ),
        "expected": "pass",
    },
    # ---- Deep-layer violations (semantic, regex cannot easily catch) ----
    {
        "id": "fail_this_pr_opener",
        "category": "TP",
        "payload": bash(
            "gh pr create --title 'Add upgrade gate' --body "
            + heredoc(
                "This PR adds a feature flag gate for the membership upgrade flow. "
                "It also introduces a Postgres column.\n\n"
                "## References\n\n- [BYB-1234](https://linear.app/x/BYB-1234): Add Upgrade Gate\n"
            )
        ),
        "expected": "fail",
        "expected_rule_substrings": ["git.md"],
    },
    {
        "id": "fail_in_this_pr_opener",
        "category": "TP",
        "payload": bash(
            "gh pr create --title 'Add upgrade gate' --body "
            + heredoc(
                "In this PR, I add a feature flag for the upgrade flow and a new column.\n\n"
                "## References\n\n- [BYB-1234](https://linear.app/x/BYB-1234): Add Upgrade Gate\n"
            )
        ),
        "expected": "fail",
        "expected_rule_substrings": ["git.md"],
    },
    {
        "id": "fail_commit_coauthor",
        "category": "TP",
        "payload": bash(
            "git commit -m "
            + heredoc(
                "Add upgrade gate column\n\nIntroduces upgrade_eligible column on members.\n\n"
                "Co-Authored-By: Claude <noreply@anthropic.com>"
            )
        ),
        "expected": "fail",
        "expected_rule_substrings": ["git.md"],
    },
    {
        "id": "fail_pr_closes_keyword",
        "category": "TP",
        "payload": bash(
            "gh pr create --title 'Add upgrade gate' --body "
            + heredoc(
                "Adds a feature flag gate for the membership upgrade flow.\n\n"
                "Closes: BYB-1234\n\n"
                "## References\n\n- [BYB-1234](https://linear.app/x/BYB-1234): Add Upgrade Gate\n"
            )
        ),
        "expected": "fail",
        "expected_rule_substrings": ["git.md"],
    },
    {
        "id": "fail_internal_path_leak",
        "category": "TP",
        "payload": bash(
            "gh pr create --title 'Add upgrade gate' --body "
            + heredoc(
                "Adds the upgrade gate documented in ~/nickolashkraus/agent-os/master/notes/daily/2026-06-08.md.\n\n"
                "## References\n\n- [BYB-1234](https://linear.app/x/BYB-1234): Add Upgrade Gate\n"
            )
        ),
        "expected": "fail",
        "expected_rule_substrings": ["general.md"],
    },
    {
        "id": "fail_inline_internal_context_leak",
        "category": "TP",
        "payload": bash(
            "gh pr create --title 'Add upgrade gate' --body "
            + heredoc(
                "Adds the upgrade gate. See my scratch notes in agent-os for the design exploration.\n\n"
                "## References\n\n- [BYB-1234](https://linear.app/x/BYB-1234): Add Upgrade Gate\n"
            )
        ),
        "expected": "fail",
        "expected_rule_substrings": ["general.md"],
    },
    {
        "id": "fail_em_dash_in_pr_body",
        "category": "TP",
        "payload": bash(
            "gh pr create --title 'Add upgrade gate' --body "
            + heredoc(
                "Adds the upgrade gate — the column lives on `members`.\n\n"
                "## References\n\n- [BYB-1234](https://linear.app/x/BYB-1234): Add Upgrade Gate\n"
            )
        ),
        "expected": "fail",
        "expected_rule_substrings": ["typography.md"],
    },
    {
        "id": "fail_smart_quotes_in_linear",
        "category": "TP",
        "payload": mcp(
            "mcp__linear__save_issue",
            title="Add idempotency key",
            description=(
                "## Overview\n\nAdds the “idempotency key” to the webhook handler.\n\n"
                "## Acceptance Criteria\n\n- Retried events are no-ops\n"
            ),
        ),
        "expected": "fail",
        "expected_rule_substrings": ["typography.md"],
    },
    {
        "id": "fail_pr_test_plan_boilerplate",
        "category": "TP",
        "payload": bash(
            "gh pr create --title 'Bump pyright' --body "
            + heredoc(
                "Routine version bump to pick up upstream type fixes.\n\n"
                "## Test plan\n\n- [ ] CI passes\n- [ ] pyright still happy\n"
            )
        ),
        "expected": "fail",
        "expected_rule_substrings": ["git.md"],
    },
    {
        "id": "fail_bullet_lowercase_after_colon",
        "category": "TP",
        "payload": bash(
            "gh pr create --title 'Add upgrade gate' --body "
            + heredoc(
                "Adds the upgrade gate.\n\n"
                "- **Implementation**: introduces a new Postgres column and a service accessor\n"
                "- **Risk**: no production data is touched in this PR\n\n"
                "## References\n\n- [BYB-1234](https://linear.app/x/BYB-1234): Add Upgrade Gate\n"
            )
        ),
        "expected": "fail",
        "expected_rule_substrings": ["typography.md"],
    },
    {
        "id": "fail_bullet_dash_instead_of_colon",
        "category": "TP",
        "payload": bash(
            "gh pr create --title 'Add upgrade gate' --body "
            + heredoc(
                "Adds the upgrade gate.\n\n"
                "- **Implementation** - Introduces a new Postgres column and a service accessor.\n"
                "- **Risk** - No production data is touched in this PR.\n\n"
                "## References\n\n- [BYB-1234](https://linear.app/x/BYB-1234): Add Upgrade Gate\n"
            )
        ),
        "expected": "fail",
        "expected_rule_substrings": ["typography.md"],
    },
    {
        "id": "fail_commit_subject_past_tense",
        "category": "TP",
        "payload": bash(
            "git commit -m 'Added upgrade gate column to members table.'"
        ),
        "expected": "fail",
        "expected_rule_substrings": ["git.md"],
    },
    {
        "id": "fail_linear_issue_missing_sections",
        "category": "TP",
        "payload": mcp(
            "mcp__linear__save_issue",
            title="Add idempotency key to webhook handler",
            description=(
                "We should add an idempotency key to the webhook handler so retried "
                "Stripe deliveries do not double-record. The key would live on the "
                "webhook_events table with a unique index. This work depends on the "
                "Stripe restricted-key rotation completing first."
            ),
        ),
        "expected": "fail",
        "expected_rule_substrings": ["linear.md"],
    },
    # ---- gh pr comment / gh issue comment / gh issue create ----
    {
        "id": "clean_pr_comment",
        "category": "TN",
        "payload": bash(
            "gh pr comment 1234 --body 'Resolved in [a1b2c3](https://github.com/org/repo/commit/a1b2c3). Idempotency key added as suggested.'"
        ),
        "expected": "pass",
    },
    {
        "id": "fail_pr_comment_em_dash",
        "category": "TP",
        "payload": bash(
            "gh pr comment 1234 --body 'Will address — see follow-up in linked thread for context on the design.'"
        ),
        "expected": "fail",
        "expected_rule_substrings": ["typography.md"],
    },
    {
        "id": "clean_issue_comment",
        "category": "TN",
        "payload": bash(
            "gh issue comment 567 --body 'Reproduced locally; root cause is the missing index on `members.email`. Fix in PR #1234.'"
        ),
        "expected": "pass",
    },
    {
        "id": "fail_issue_create_internal_path",
        "category": "TP",
        "payload": bash(
            "gh issue create --title 'Track upgrade-gate followups' --body "
            + heredoc(
                "Captures the loose ends from rolling out the upgrade gate. Full design notes live at ~/nickolashkraus/agent-os/master/notes/upgrade-gate.md.\n"
            )
        ),
        "expected": "fail",
        "expected_rule_substrings": ["general.md"],
    },
    # ---- gh api with -f body=... ----
    {
        "id": "clean_gh_api_body",
        "category": "TN",
        "payload": bash(
            "gh api repos/org/repo/issues/123/comments -f body='Closing as resolved by [PR #200](https://github.com/org/repo/pull/200).'"
        ),
        "expected": "pass",
    },
    {
        "id": "fail_gh_api_body_smart_quotes",
        "category": "TP",
        "payload": bash(
            "gh api repos/org/repo/issues/123/comments -f body='Will reopen if the “fix” regresses on the next deploy.'"
        ),
        "expected": "fail",
        "expected_rule_substrings": ["typography.md"],
    },
    # ---- Notion ----
    {
        "id": "clean_notion_create_page",
        "category": "TN",
        "payload": mcp(
            "mcp__notion__notion-create-pages",
            pages=[
                {
                    "properties": {"title": "Membership Upgrade Rollout Plan"},
                    "content": (
                        "## Overview\n\n"
                        "Captures the rollout plan for the membership-upgrade feature flag.\n\n"
                        "## Phases\n\n"
                        "- **Internal**: Enable in Dev and Staging; smoke-test the upgrade flow.\n"
                        "- **Beta cohort**: Ramp to 5% of Prod members for one week.\n"
                        "- **Full ramp**: 100% rollout after beta metrics clear thresholds.\n\n"
                        "## References\n\n"
                        "- [Stripe webhook idempotency](https://stripe.com/docs/webhooks)\n"
                    ),
                }
            ],
        ),
        "expected": "pass",
    },
    {
        "id": "fail_notion_update_internal_paths",
        "category": "TP",
        "payload": mcp(
            "mcp__notion__notion-update-page",
            data={
                "page_id": "abc-123",
                "command": "replace_content",
                "new_str": (
                    "Updates the rollout plan with the latest review notes from "
                    "~/nickolashkraus/agent-os/master/notes/daily/2026-06-08.md "
                    "and the agent-os scratch pad."
                ),
            },
        ),
        "expected": "fail",
        "expected_rule_substrings": ["general.md"],
    },
    # ---- Gmail ----
    {
        "id": "clean_gmail_draft",
        "category": "TN",
        "payload": mcp(
            "mcp__claude_ai_Gmail__create_draft",
            to=["team@example.com"],
            subject="Upgrade-gate rollout status",
            body=(
                "Quick status on the upgrade-gate rollout. The beta cohort is "
                "live and metrics look clean after 48 hours. Planning the full "
                "ramp for Monday pending one more review of the dashboard."
            ),
        ),
        "expected": "pass",
    },
    {
        "id": "fail_gmail_draft_internal_path",
        "category": "TP",
        "payload": mcp(
            "mcp__claude_ai_Gmail__create_draft",
            to=["team@example.com"],
            subject="Upgrade-gate followups",
            body=(
                "Followups from this morning's review are tracked in "
                "~/nickolashkraus/agent-os/master/notes/upgrade-gate.md. "
                "Take a look before the Monday sync."
            ),
        ),
        "expected": "fail",
        "expected_rule_substrings": ["general.md"],
    },
    # ---- Multi-violation: one payload, multiple distinct violations ----
    {
        "id": "fail_multi_violation",
        "category": "TP",
        "payload": bash(
            "gh pr create --title 'Add upgrade gate' --body "
            + heredoc(
                "This PR adds a feature flag gate — see ~/nickolashkraus/agent-os/notes.\n\n"
                "Closes: BYB-1234\n\n"
                "## References\n\n"
                "- [BYB-1234](https://linear.app/x/BYB-1234): Add Upgrade Gate\n"
            )
        ),
        "expected": "fail",
        "expected_rule_substrings": ["git.md", "general.md", "typography.md"],
        "min_violations": 3,
    },
    # ---- Truncation: payload exceeds MAX_PAYLOAD_CHARS (40K) ----
    {
        "id": "edge_payload_truncation",
        "category": "TN_or_TP",
        "payload": bash(
            "gh pr create --title 'Clean huge body' --body "
            + heredoc(
                "Adds a feature flag for membership upgrades. "
                + ("This is a benign sentence that repeats to stretch the payload. " * 1200)
                + "End of body."
            )
        ),
        "expected": "any",
        "smoke_only": True,
    },
    # ---- Edge cases ----
    {
        "id": "edge_override_sentinel_bypasses",
        "category": "TN",
        "payload": bash(
            "gh pr create --title 'Add upgrade gate' --body "
            + heredoc(
                "<!-- rule-check: skip reason=\"intentional non-standard format for migration callout\" -->\n\n"
                "This PR adds a feature flag gate — see ~/nickolashkraus/agent-os/notes.\n"
            )
        ),
        "expected": "pass",
    },
    {
        "id": "edge_too_short_payload",
        "category": "TN",
        "payload": bash("git commit -m 'OK'"),
        "expected": "pass",
    },
    {
        "id": "edge_unrelated_bash_command",
        "category": "TN",
        "payload": bash("ls -la /tmp"),
        "expected": "pass",
    },
]


def run_one(test: dict) -> dict:
    payload_bytes = json.dumps(test["payload"]).encode()
    started = time.monotonic()
    try:
        proc = subprocess.run(
            [str(HOOK)],
            input=payload_bytes,
            capture_output=True,
            timeout=180,
        )
        elapsed = time.monotonic() - started
        actual_verdict = "fail" if proc.returncode == 2 else "pass"
        stderr_text = proc.stderr.decode(errors="replace")
        cited_rules: list[str] = []
        violation_count = 0
        for line in stderr_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("[") and "]" in stripped:
                violation_count += 1
            for prefix in ("CLAUDE.md", "rules/"):
                idx = line.find(prefix)
                if idx >= 0:
                    tail = line[idx:].split()[0].rstrip(":").rstrip(",")
                    if tail not in cited_rules:
                        cited_rules.append(tail)

        expected = test["expected"]
        smoke_only = test.get("smoke_only", False)
        min_violations = test.get("min_violations", 0)

        if smoke_only:
            ok = proc.returncode in (0, 2)
        elif expected == "any":
            ok = proc.returncode in (0, 2)
        else:
            ok = actual_verdict == expected
            if ok and expected == "fail" and min_violations:
                if violation_count < min_violations:
                    ok = False

        return {
            "id": test["id"],
            "category": test["category"],
            "expected": expected,
            "actual": actual_verdict,
            "ok": ok,
            "elapsed_s": round(elapsed, 1),
            "cited_rules": cited_rules,
            "violation_count": violation_count,
            "min_violations": min_violations,
            "expected_rule_substrings": test.get("expected_rule_substrings", []),
            "stderr": stderr_text[:1500],
        }
    except subprocess.TimeoutExpired:
        return {
            "id": test["id"],
            "category": test["category"],
            "expected": test["expected"],
            "actual": "timeout",
            "ok": False,
            "elapsed_s": 180.0,
            "cited_rules": [],
            "violation_count": 0,
            "min_violations": test.get("min_violations", 0),
            "expected_rule_substrings": test.get("expected_rule_substrings", []),
            "stderr": "TIMEOUT",
        }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--parallel", type=int, default=4)
    p.add_argument("--filter", default="")
    args = p.parse_args()

    cases = [t for t in TESTS if args.filter in t["id"]]
    print(f"Running {len(cases)} cases (parallel={args.parallel})...\n")

    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        futures = {pool.submit(run_one, t): t for t in cases}
        for fut in as_completed(futures):
            r = fut.result()
            results.append(r)
            mark = "PASS" if r["ok"] else "FAIL"
            extra = ""
            if r["expected"] == "fail" and r["actual"] == "fail":
                wanted = r["expected_rule_substrings"]
                cited = r["cited_rules"]
                missing = [s for s in wanted if not any(s in c for c in cited)]
                if missing:
                    extra = f" [missing rule cite: {missing}, cited: {cited}]"
                if r["min_violations"] and r["violation_count"] < r["min_violations"]:
                    extra += (
                        f" [violations={r['violation_count']}, "
                        f"want>={r['min_violations']}]"
                    )
            print(
                f"  [{mark}] {r['id']:<45} "
                f"expected={r['expected']:<4} actual={r['actual']:<5} "
                f"t={r['elapsed_s']:>5}s{extra}"
            )

    results.sort(key=lambda r: r["id"])
    print()
    total = len(results)
    ok = sum(1 for r in results if r["ok"])
    tp = sum(
        1 for r in results
        if r["expected"] == "fail" and r["actual"] == "fail"
    )
    fp = sum(
        1 for r in results
        if r["expected"] == "pass" and r["actual"] == "fail"
    )
    fn = sum(
        1 for r in results
        if r["expected"] == "fail" and r["actual"] == "pass"
    )
    tn = sum(
        1 for r in results
        if r["expected"] == "pass" and r["actual"] == "pass"
    )
    precision = tp / (tp + fp) if tp + fp else float("nan")
    recall = tp / (tp + fn) if tp + fn else float("nan")
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else float("nan")
    )
    print(f"Overall: {ok}/{total} pass")
    print(f"  TP={tp} FP={fp} FN={fn} TN={tn}")
    print(f"  precision={precision:.2f} recall={recall:.2f} f1={f1:.2f}")

    failures = [r for r in results if not r["ok"]]
    if failures:
        print("\n--- Failures ---\n")
        for r in failures:
            print(f"[{r['id']}] expected={r['expected']} actual={r['actual']}")
            print(f"  stderr:\n{r['stderr']}\n")

    print("\n--- Rule citations on TP cases ---\n")
    for r in results:
        if r["expected"] == "fail" and r["actual"] == "fail":
            print(f"  {r['id']}: {r['cited_rules']}")

    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
