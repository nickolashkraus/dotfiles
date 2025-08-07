#!/usr/bin/env bash
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
