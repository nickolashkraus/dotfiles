---
name: snapshot
description: >
  Snapshots dirty working tree to a dated backup branch, then restores the
  dirty state on the default branch.
disable-model-invocation: false
allowed-tools: Bash, Read, Skill
---

You are creating a snapshot of the current dirty working tree. Follow every
step in order.

## Step 1: Determine the default branch

```
git remote show origin | grep 'HEAD branch' | awk '{print $NF}'
```

Verify you are currently on the default branch. If not, abort and tell the user
which branch they are on.

## Step 2: Determine the snapshot branch name

The naming convention is `SNAPSHOT-YYYY-MM-DD.XX`, where `YYYY-MM-DD` is
today's date and `XX` is an incrementing integer starting at 1 (padded).

List existing snapshot branches for today:

```
git branch -a | grep "SNAPSHOT-$(date +%Y-%m-%d)" | sort -t. -k2 -n
```

Pick the next available `XX`. If no branches exist for today, use `.01`.

## Step 3: Create the snapshot branch and commit

1. Create and switch to the snapshot branch:
   ```
   git checkout -b SNAPSHOT-YYYY-MM-DD.XX
   ```
2. Run `/commit` to stage and commit all changes.

## Step 4: Push the snapshot branch

```
git push -u origin SNAPSHOT-YYYY-MM-DD.XX
```

## Step 5: Return to the default branch with dirty state

1. Switch back to the default branch:
   ```
   git checkout <default-branch>
   ```
2. Cherry-pick the snapshot commit without committing, restoring the dirty
   working tree:
   ```
   git cherry-pick --no-commit <commit-sha>
   ```
3. Unstage everything so the state is fully dirty (unstaged), matching the
   original state:
   ```
   git reset HEAD
   ```

## Step 6: Confirm

Print the snapshot branch name and confirm that the default branch is back to
its original dirty state (`git status`).
