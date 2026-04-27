---
name: worktree-cleanup
description: Safely clean merged or stale Git worktrees. Use when the user asks to clean merged worktrees, remove stale worktrees, prune Git worktree metadata, or fix worktrees whose upstream branch is gone. Always inventory worktrees first, skip dirty worktrees, and remove worktrees through Git rather than raw directory deletion.
---

# Worktree Cleanup

## Workflow

1. Identify the worktree manager:
   - For a normal repo, use the repo root.
   - For a bare worktree manager, `git -C <path> rev-parse --is-bare-repository` should return `true`.
2. Inventory before mutating:
   - `git -C <base> worktree list --porcelain`
   - `git -C <base> symbolic-ref --quiet --short refs/remotes/origin/HEAD || true`
   - `git -C <base> branch --merged <base-ref> --format='%(refname:short)'`
   - `git -C <base> for-each-ref --format='%(refname:short)%09%(upstream:track)' refs/heads`
3. Choose merge bases deliberately. Use the remote default branch when appropriate, but also check project-specific long-lived branches such as `origin/dev` and release bases like `origin/main` when the repo uses both.
4. Build a candidate list with path, branch, size, status, and reason:
   - `merged-origin-dev`
   - `merged-origin-main`
   - `upstream-gone`
   - `prunable-metadata`
5. Skip any worktree with `git -C <worktree> status --porcelain` output. Report the dirty files instead of deleting.
6. Remove clean candidates with `git -C <base> worktree remove <path>`.
7. Delete the corresponding local branch only after independently verifying it is merged into the selected base or its upstream is gone:
   - Prefer `git -C <base> branch -d <branch>` for branches merged into their configured upstream.
   - Use `git -C <base> branch -D <branch>` only when a separate `branch --merged <base-ref>` check already proved the branch is merged, or when the branch upstream is gone and the user asked to remove stale branches.
8. Run `git -C <base> worktree prune --verbose` to remove missing-worktree metadata.
9. Verify with another candidate scan and report anything skipped.

## Safety Rules

- Do not use `rm -rf` for valid Git worktrees. Use `git worktree remove` so Git metadata is updated correctly.
- Do not remove the main/default worktree, active long-lived branches such as `dev` or `main`, or a dirty worktree.
- Treat linked worktrees as shared state. A branch may appear in other worktrees through shared metadata; deduplicate by actual worktree path and current branch.
- If `git branch -d` refuses because a branch tracks an unexpected upstream, only force-delete after verifying the branch is merged into the intended base.
- If a worktree entry is already missing and marked prunable, do not recreate or manually edit metadata. Use `git worktree prune --verbose`.

## Reporting

Before cleanup, report the proposed removals grouped by reason and explicitly list dirty skips. After cleanup, report:

- Removed worktree count.
- Deleted branch count.
- Pruned metadata count if visible in command output.
- Any skipped dirty worktrees with paths to modified files.
- Final `git worktree list` or a concise summary of remaining worktrees.
