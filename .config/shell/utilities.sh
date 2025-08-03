#!/usr/bin/env bash
###############################################################################
# Shell Utilities Configuration
#
# DESCRIPTION
#   My personal shell utilities configuration.
#
#   A shell utility is a standalone command-line program that extends your
#   shell's capabilities beyond the built-in commands. Unlike aliases and
#   functions (which are shell features), utilities are separate executable
#   programs that you install and run from your shell.
#
#   This file is sourced by .zshrc.
#
# INSTALLATION
#   Symlink file to $XDG_CONFIG_HOME/shell/utilities.sh:
#
#     ln -s .config/shell/utilities.sh $XDG_CONFIG_HOME/shell/utilities.sh
###############################################################################

###############################################################################
# Homebrew
#
# Homebrew is a package manager for macOS and Linux that makes it easy to
# install, manage, and update software from the command line.
#
# See: https://brew.sh
###############################################################################

# Set up Homebrew.
eval "$(/opt/homebrew/bin/brew shellenv)"

###############################################################################
# Gruvbox
#
# Gruvbox is a popular retro-inspired colorscheme for Vim and other text
# editors. It's designed with warm, earthy tones that are easy on the eyes for
# long coding sessions.
#
# See: https://github.com/morhetz/gruvbox
###############################################################################

# Run script to override the system default 256-color palette with the precise
# Gruvbox color palette.
#
# See: https://github.com/morhetz/gruvbox/wiki/Terminal-specific
source "$HOME/.vim/bundle/gruvbox/gruvbox_256palette.sh"

###############################################################################
# Go
###############################################################################

# Add the Go binaries directory ($GOPATH/bin) to $PATH.
#
# When you build Go programs with `go install`, the compiled executables go
# into $GOPATH/bin. By default, Go uses $HOME/go for $GOPATH.
export PATH=$PATH:${GOPATH:-$HOME/go}/bin

###############################################################################
# Java
###############################################################################

# openjdk@24 is marked as keg-only, so it isn't symlinked to `brew --prefix`.
# This is because it's an alternative version of the main OpenJDK formula.
export PATH="$(brew --prefix)/opt/openjdk@24/bin:$PATH"

# For compilers to find openjdk@24, CPPFLAGS is set.
export CPPFLAGS="-I/opt/homebrew/opt/openjdk@24/include"
