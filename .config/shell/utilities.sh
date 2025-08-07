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
source "$HOME/.vim/plugged/gruvbox/gruvbox_256palette.sh"

###############################################################################
# fzf
#
# fzf is a general-purpose command-line fuzzy finder. It helps you quickly
# search and select items from a list using a fast, interactive fuzzy search
# interface. It's written in Go and works in any Unix-like terminal
# environment.
#
# See:
#   - https://github.com/junegunn/fzf
#   - https://junegunn.github.io/fzf
###############################################################################

# Set up fzf shell integration.
#
# Key Bindings:
#   Ctrl - r: Paste the selected command from history onto the command line.
#   Ctrl - t: Paste the selected files and directories onto the command line.
#   Alt - c: cd into the selected directory.
source <(fzf --zsh)

# Default fzf command (uses ripgrep).
#   --hidden: Search hidden files and directories.
#   --follow: Follow symbolic links while traversing directories.
#   --glob: Include or exclude files and directories that match the given glob.
export FZF_DEFAULT_COMMAND='rg --files --hidden --follow --glob "!.git/*" --glob "!node_modules/*"'

# Use 'FZF_DEFAULT_COMMAND' for Ctrl - t.
export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND"

# Default fzf options.
export FZF_DEFAULT_OPTS='--height 40% --preview-window right:50%'

# Additional options for Ctrl - r.
#
# Press Ctrl - y to copy the selected command to the system clipboard.
export FZF_CTRL_R_OPTS="
--bind 'ctrl-y:execute-silent(echo -n {2..} | pbcopy)+abort'
--color header:italic
--header 'Press Ctrl - y to copy the selected command to the system clipboard.'
"

# Additional options for Ctrl - t.
#
# Press Ctrl - / to toggle file preview.
export FZF_CTRL_T_OPTS="
--preview 'bat -n --color=always {}'
--bind 'ctrl-/:change-preview-window(hidden|)'
--color header:italic
--header 'Press Ctrl - / to toggle file preview.'
"

# Additional options for Alt - c.
export FZF_ALT_C_OPTS="
--preview 'tree -C {}'
"

# Configure fzf theme.
#
#   fg:      #ebdbb2 - fg1
#   fg+:     #d5c4a1 - fg2
#   bg:      #282828 - bg0
#   bg+:     #3c3836 - bg1
#   hl:      #fabd2f - yellow (bright)
#   hl+:     #d79921 - yellow (neutral)
#   info:    #665c54 - bg3
#   marker:  #83a598 - blue (bright)
#   prompt:  #665c54 - bg3
#   spinner: #665c54 - bg3
#   pointer: #83a598 - blue (bright)
#   header:  #665c54 - bg3
#   border:  #3c3836 - bg1
#   label:   #665c54 - bg3
#   query:   #ebdbb2 - fg1
#
# See:
#   - https://github.com/junegunn/fzf/wiki/Color-schemes
#   - https://vitormv.github.io/fzf-themes
export FZF_DEFAULT_OPTS=$FZF_DEFAULT_OPTS'
--color=fg:#ebdbb2,fg+:#d5c4a1,bg:#282828,bg+:#3c3836
--color=hl:#fabd2f,hl+:#d79921,info:#665c54,marker:#83a598
--color=prompt:#665c54,spinner:#665c54,pointer:#83a598,header:#665c54
--color=border:#3c3836,label:#665c54,query:#ebdbb2
--border="rounded" --border-label="" --preview-window="border-rounded" --prompt="> "
--marker=">" --pointer="▌" --separator="─" --scrollbar="│"
--layout="reverse"'

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

# openjdk@24 is marked as keg-only, so it isn't symlinked to `brew --prefix`
# ($HOMEBREW_PREFIX). This is because it's an alternative version of the main
# OpenJDK formula.
export PATH="$HOMEBREW_PREFIX/opt/openjdk@24/bin:$PATH"

# For compilers to find openjdk@24, CPPFLAGS is set.
export CPPFLAGS="-I/opt/homebrew/opt/openjdk@24/include"

###############################################################################
# Docker
###############################################################################

# Added by Docker Desktop.
source "$HOME/.docker/init-zsh.sh" || true

###############################################################################
# nvm
#
# nvm (Node Version Manager) is a tool that lets you install, manage, and
# switch between multiple versions of Node.js on the same machine.
#
# See: https://github.com/nvm-sh/nvm
###############################################################################

# WARNING: Managing nvm via Homebrew is not supported.
export NVM_DIR="$HOME/.nvm"
[ -s "$HOMEBREW_PREFIX/opt/nvm/nvm.sh" ] &&
  \. "$HOMEBREW_PREFIX/opt/nvm/nvm.sh"
[ -s "$HOMEBREW_PREFIX/opt/nvm/etc/bash_completion.d/nvm" ] &&
  \. "$HOMEBREW_PREFIX/opt/nvm/etc/bash_completion.d/nvm"

###############################################################################
# pyenv
#
# pyenv is a Python version manager that lets you install, manage, and switch
# between multiple versions of Python on the same machine.
#
# See: https://github.com/pyenv/pyenv
###############################################################################

export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"
