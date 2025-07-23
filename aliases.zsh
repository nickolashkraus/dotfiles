###############################################################################
# Oh My Zsh Aliases
#
# DESCRIPTION
#   My personal Zsh aliases.
#
# INSTALLATION
#   Symlink file to Oh My Zsh custom directory:
#
#     ln -s aliases.zsh $ZSH_CUSTOM/aliases.zsh
###############################################################################

alias clean='pyenv deactivate; cd $HOME; clear; pyenv activate default; asp master.root'
alias docker-purge='docker-stop; docker-rm; docker-rmi; docker-rmv'
alias docker-rm='docker rm $(docker ps -aq) >/dev/null 2>&1 || echo "No containers to remove."'
alias docker-rmi='docker rmi --force $(docker images -q) >/dev/null 2>&1 || echo "No images to remove."'
alias docker-rmv='docker volume rm --force $(docker volume ls -q) >/dev/null 2>&1 || echo "No volumes to remove."'
alias docker-stop='docker stop $(docker ps -aq) >/dev/null 2>&1 || echo "No running containers."'
alias gcp='git log -1 --pretty=%B | pbcopy'
alias gp='git push origin $(git branch --show-current)'
alias k='kubectl'
alias tf='terraform'
alias tmux-config='vim $XDG_CONFIG_HOME/tmux/tmux.conf'
alias tmux-kill='tmux kill-server'
alias vim-config='vim $HOME/.vimrc'
alias vim-update='vim -u NONE +PlugClean +qall && vim -u NONE +PlugInstall +qall && vim -u NONE +PlugUpdate +qall'
alias zsh-config='vim $HOME/.zshrc'
