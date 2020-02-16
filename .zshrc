# vim: fdm=marker

# Zsh                                                                      {{{1
# -----------------------------------------------------------------------------

# If you come from bash you might have to change your $PATH.
export PATH=$HOME/bin:/usr/local/bin:$GOPATH/bin:$PATH

# Path to your oh-my-zsh installation.
export ZSH=$HOME/.oh-my-zsh

# Set name of the theme to load --- if set to "random", it will
# load a random theme each time oh-my-zsh is loaded, in which case,
# to know which specific one was loaded, run: echo $RANDOM_THEME
# See https://github.com/robbyrussell/oh-my-zsh/wiki/Themes
ZSH_THEME="nhk"

# prevent aws plugin from modifying RPROMPT
SHOW_AWS_PROMPT=false

# Set list of themes to pick from when loading at random
# Setting this variable when ZSH_THEME=random will cause zsh to load
# a theme from this variable instead of looking in ~/.oh-my-zsh/themes/
# If set to an empty array, this variable will have no effect.
# ZSH_THEME_RANDOM_CANDIDATES=( "robbyrussell" "agnoster" )

# Uncomment the following line to use case-sensitive completion.
# CASE_SENSITIVE="true"

# Uncomment the following line to use hyphen-insensitive completion.
# Case-sensitive completion must be off. _ and - will be interchangeable.
# HYPHEN_INSENSITIVE="true"

# Uncomment the following line to disable bi-weekly auto-update checks.
# DISABLE_AUTO_UPDATE="true"

# Uncomment the following line to change how often to auto-update (in days).
# export UPDATE_ZSH_DAYS=13

# Uncomment the following line to disable colors in ls.
# DISABLE_LS_COLORS="true"

# Uncomment the following line to disable auto-setting terminal title.
# DISABLE_AUTO_TITLE="true"

# Uncomment the following line to enable command auto-correction.
# ENABLE_CORRECTION="true"

# Uncomment the following line to display red dots whilst waiting for completion.
# COMPLETION_WAITING_DOTS="true"

# Uncomment the following line if you want to disable marking untracked files
# under VCS as dirty. This makes repository status check for large repositories
# much, much faster.
# DISABLE_UNTRACKED_FILES_DIRTY="true"

# Uncomment the following line if you want to change the command execution time
# stamp shown in the history command output.
# You can set one of the optional three formats:
# "mm/dd/yyyy"|"dd.mm.yyyy"|"yyyy-mm-dd"
# or set a custom format using the strftime function format specifications,
# see 'man strftime' for details.
# HIST_STAMPS="mm/dd/yyyy"

# Would you like to use another custom folder than $ZSH/custom?
# ZSH_CUSTOM=/path/to/new-custom-folder

# Which plugins would you like to load?
# Standard plugins can be found in ~/.oh-my-zsh/plugins/*
# Custom plugins may be added to ~/.oh-my-zsh/custom/plugins/
# Example format: plugins=(rails git textmate ruby lighthouse)
# Add wisely, as too many plugins slow down shell startup.
plugins=(
  aws
  git
  kubectl
  vi-mode
  virtualenv
)

source $ZSH/oh-my-zsh.sh

# User configuration

# export MANPATH="/usr/local/man:$MANPATH"

# You may need to manually set your language environment
export LANG=en_US.UTF-8

# Preferred editor for local and remote sessions
if [[ -n $SSH_CONNECTION ]]; then
  export EDITOR='vim'
else
  export EDITOR='vim'
fi

# Compilation flags
# export ARCHFLAGS="-arch x86_64"

# ssh
# export SSH_KEY_PATH="~/.ssh/rsa_id"

# Set personal aliases, overriding those provided by oh-my-zsh libs,
# plugins, and themes. Aliases can be placed here, though oh-my-zsh
# users are encouraged to define aliases within the ZSH_CUSTOM folder.
# For a full list of active aliases, run `alias`.
#
# Example aliases
# alias zshconfig="mate ~/.zshrc"
# alias ohmyzsh="mate ~/.oh-my-zsh"

# Utilities                                                                {{{1
# -----------------------------------------------------------------------------

# AWS                                                                      {{{2
# -----------------------------------------------------------------------------

# enable AWS CLI command completion
source /Users/$USER/.virtualenvs/dev3/bin/aws_zsh_completer.sh

# set profile
export AWS_PROFILE=master


# Google                                                                   {{{2
# -----------------------------------------------------------------------------

# the next line updates PATH for the Google Cloud SDK
if [ -f "/Users/$USER/.local/google-cloud-sdk/path.zsh.inc" ]; then
  source "/Users/$USER/.local/google-cloud-sdk/path.zsh.inc";
fi

# the next line enables shell command completion for gcloud
if [ -f "/Users/$USER/.local/google-cloud-sdk/completion.zsh.inc" ]; then
  source "/Users/$USER/.local/google-cloud-sdk/completion.zsh.inc";
fi

# set Google Cloud SDK environment variable
export GOOGLE_CLOUD_SDK=/Users/$USER/.local/google-cloud-sdk

# set App Engine SDK environment variable
export APP_ENGINE_SDK=/Users/$USER/.local/google-cloud-sdk/platform/google_appengine


# Kubernetes                                                               {{{2
# -----------------------------------------------------------------------------

export KUBECONFIG=$HOME/.kube/config:$HOME/Workspace/EKS/kubeconfigs.yaml


# SDKMAN!                                                                  {{{2
# -----------------------------------------------------------------------------

