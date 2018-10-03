# ~~~~~~~~~~~~~~~~~~~~~~~~~~~ Start Zsh configuration ~~~~~~~~~~~~~~~~~~~~~~~~~

# If you come from bash you might have to change your $PATH.
export PATH=$HOME/bin:/usr/local/bin:$PATH

# Path to your oh-my-zsh installation.
export ZSH=$HOME/.oh-my-zsh

# Set name of the theme to load --- if set to "random", it will
# load a random theme each time oh-my-zsh is loaded, in which case,
# to know which specific one was loaded, run: echo $RANDOM_THEME
# See https://github.com/robbyrussell/oh-my-zsh/wiki/Themes
ZSH_THEME="amuse"

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
COMPLETION_WAITING_DOTS="true"

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
  git
  vi-mode
  virtualenv
)

source $ZSH/oh-my-zsh.sh

# User configuration

# export MANPATH="/usr/local/man:$MANPATH"

# You may need to manually set your language environment
# export LANG=en_US.UTF-8

# Preferred editor for local and remote sessions
# if [[ -n $SSH_CONNECTION ]]; then
#   export EDITOR='vim'
# else
#   export EDITOR='mvim'
# fi

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

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~ Start AWS configuration ~~~~~~~~~~~~~~~~~~~~~~~~~

# enable AWS CLI command completion
source /Users/$USER/.virtualenvs/dev/bin/aws_zsh_completer.sh


# ~~~~~~~~~~~~~~~~~~~~~~~~~~ Start Google configuration ~~~~~~~~~~~~~~~~~~~~~~~

# the next line updates PATH for the Google Cloud SDK
if [ -f "/Users/$USER/.local/google-cloud-sdk/path.zsh.inc" ]; then source "/Users/$USER/.local/google-cloud-sdk/path.zsh.inc"; fi

# the next line enables shell command completion for gcloud
if [ -f "/Users/$USER/.local/google-cloud-sdk/completion.zsh.inc" ]; then source "/Users/$USER/.local/google-cloud-sdk/completion.zsh.inc"; fi

# set Google Cloud SDK environment variable
export GOOGLE_CLOUD_SDK=/Users/nickolaskraus/.local/google-cloud-sdk

# set App Engine SDK environment variable
export APP_ENGINE_SDK=/Users/nickolaskraus/.local/google-cloud-sdk/platform/google_appengine


# ~~~~~~~~~~~~~~~~~~~~~~~~ Start virtualenv configuration ~~~~~~~~~~~~~~~~~~~~~

# configure virtualenv and virtualenvwrapper
export WORKON_HOME=$HOME/.virtualenvs
export VIRTUALENVWRAPPER_PYTHON=/usr/local/bin/python2
export VIRTUALENVWRAPPER_VIRTUALENV=/usr/local/bin/virtualenv
source /usr/local/bin/virtualenvwrapper.sh

# set up pyenv
eval "$(pyenv init -)"

python2.7.8() {
  pyenv shell 2.7.8
  pyenv virtualenvwrapper
}

python2.latest() {
  pyenv shell 2.7.15
  pyenv virtualenvwrapper
}

python3.latest() {
  pyenv shell 3.7.0
  pyenv virtualenvwrapper
}


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Start fzf configuration ~~~~~~~~~~~~~~~~~~~~~~~~

# configure fzf
[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh
export FZF_DEFAULT_OPTS='--height 40% --layout=reverse --border'

# ignore files specified in .gitignore
export FZF_DEFAULT_COMMAND='ag -g ""'

# apply 'FZF_DEFAULT_COMMAND' to ^Ctrl + t
export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND"


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~ Start user configuration ~~~~~~~~~~~~~~~~~~~~~~~~

# default to Python 2.7.14
python2.latest

# default to 'dev' virtualenv
workon dev

# set Dartium expiration to January 2020
export DARTIUM_EXPIRATION_TIME=1577836800;


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~ Start alias configuration ~~~~~~~~~~~~~~~~~~~~~~~

# general
alias clean='deactivate; cd ~; clear; workon dev;'

# osx
alias show-hidden-on='defaults write com.apple.finder AppleShowAllFiles YES'
alias show-hidden-off='defaults write com.apple.finder AppleShowAllFiles NO'

# docker
alias docker-purge='docker stop $(docker ps -aq) && docker rm $(docker ps -aq) && docker rmi $(docker images -q)'

# dart
alias ddev='pub run dart_dev'
alias pub-purge='rm -rf .pub .packages && find . -name packages | xargs rm -rf'

