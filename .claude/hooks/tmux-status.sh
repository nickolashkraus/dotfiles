#!/usr/bin/env bash
# Claude Code status marker for tmux. Stores per-pane state and rolls up to
# a window-level @claude_status marker (highest-priority across panes).
#
# Usage:
#   tmux-status.sh working
#   tmux-status.sh input       # reads JSON payload from stdin; filters
#   tmux-status.sh idle
#   tmux-status.sh clear       # remove this pane's state (SessionEnd)
#   tmux-status.sh rollup ID   # recompute window marker for window-id ID
#                              # (used by tmux pane-exited hook)
#
# Pane state lives in pane option @claude_pane_status; tmux auto-clears it
# when the pane is destroyed. Window state lives in @claude_status; the
# Powerline format prepends it to the window status.

log=/tmp/claude-tmux-debug.log
state="${1:-idle}"
echo "[$(date +%T)] state=$state TMUX_PANE=${TMUX_PANE:-unset}" >>"$log"

priorities=(input working idle)

rollup() {
  local win="$1"
  [ -z "$win" ] && return 0
  local rolled=""
  local prio p s
  for prio in "${priorities[@]}"; do
    while IFS= read -r p; do
      s=$(tmux show-options -pqv -t "$p" @claude_pane_status 2>/dev/null)
      if [ "$s" = "$prio" ]; then
        rolled="$prio"
        break 2
      fi
    done < <(tmux list-panes -t "$win" -F '#{pane_id}' 2>/dev/null)
  done

  local symbol=""
  case "$rolled" in
    working) symbol='⋯' ;;
    input) symbol='!' ;;
    idle) symbol='✓' ;;
  esac

  if [ -n "$symbol" ]; then
    tmux set-option -w -t "$win" @claude_status "$symbol" 2>>"$log"
  else
    tmux set-option -wu -t "$win" @claude_status 2>/dev/null
  fi
  echo "  -> rollup win=$win rolled=${rolled:-none}" >>"$log"
}

if [ "$state" = "rollup" ]; then
  rollup "$2"
  exit 0
fi

[ -z "$TMUX" ] && {
  echo "  -> no TMUX, exit" >>"$log"
  exit 0
}

pane="${TMUX_PANE:-$(tmux display-message -p '#{pane_id}' 2>/dev/null)}"
win=$(tmux display-message -p -t "$pane" '#{window_id}' 2>>"$log")
[ -z "$pane" ] || [ -z "$win" ] && {
  echo "  -> no pane/win, exit" >>"$log"
  exit 0
}

case "$state" in
  clear)
    tmux set-option -pu -t "$pane" @claude_pane_status 2>/dev/null
    ;;
  input)
    # Notification hook fires for both permission requests and idle-timeout
    # "waiting for input" messages. Only treat permission-style messages as
    # needing attention; the idle case is already covered by Stop -> idle.
    payload=$(cat 2>/dev/null || true)
    if [ -n "$payload" ] && ! echo "$payload" | grep -qiE 'permission|approval|needs? (your )?(permission|approval|input)'; then
      echo "  -> input filtered (no permission keyword)" >>"$log"
      rollup "$win"
      exit 0
    fi
    tmux set-option -p -t "$pane" @claude_pane_status input 2>>"$log"
    ;;
  working | idle)
    tmux set-option -p -t "$pane" @claude_pane_status "$state" 2>>"$log"
    ;;
  *)
    echo "  -> unknown state, exit" >>"$log"
    exit 0
    ;;
esac

rollup "$win"
echo "  -> applied pane=$pane state=$state" >>"$log"