# configure SDKMAN!
export SDKMAN_DIR="/Users/nkraus/.sdkman"
[[ -s "/Users/nkraus/.sdkman/bin/sdkman-init.sh" ]] && \
  source "/Users/nkraus/.sdkman/bin/sdkman-init.sh"


# Serverless                                                               {{{2
# -----------------------------------------------------------------------------

# enable `serverless` command completion
[[ -f "/usr/local/lib/node_modules/serverless/node_modules/tabtab/.completions/serverless.zsh" ]] && \
  . "/usr/local/lib/node_modules/serverless/node_modules/tabtab/.completions/serverless.zsh"


# Travis CI                                                                {{{2
# -----------------------------------------------------------------------------

# added by travis gem
[ -f /Users/nkraus/.travis/travis.sh ] && \
  source /Users/nkraus/.travis/travis.sh


# fzf                                                                      {{{2
# -----------------------------------------------------------------------------

# configure fzf
[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh
export FZF_DEFAULT_OPTS='--height 40% --layout=reverse --border'

# ignore files specified in .gitignore
export FZF_DEFAULT_COMMAND='ag --hidden -g ""'

# apply 'FZF_DEFAULT_COMMAND' to CTRL + t
export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND"


# nvm                                                                      {{{2
# -----------------------------------------------------------------------------

# configure nvm
export NVM_DIR=$HOME/.nvm && mkdir -p $NVM_DIR
source $(brew --prefix nvm)/nvm.sh


# Languages                                                                {{{1
# -----------------------------------------------------------------------------

# Go                                                                       {{{2
# -----------------------------------------------------------------------------

export GOPATH=$HOME/go


# Virtual Environments                                                     {{{1
# -----------------------------------------------------------------------------

# jenv                                                                     {{{2
# -----------------------------------------------------------------------------

# configure jenv
export PATH="$HOME/.jenv/bin:$PATH"

# set up jenv
eval "$(jenv init -)"


# pyenv                                                                    {{{2
# -----------------------------------------------------------------------------

# configure virtualenv and virtualenvwrapper
export WORKON_HOME=$HOME/.virtualenvs
export VIRTUALENVWRAPPER_PYTHON=$HOME/.pyenv/shims/python
export VIRTUALENVWRAPPER_VIRTUALENV=$HOME/.pyenv/shims/virtualenv

# set up pyenv
eval "$(pyenv init -)"

python2.latest() {
  pyenv shell 2.7.17
  pyenv virtualenvwrapper
}

python3.latest() {
  pyenv shell 3.8.1
  pyenv virtualenvwrapper
}


# rbenv                                                                    {{{2
# -----------------------------------------------------------------------------
eval "$(rbenv init -)"


# Aliases                                                                  {{{1
# -----------------------------------------------------------------------------

# AWS                                                                      {{{2
# -----------------------------------------------------------------------------

alias aws-default='export AWS_PROFILE=default'
alias aws-ops='export AWS_PROFILE=ops'
alias aws-prod='export AWS_PROFILE=prod'
alias aws-dev='export AWS_PROFILE=dev'
alias aws-dwolla-prod='export AWS_PROFILE=dwolla-prod'
alias aws-dwolla-sand='export AWS_PROFILE=dwolla-sand'


# Dart                                                                     {{{2
# -----------------------------------------------------------------------------

alias ddev='pub run dart_dev'
alias pub-purge='rm -rf .pub .packages && find . -name packages | xargs rm -rf'


# Docker                                                                   {{{2
# -----------------------------------------------------------------------------

alias docker-stop='docker stop $(docker ps -aq) >/dev/null 2>&1 || echo "No running containers."'
alias docker-rm='docker rm $(docker ps -aq) >/dev/null 2>&1 || echo "No containers to remove."'
alias docker-rmi='docker rmi --force $(docker images -q) >/dev/null 2>&1 || echo "No images to remove."'
alias docker-purge='docker-stop; docker-rm; docker-rmi;'


# General                                                                  {{{2
# -----------------------------------------------------------------------------

alias clean='deactivate; $HOME; clear; workon dev3;'


# Git                                                                      {{{2
# -----------------------------------------------------------------------------

alias gcp='git log -1 --pretty=%B | pbcopy'


# Go                                                                       {{{2
# -----------------------------------------------------------------------------

alias go-infrable='$HOME/go/src/github.com/infrable-io'
alias go-personal='$HOME/go/src/github.com/NickolasHKraus'


# OS X                                                                     {{{2
# -----------------------------------------------------------------------------

alias show-hidden-on='defaults write com.apple.finder AppleShowAllFiles YES'
alias show-hidden-off='defaults write com.apple.finder AppleShowAllFiles NO'


# Python                                                                   {{{2
# -----------------------------------------------------------------------------

alias pip-upgrade='pip list --format=freeze | cut -d = -f 1 | xargs pip install --upgrade'


# Terraform                                                                {{{2
# -----------------------------------------------------------------------------

alias tf='terraform'


# tmux                                                                     {{{2
# -----------------------------------------------------------------------------

alias tmux-kill='tmux kill-server'
alias tmux-new='tmux new -s $(basename $(pwd))'


# Vim                                                                      {{{2
# -----------------------------------------------------------------------------

alias vim-config='vim ~/.vimrc'
alias vim-work='$HOME/.vim/bundle'


# Zsh                                                                      {{{2
# -----------------------------------------------------------------------------

alias zsh-config='vim ~/.zshrc'


# Default                                                                  {{{1
# -----------------------------------------------------------------------------

# default to Python 3
python3.latest

# default to 'dev3' virtualenv
workon dev3
