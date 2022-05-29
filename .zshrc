# vim: fdm=marker

# Zsh                                                                      {{{1
# -----------------------------------------------------------------------------

# If you come from bash you might have to change your $PATH.
export PATH=$HOME/bin:/usr/local/bin:$PATH

# Path to your oh-my-zsh installation.
export ZSH=$HOME/.oh-my-zsh

# Set name of the theme to load --- if set to "random", it will
# load a random theme each time oh-my-zsh is loaded, in which case,
# to know which specific one was loaded, run: echo $RANDOM_THEME
# See https://github.com/ohmyzsh/ohmyzsh/wiki/Themes
ZSH_THEME="nhk"

# Prevent aws plugin from modifying RPROMPT.
SHOW_AWS_PROMPT=false

# Set list of themes to pick from when loading at random
# Setting this variable when ZSH_THEME=random will cause zsh to load
# a theme from this variable instead of looking in $ZSH/themes/
# If set to an empty array, this variable will have no effect.
# ZSH_THEME_RANDOM_CANDIDATES=( "robbyrussell" "agnoster" )

# Uncomment the following line to use case-sensitive completion.
# CASE_SENSITIVE="true"

# Uncomment the following line to use hyphen-insensitive completion.
# Case-sensitive completion must be off. _ and - will be interchangeable.
# HYPHEN_INSENSITIVE="true"

# Uncomment one of the following lines to change the auto-update behavior
# zstyle ':omz:update' mode disabled  # disable automatic updates
# zstyle ':omz:update' mode auto      # update automatically without asking
# zstyle ':omz:update' mode reminder  # just remind me to update when it's time

# Uncomment the following line to change how often to auto-update (in days).
# zstyle ':omz:update' frequency 13

# Uncomment the following line if pasting URLs and other text is messed up.
# DISABLE_MAGIC_FUNCTIONS="true"

# Uncomment the following line to disable colors in ls.
# DISABLE_LS_COLORS="true"

# Uncomment the following line to disable auto-setting terminal title.
# DISABLE_AUTO_TITLE="true"

# Uncomment the following line to enable command auto-correction.
# ENABLE_CORRECTION="true"

