#!/usr/bin/env bash
###############################################################################
# Shell Aliases
#
# DESCRIPTION
#   My personal shell aliases.
#
#   A shell alias is a shortcut or custom command name that you can create to
#   represent a longer command or series of commands in your shell (like bash,
#   zsh, or other command-line interfaces).
#
#   This file is sourced by .zshrc.
#
# INSTALLATION
#   Symlink file to $XDG_CONFIG_HOME/shell/aliases.sh:
#
#     ln -s .config/shell/aliases.sh $XDG_CONFIG_HOME/shell/aliases.sh
###############################################################################

alias clean='pyenv deactivate &>/dev/null; cd $HOME; clear; asp master.root'
alias docker-purge='docker-stop; docker-rm; docker-rmi; docker-rmv'
alias docker-rm='docker rm $(docker ps -aq) >/dev/null 2>&1 || echo "No containers to remove."'
alias docker-rmi='docker rmi --force $(docker images -q) >/dev/null 2>&1 || echo "No images to remove."'
alias docker-rmv='docker volume rm --force $(docker volume ls -q) >/dev/null 2>&1 || echo "No volumes to remove."'
alias docker-stop='docker stop $(docker ps -aq) >/dev/null 2>&1 || echo "No running containers."'
alias gcb='git branch | fzf | cut -c 3- | xargs git checkout'
alias gcp='git log -1 --pretty=%B | pbcopy'
alias gp='git push origin $(git branch --show-current)'
alias k='kubectl'
alias tf='terraform'
alias tmux-config='vim $XDG_CONFIG_HOME/tmux/tmux.conf'
alias tmux-kill='tmux kill-server'
alias tmux-new='tmux new-session -t $(basename $(pwd))'
alias vim-config='vim $HOME/.vimrc'
alias vim-update='vim -u NONE +PlugClean +qall && vim -u NONE +PlugInstall +qall && vim -u NONE +PlugUpdate +qall'
alias zsh-config='vim $HOME/.zshrc'
