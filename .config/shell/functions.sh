#!/usr/bin/env zsh
###############################################################################
# Shell Functions
#
# DESCRIPTION
#   My personal shell functions.
#
#   A shell function is a reusable block of code that you can define once and
#   then call multiple times by name. Functions are more powerful than aliases
#   because they can accept parameters, contain complex logic, and span
#   multiple lines.
#
#   This file is sourced by .zshrc.
#
# INSTALLATION
#   Symlink file to $XDG_CONFIG_HOME/shell/functions.sh:
#
#     ln -s .config/shell/functions.sh $XDG_CONFIG_HOME/shell/functions.sh
###############################################################################

fh_init() {
  # Auth gcloud (Function Dev) + read-only `gws`.
  gcp_auth function-dev --gws
  # Auth gcloud (Function Prod).
  gcp_auth function-prod
}

# See: https://junegunn.github.io/fzf/tips/ripgrep-integration/
rfv() (
  RELOAD='reload:rg --column --color=always --smart-case {q} || :'
  OPENER='if [[ $FZF_SELECT_COUNT -eq 0 ]]; then
            vim {1} +{2}     # No selection. Open the current line in Vim.
          else
            vim +cw -q {+f}  # Build quickfix list for the selected items.
          fi'
  fzf --disabled --ansi --multi --tmux \
    --bind "start:$RELOAD" --bind "change:$RELOAD" \
    --bind "enter:become:$OPENER" \
    --bind "ctrl-o:execute:$OPENER" \
    --bind 'alt-a:select-all,alt-d:deselect-all,ctrl-/:toggle-preview' \
    --delimiter : \
    --preview 'bat --style=full --color=always --highlight-line {2} {1}' \
    --preview-window '~4,+{2}+4/3,<80(up)' \
    --query "$*"
)

gcp_current_config() (
  gcloud config configurations list --filter="is_active:true" --format="value(name)" 2>/dev/null
)

# Automatically activate the Poetry environment when entering a directory that
# belongs to a Poetry project (the current directory or any ancestor contains a
# pyproject.toml with a Poetry section). Deactivates and restores the default
# pyenv virtualenv when leaving the project tree.
#
# The Python version is resolved from the `python` dependency in pyproject.toml
# (e.g., "^3.12", "~=3.12", ">=3.12") and matched to the latest installed
# pyenv version for that minor release.
#
# The activated project root is tracked in _POETRY_ACTIVE_ROOT so that moving
# between subdirectories of the same project (or re-entering it) is a no-op,
# avoiding a redundant ~0.3s `poetry env activate` on every chpwd.
_poetry_auto_activate() {
  # Walk up to the nearest ancestor containing a pyproject.toml.
  local root=$PWD
  while [[ $root != / && ! -f $root/pyproject.toml ]]; do
    root=${root:h}
  done

  if [[ -f $root/pyproject.toml ]] && grep -q '\[tool\.poetry\]' $root/pyproject.toml 2>/dev/null; then
    # Already active for this project: nothing to do.
    [[ $root == $_POETRY_ACTIVE_ROOT ]] && return

    # Extract the minor version (e.g., "3.12") from the Python dependency.
    local py_constraint
    py_constraint=$(grep -E '^\s*python\s*=' $root/pyproject.toml | head -1 | grep -oE '[0-9]+\.[0-9]+')
    if [[ -z "$py_constraint" ]]; then
      return
    fi

    # Find the latest installed pyenv version matching that minor release.
    local py_version
    py_version=$(pyenv versions --bare 2>/dev/null |
      grep -E "^${py_constraint}\.[0-9]+$" |
      sort -t. -k3 -n |
      tail -1)
    if [[ -z "$py_version" ]]; then
      echo "pyenv: no installed version matches ${py_constraint}.x"
      return
    fi

    # Deactivate any active virtualenv before activating the new one.
    deactivate 2>/dev/null
    pyenv deactivate 2>/dev/null
    pyenv shell --unset 2>/dev/null
    pyenv shell "$py_version"
    eval "$(poetry env activate 2>/dev/null)"
    export _POETRY_ACTIVE_ROOT=$root
  elif [[ -n "$_POETRY_ACTIVE_ROOT" ]]; then
    # Left the Poetry project tree. Restore defaults.
    unset _POETRY_ACTIVE_ROOT
    deactivate 2>/dev/null
    pyenv shell --unset
    pyenv activate default 2>/dev/null
  fi
}