# Uncomment the following line to display red dots whilst waiting for completion.
# You can also set it to another string to have that shown instead of the default red dots.
# e.g. COMPLETION_WAITING_DOTS="%F{yellow}waiting...%f"
# Caution: this setting can cause issues with multiline prompts in zsh < 5.7.1 (see #5765)
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
# Standard plugins can be found in $ZSH/plugins/
# Custom plugins may be added to $ZSH_CUSTOM/plugins/
# Example format: plugins=(rails git textmate ruby lighthouse)
# Add wisely, as too many plugins slow down shell startup.
plugins=(
  aws
  git
  kubectl
  poetry
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

# Set personal aliases, overriding those provided by oh-my-zsh libs,
# plugins, and themes. Aliases can be placed here, though oh-my-zsh
# users are encouraged to define aliases within the ZSH_CUSTOM folder.
# For a full list of active aliases, run `alias`.
#
# Example aliases
# alias zshconfig="mate ~/.zshrc"
# alias ohmyzsh="mate ~/.oh-my-zsh"

# Gruvbox                                                                  {{{1
# -----------------------------------------------------------------------------

# Script to override the system default 256-color palette with the precise
# Gruvbox color palette.
#
# See: https://github.com/morhetz/gruvbox/wiki/Terminal-specific
source "$HOME/.vim/bundle/gruvbox/gruvbox_256palette.sh"

# Homebrew                                                                 {{{1
# -----------------------------------------------------------------------------
eval "$(/opt/homebrew/bin/brew shellenv)"

# fzf                                                                      {{{1
# -----------------------------------------------------------------------------

# Configure fzf layout
[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh
export FZF_DEFAULT_OPTS='--preview-window down --height 40% --layout=reverse --border'

# Ignore files specified in .gitignore
export FZF_DEFAULT_COMMAND='ag --hidden -g ""'

# Apply 'FZF_DEFAULT_COMMAND' to CTRL + t
export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND"

# k9s                                                                      {{{1
# -----------------------------------------------------------------------------
export XDG_CONFIG_HOME=$HOME/.config

# nvm                                                                      {{{1
# -----------------------------------------------------------------------------
export NVM_DIR=$HOME/.nvm && mkdir -p $NVM_DIR
source $(brew --prefix nvm)/nvm.sh

# Languages                                                                {{{1
# -----------------------------------------------------------------------------

# Go                                                                       {{{2
# -----------------------------------------------------------------------------
export GOPATH=$HOME/go
export PATH=$PATH:$GOPATH/bin

# Java                                                                     {{{2
# -----------------------------------------------------------------------------
# openjdk@11 is keg-only, which means it was not symlinked into
# `brew --prefix`, because this is an alternate version of another formula.
export PATH="$(brew --prefix)/opt/openjdk@11/bin:$PATH"

# For compilers to find openjdk@11 you may need to set:
export CPPFLAGS="-I/opt/homebrew/opt/openjdk@11/include"

# Virtual Environments                                                     {{{1
# -----------------------------------------------------------------------------

# jenv                                                                     {{{2
# -----------------------------------------------------------------------------
export PATH="$HOME/.jenv/bin:$PATH"
eval "$(jenv init -)"

# pyenv                                                                    {{{2
# -----------------------------------------------------------------------------

# See https://github.com/pyenv/pyenv/issues/1737 for details.
#
# For compilers to find bzip2 you may need to set:
export LDFLAGS="-L/usr/local/opt/bzip2/lib"
export CPPFLAGS="-I/usr/local/opt/bzip2/include"

# For compilers to find zlib you may need to set:
export LDFLAGS="-L/usr/local/opt/zlib/lib"
export CPPFLAGS="-I/usr/local/opt/zlib/include"

export WORKON_HOME="${HOME}/.virtualenvs"
export VIRTUALENVWRAPPER_PYTHON="${HOME}/.pyenv/shims/python"
export VIRTUALENVWRAPPER_VIRTUALENV="${HOME}/.pyenv/shims/virtualenv"

export PYENV_ROOT="$HOME/.pyenv"
command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

python3.latest() {
  pyenv shell 3.10.3
  pyenv virtualenvwrapper
}

# rbenv                                                                    {{{2
# -----------------------------------------------------------------------------
eval "$(rbenv init -)"

# Aliases                                                                  {{{1
# -----------------------------------------------------------------------------
alias clean='deactivate; $HOME; clear; workon default; asp master.root'
alias credstash='credstash --log-file /dev/null'
alias docker-purge='docker-stop; docker-rm; docker-rmi; docker-rmv;'
alias docker-rm='docker rm $(docker ps -aq) >/dev/null 2>&1 || echo "No containers to remove."'
alias docker-rmi='docker rmi --force $(docker images -q) >/dev/null 2>&1 || echo "No images to remove."'
alias docker-rmv='docker volume rm --force $(docker volume ls -q) >/dev/null 2>&1 || echo "No volumes to remove."'
alias docker-stop='docker stop $(docker ps -aq) >/dev/null 2>&1 || echo "No running containers."'
alias gcp='git log -1 --pretty=%B | pbcopy'
alias go-infrable-io='$HOME/go/src/github.com/infrable-io'
alias go-nickolashkraus='$HOME/go/src/github.com/NickolasHKraus'
alias k='kubectl'
alias osx-show-hidden-off='defaults write com.apple.finder AppleShowAllFiles NO'
alias osx-show-hidden-on='defaults write com.apple.finder AppleShowAllFiles YES'
alias pip-upgrade='pip list --format=freeze | cut -d = -f 1 | xargs pip install --upgrade'
alias ssh-ip='ip=$(pbpaste); ssh nickolaskraus@${ip}'
alias tf='terraform'
alias tmux-config='vim ~/.tmux.conf'
alias tmux-kill='tmux kill-server'
alias tmux-new='tmux new -s $(basename $(pwd))'
alias vim-config='vim ~/.vimrc'
alias zsh-config='vim ~/.zshrc'

# Bash Functions                                                           {{{1
# -----------------------------------------------------------------------------
python_clean() {
  # Remove build artifacts
  find . -name '*.egg' -exec rm -fr {} +
  find . -name '*.egg-info' -exec rm -fr {} +
  rm -fr .eggs/
  rm -fr build/
  rm -fr dist/
  # Remove Python artifacts
  find . -name '*.pyc' -exec rm -f {} +
  find . -name '*.pyo' -exec rm -f {} +
  find . -name '*~' -exec rm -f {} +
  find . -name '__pycache__' -exec rm -fr {} +
  # Remove test and coverage artifacts
  find . -name '*,cover' -exec rm -f {} +
  find . -name '.coverage' -exec rm -f {} +
  find . -name '.pytest_cache' -exec rm -fr {} +
  find . -name 'cover' -exec rm -fr {} +
  find . -name 'coverage.xml' -exec rm -f {} +
  find . -name 'htmlcov' -exec rm -fr {} +
}

remove_whitespace() {
  find . -type f \
  -name "*" \
  -not -name "*.png" \
  -not -path "./.git/*" \
  -exec gsed -i 's/[[:space:]]\+$//' {} \;
}

add_newline_eof() {
  find . -type f \
  -name "*" \
  -not -name "*.png" \
  -not -path "./.git/*" \
  -exec gsed -i '$a\' {} \;
}

# Default                                                                  {{{1
# -----------------------------------------------------------------------------

# Set default AWS profile
export AWS_PROFILE=master.root

# Default to latest version of Python 3
python3.latest

# Default to 'default' virtualenv
workon default
