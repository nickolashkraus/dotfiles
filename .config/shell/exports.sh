#!/usr/bin/env bash
###############################################################################
# Shell Environment Variables
#
# DESCRIPTION
#   My personal shell environment variables.
#
#   A shell environment variable is a named value that stores information the
#   shell and programs can access. These variables affect how the shell and
#   other programs behave, and they're available to both the current shell
#   session and programs launched from it.
#
#   This file is sourced by .zshrc.
#
# INSTALLATION
#   Symlink file to $XDG_CONFIG_HOME/shell/exports.sh:
#
#     ln -s .config/shell/exports.sh $XDG_CONFIG_HOME/shell/exports.sh
###############################################################################

# Set path to configuration files.
export XDG_CONFIG_HOME=${XDG_CONFIG_HOME:-$HOME/.config}

# Set language.
export LANG=en_US.UTF-8

# Set preferred editor for local and remote sessions.
export EDITOR='vim'

# Set path to kubeconfig file (prepend Workiva-specific kubeconfig file).
export KUBECONFIG=$HOME/.kube/workiva.yaml:$HOME/.kube/config

# Set default AWS profile.
export AWS_PROFILE=master.root