autoload -U add-zsh-hook
add-zsh-hook chpwd _poetry_auto_activate

# Activate a gcloud configuration and authenticate. Runs `gcloud auth login`
# and `gcloud auth application-default login` after switching configurations.
#
# NOTE: Adding gmail scopes (gmail.readonly, gmail.modify) causes "This app
# is blocked" from Google. Use the Gmail MCP connector via Claude.ai instead.
#
# Options:
#   --gws  Include Google Workspace scopes (cloud-platform, drive.readonly)
#          and save a per-profile ADC file for the gws wrapper.
#
# Usage:
#   gcp_auth                 # Authenticate with the current configuration.
#   gcp_auth personal        # Switch to "personal" and authenticate.
#   gcp_auth function-dev    # Switch to "function-dev" and authenticate.
#   gcp_auth --gws           # Authenticate with Google Workspace scopes.
#   gcp_auth personal --gws  # Switch to "personal" and authenticate with
#                            # Google Workspace scopes.
gcp_auth() {
  local config="" gws=0
  for arg in "$@"; do
    case "$arg" in
      --gws) gws=1 ;;
      *) config="$arg" ;;
    esac
  done

  if [[ -n "$config" ]]; then
    gcloud config configurations activate "$config" || return 1
  fi

  gcloud auth login || return 1

  if ((gws)); then
    gcloud auth application-default login \
      --scopes="https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/drive.readonly" ||
      return 1
    local active
    active=$(gcp_current_config)
    cp ~/.config/gcloud/application_default_credentials.json \
      ~/.config/gcloud/adc-"${active}".json
    echo "Saved ADC for ${active}."
  else
    gcloud auth application-default login || return 1
  fi
}

# Switch gws between Personal (native OAuth) and Function Health (gcloud ADC).
#
# Usage:
#   gws_use personal  # Use native gws auth (full drive scope).
#   gws_use function  # Use gcloud ADC (drive.readonly).
gws_use() {
  case "$1" in
    personal | function) export GWS_PROFILE="$1" ;;
    *) echo "Usage: gws_use personal|function" && return 1 ;;
  esac
  echo "gws profile: $GWS_PROFILE"
}

# Wrap gws (Google Workspace CLI) to automatically inject a Google access token
# via per-profile ADC credentials when using the Function Health profile. This
# bypasses `gws auth setup`, which requires creating an OAuth client in the GCP
# project.
#
# When GWS_PROFILE is "personal", gws uses its native auth (via `gws auth
# login`). When "function", it injects a token from the saved Function Health
# ADC file. Auth each profile once with `gcp_auth <config> --gws` to save the
# ADC credentials.
gws() {
  if [[ "$GWS_PROFILE" == "personal" ]]; then
    command gws "$@"
  else
    local adc=~/.config/gcloud/adc-function-dev.json
    if [[ ! -f "$adc" ]]; then
      echo "No saved ADC for function-dev. Run: gcp_auth function-dev --gws"
      return 1
    fi
    local project
    project=$(python3 -c "import json; print(json.load(open('$adc')).get('quota_project_id',''))" 2>/dev/null)
    GOOGLE_WORKSPACE_CLI_TOKEN=$(
      GOOGLE_APPLICATION_CREDENTIALS="$adc" \
        gcloud auth application-default print-access-token 2>/dev/null
    ) GOOGLE_WORKSPACE_PROJECT_ID="$project" command gws "$@"
  fi
}

