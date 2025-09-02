#!/usr/bin/env bash
###############################################################################
# Shell Plugins
#
# DESCRIPTION
#   My personal shell plugins.
#
#   This file is sourced by .zshrc.
#
# INSTALLATION
#   Symlink file to $XDG_CONFIG_HOME/shell/plugins.sh:
#
#     ln -s .config/shell/plugins.sh $XDG_CONFIG_HOME/shell/plugins.sh
###############################################################################

# Enable plugins.
# See: https://github.com/ohmyzsh/ohmyzsh/wiki/Plugins
export plugins=(
  aws
  git
  vi-mode
  virtualenv
)

# Set vi-mode indicator color.
export MODE_INDICATOR="%F{#cc241d}<<<%f"

# Prevent aws plugin from modifying RPROMPT.
export SHOW_AWS_PROMPT=false
