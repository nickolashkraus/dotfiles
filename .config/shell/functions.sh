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

gcp_current_config() (
  gcloud config configurations list --filter="is_active:true" --format="value(name)" 2>/dev/null
)

# Automatically activate the Poetry environment when entering a directory that
# contains a pyproject.toml with a Poetry section. Deactivates and restores the
# default pyenv virtualenv when leaving.
#
# The Python version is resolved from the `python` dependency in pyproject.toml
# (e.g., "^3.12", "~=3.12", ">=3.12") and matched to the latest installed
# pyenv version for that minor release.
_poetry_auto_activate() {
  # Check for a Poetry project in the current directory.
  if [[ -f pyproject.toml ]] && grep -q '\[tool\.poetry\]' pyproject.toml 2>/dev/null; then
    # Extract the minor version (e.g., "3.12") from the Python dependency.
    local py_constraint
    py_constraint=$(grep -E '^\s*python\s*=' pyproject.toml | head -1 | grep -oE '[0-9]+\.[0-9]+')
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

    # Activate.
    pyenv deactivate 2>/dev/null
    pyenv shell "$py_version"
    eval "$(poetry env activate 2>/dev/null)"
    export _POETRY_AUTO_ACTIVATED=1
  elif [[ -n "$_POETRY_AUTO_ACTIVATED" ]]; then
    # Left a Poetry project. Restore defaults.
    unset _POETRY_AUTO_ACTIVATED
    deactivate 2>/dev/null
    pyenv shell --unset
    pyenv activate default 2>/dev/null
  fi
}

autoload -U add-zsh-hook
add-zsh-hook chpwd _poetry_auto_activate