_pr_body_lint() {
  # Run the outbound hooks against a body file exactly as a tool call would.
  #
  # Editing a description on GitHub skips these entirely, so this is the only
  # path where the typography rules actually gate the text. lint-outbound.py
  # is deterministic and free; rule-check.py costs a Sonnet call, so it only
  # runs once the cheap pass is clean.
  local file=$1 number=$2 payload
  payload=$(
    python3 -c 'import json, sys; print(json.dumps({"tool_name": "Bash", "tool_input": {"command": sys.argv[1]}}))' \
      "gh pr edit $number --body-file $file"
  ) || return 1
  print -r -- "$payload" | python3 "$HOME/.claude/hooks/lint-outbound.py" || return 1
  print -r -- "$payload" | python3 "$HOME/.claude/hooks/rule-check.py" || return 1
}

pr_body() {
  # Review and edit a pull request description without opening a browser.
  #
  #   pr_body [<pr>]         Fetch, edit in $EDITOR, lint, show the diff, push.
  #   pr_body --show [<pr>]  Render the description GitHub currently has.
  #   pr_body --diff [<pr>]  Show what the local buffer would change.
  #
  # The buffer lives in the worktree's own gitdir, which in a worktree layout
  # sits outside the checkout, so it is never committable and each worktree
  # keeps its own. A pristine copy of what GitHub returned sits beside it.
  # That copy is what makes an unchanged body skip the push, and what catches
  # an edit someone else made while the buffer was open: without it, a push
  # silently overwrites them.
  local mode=edit
  while [[ $1 == --* ]]; do
    case $1 in
      --show) mode=show ;;
      --diff) mode=diff ;;
      *) print -u2 "pr_body: unknown flag $1"; return 1 ;;
    esac
    shift
  done

  local gitdir
  gitdir=$(git rev-parse --git-dir 2>/dev/null) || {
    print -u2 "pr_body: not a git repository"
    return 1
  }

  local -a target=()
  [[ -n $1 ]] && target=("$1")

  local meta
  meta=$(gh pr view "${target[@]}" --json number,title --jq '[.number, .title] | @tsv' 2>/dev/null) || {
    print -u2 "pr_body: no pull request found; pass a number or URL"
    return 1
  }
  local number title
  IFS=$'\t' read -r number title <<< "$meta"

  local file="$gitdir/pr-body.md"
  local remote="$gitdir/pr-body.remote.md"
  local fetched="$gitdir/pr-body.fetched.md"

  gh pr view "$number" --json body --jq .body > "$fetched" || return 1

  if [[ $mode == show ]]; then
    if (( $+commands[bat] )); then
      bat --style=plain --language=md --paging=never "$fetched"
    else
      cat "$fetched"
    fi
    rm -f "$fetched"
    return 0
  fi

  # The buffer predates a change made on GitHub, so pushing it would discard
  # that change. Show what would be lost before going further.
  if [[ -f $file && -f $remote ]] && ! cmp -s "$remote" "$fetched"; then
    print -u2 "pr_body: #$number changed on GitHub since this buffer was fetched."
    diff -u --label "what you fetched" --label "GitHub now" "$remote" "$fetched" >&2
    print -u2 ""
    print -u2 "Pushing the buffer discards that. To start from GitHub's version:"
    print -u2 "  rm $file"
    if ! read -q "?Keep the local buffer anyway? [y/N] "; then
      print
      rm -f "$fetched"
      return 1
    fi
    print
  fi

  [[ -f $file ]] || cp "$fetched" "$file"
  cp "$fetched" "$remote"
  rm -f "$fetched"

  if [[ $mode == diff ]]; then
    diff -u --label "#$number on GitHub" --label "your local buffer" "$remote" "$file"
    return $?
  fi

  ${EDITOR:-vim} "$file" || return 1

  if cmp -s "$file" "$remote"; then
    print "pr_body: #$number unchanged, nothing to push."
    return 0
  fi

  diff -u --label "#$number on GitHub" --label "your local buffer" "$remote" "$file"
  print

  _pr_body_lint "$file" "$number" || {
    print -u2 "pr_body: #$number not pushed; the buffer is kept at $file"
    return 1
  }

  # PR_BODY_ASSUME_YES exists so this is scriptable, and because the prompt
  # reads /dev/tty: without it there is no way to reach the push from a
  # non-interactive shell, which also makes the push path untestable.
  if [[ -z $PR_BODY_ASSUME_YES ]]; then
    if [[ ! -t 0 ]]; then
      print -u2 "pr_body: no terminal to confirm on; set PR_BODY_ASSUME_YES=1 to push"
      print -u2 "pr_body: #$number not pushed; the buffer is kept at $file"
      return 1
    fi
    if ! read -q "?Push this description to #$number? [y/N] "; then
      print
      print "pr_body: #$number not pushed; the buffer is kept at $file"
      return 1
    fi
    print
  fi

  gh pr edit "$number" --body-file "$file" || return 1
  cp "$file" "$remote"
  print "pr_body: updated #$number ($title)"
}

pr_threads() {
  # List and resolve pull request review threads without opening a browser.
  #
  #   pr_threads [<pr>]                    List the unresolved threads.
  #   pr_threads --all [<pr>]              List resolved ones too.
  #   pr_threads --resolve 2,5 [<pr>]      Resolve by listing number.
  #   pr_threads --resolve replied [<pr>]  Resolve every thread you answered.
  #   pr_threads --resolve all [<pr>]      Resolve every unresolved thread.
  #   pr_threads --unresolve 2 [<pr>]      Put one back.
  #
  # `gh` has no command for this, so it goes through the GraphQL mutations
  # resolveReviewThread and unresolveReviewThread. Numbers come from the
  # listing, which is cached per pull request in the worktree's gitdir, so
  # `--resolve` acts on exactly what was printed.
  #
  # `replied` is the one to reach for after a round of bot review: it resolves
  # only the threads that already carry an answer from you, and leaves
  # anything still unanswered alone.
  local mode=list selector=""
  while [[ $1 == --* ]]; do
    case $1 in
      --all) mode=list_all ;;
      --resolve) mode=resolve; selector=$2; shift ;;
      --unresolve) mode=unresolve; selector=$2; shift ;;
      *) print -u2 "pr_threads: unknown flag $1"; return 1 ;;
    esac
    shift
  done
  if [[ $mode == (resolve|unresolve) && -z $selector ]]; then
    print -u2 "pr_threads: $mode needs numbers, or 'replied', or 'all'"
    return 1
  fi

  local gitdir
  gitdir=$(git rev-parse --git-dir 2>/dev/null) || {
    print -u2 "pr_threads: not a git repository"
    return 1
  }

  local -a target=()
  [[ -n $1 ]] && target=("$1")
  local number
  number=$(gh pr view "${target[@]}" --json number --jq .number 2>/dev/null) || {
    print -u2 "pr_threads: no pull request found; pass a number or URL"
    return 1
  }
  local owner repo
  IFS=/ read -r owner repo <<< "$(gh repo view --json nameWithOwner --jq .nameWithOwner)"

  local cache="$gitdir/pr-threads.$number.tsv"
  local me
  me=$(gh api user --jq .login)

  if [[ $mode == (list|list_all) ]]; then
    gh api graphql -F owner="$owner" -F repo="$repo" -F pr="$number" -f query='
      query($owner:String!, $repo:String!, $pr:Int!) {
        repository(owner:$owner, name:$repo) { pullRequest(number:$pr) {
          reviewThreads(first:100) { nodes {
            id isResolved isOutdated path line
            comments(first:50) { nodes { author { login } body } } } } } } }' \
      --jq '.data.repository.pullRequest.reviewThreads.nodes[] | [
              .id, (.isResolved|tostring), (.isOutdated|tostring),
              (.path // "-"), ((.line // 0)|tostring),
              (.comments.nodes[0].author.login // "-"),
              ([.comments.nodes[].author.login] | join(",")),
              ((.comments.nodes[0].body | split("\n")
                 | map(select(length > 0 and (startswith("<!--") | not)))
                 | (map(select(startswith("**"))) + .) | .[0]) // "")
            ] | @tsv' > "$cache" || return 1

    MODE=$mode ME=$me python3 - "$cache" <<'PY'
import os, sys
from pathlib import Path

rows = [l.split("\t") for l in Path(sys.argv[1]).read_text().splitlines() if l.strip()]
show_all = os.environ["MODE"] == "list_all"
me = os.environ["ME"]
shown = 0
for i, r in enumerate(rows, 1):
    _id, resolved, outdated, path, line, author, participants, title = (r + [""] * 8)[:8]
    if resolved == "true" and not show_all:
        continue
    shown += 1
    flags = "resolved" if resolved == "true" else "open"
    if outdated == "true":
        flags += ",outdated"
    if me in participants.split(",")[1:]:
        flags += ",replied"
    title = title.lstrip("# ").strip()
    if len(title) > 78:
        title = title[:77] + "…"
    where = f"{path}:{line}" if line != "0" else path
    print(f"{i:>3}  {flags:<22}  {author:<12}  {where}")
    print(f"     {title}")
if not shown:
    print("No unresolved threads." if not show_all else "No threads.")
PY
    return 0
  fi

  [[ -f $cache ]] || {
    print -u2 "pr_threads: run the listing first so the numbers mean something"
    return 1
  }

  local mutation=resolveReviewThread
  [[ $mode == unresolve ]] && mutation=unresolveReviewThread

  local -a ids=()
  local -a labels=()
  local line_data
  local -i idx=0
  while IFS=$'\t' read -r tid resolved outdated tpath tline tauthor tparts ttitle; do
    (( idx++ ))
    local want=0
    case $selector in
      all) [[ $resolved == false ]] && want=1 ;;
      replied)
        [[ $resolved == false ]] || continue
        # The first comment is the bot's; a later one from you is the answer.
        [[ ",${tparts}," == *",${me},"* && ${tparts%%,*} != "$me" ]] && want=1
        ;;
      *) [[ ",${selector}," == *",${idx},"* ]] && want=1 ;;
    esac
    if (( want )); then
      ids+=("$tid")
      labels+=("$idx ${tpath}:${tline}")
    fi
  done < "$cache"

  if (( ${#ids} == 0 )); then
    print "pr_threads: nothing matched '$selector'."
    return 0
  fi

  print "About to $mode ${#ids} thread(s) on #$number:"
  local l
  for l in "${labels[@]}"; do print "  $l"; done
  if [[ -z $PR_THREADS_ASSUME_YES ]]; then
    if [[ ! -t 0 ]]; then
      print -u2 "pr_threads: no terminal to confirm on; set PR_THREADS_ASSUME_YES=1"
      return 1
    fi
    if ! read -q "?Continue? [y/N] "; then
      print
      return 1
    fi
    print
  fi

  local id ok=0 failed=0
  for id in "${ids[@]}"; do
    if gh api graphql -F id="$id" -f query="
      mutation(\$id:ID!) { $mutation(input:{threadId:\$id}) { thread { isResolved } } }" \
      --jq ".data.$mutation.thread.isResolved" > /dev/null 2>&1; then
      (( ok++ ))
    else
      (( failed++ ))
      print -u2 "pr_threads: $mutation failed for $id"
    fi
  done
  print "pr_threads: ${mode}d $ok thread(s) on #$number${${failed:#0}:+, $failed failed}"
  (( failed == 0 ))
}
