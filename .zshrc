###############################################################################
# Zsh + Oh My Zsh Configuration
#
# DESCRIPTION
#   Configuration file for Zsh + Oh My Zsh.
#
#   Zsh (Z Shell) is a powerful, feature-rich Unix shell that serves as an
#   alternative to Bash. It is widely used as a command-line interpreter and
#   interactive shell by developers and power users due to its advanced
#   functionality, customization options, and plugin support.
#
#   See: https://www.zsh.org
#
#   Oh My Zsh is a popular open-source framework for managing Zsh configuration,
#   designed to make using the Z shell more powerful, user-friendly, and
#   visually appealing—especially for developers.
#
#   See: https://ohmyz.sh
#
# INSTALLATION
#   Symlink file to $HOME/.zshrc:
#
#     ln -s .zshrc $HOME/.zshrc
###############################################################################

###############################################################################
# Basic Configuration
###############################################################################

# Set $PATH.
export PATH=$HOME/bin:$HOME/.local/bin:/usr/local/bin:$PATH

# Set path to Oh My Zsh installation.
export ZSH="$HOME/.oh-my-zsh"

# Set Oh My Zsh theme.
# See: https://github.com/ohmyzsh/ohmyzsh/wiki/Themes
ZSH_THEME="nhk"

# Set auto update behavior.
zstyle ':omz:update' mode auto     # Auto update without asking.
zstyle ':omz:update' frequency 14  # Auto update every 14 days.

# Enable plugins.
# See: https://github.com/ohmyzsh/ohmyzsh/wiki/Plugins
plugins=(
  aws
  git
  vi-mode
  virtualenv
)

# Prevent aws plugin from modifying RPROMPT.
SHOW_AWS_PROMPT=false

source $ZSH/oh-my-zsh.sh

###############################################################################
# User Configuration
###############################################################################

# Set path to configuration files.
export XDG_CONFIG_HOME=${XDG_CONFIG_HOME:-$HOME/.config}

# Set language.
export LANG=en_US.UTF-8

# Set preferred editor for local and remote sessions.
export EDITOR='vim'

# Set up Homebrew.
eval "$(/opt/homebrew/bin/brew shellenv)"

# Run script to override the system default 256-color palette with the precise
# Gruvbox color palette.
# See: https://github.com/morhetz/gruvbox/wiki/Terminal-specific
source "$HOME/.vim/bundle/gruvbox/gruvbox_256palette.sh"

# Set path to kubeconfig file (prepend Workiva-specific kubeconfig file).
export KUBECONFIG=$HOME/.kube/workiva.yaml:$HOME/.kube/config

# Configure fzf.
# See: https://github.com/junegunn/fzf
[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh

# Configure fzf layout.
export FZF_DEFAULT_OPTS='--preview-window down --height 40% --layout=reverse --border'

# Configure fzf colorscheme.
# See: https://github.com/junegunn/fzf/wiki/Color-schemes
export FZF_DEFAULT_OPTS="$FZF_DEFAULT_OPTS
--color=fg:#ebdbb2
--color=bg:#282828
--color=preview-fg:#ebdbb2
--color=preview-bg:#282828
--color=hl:#fabd2f
--color=fg+:#ebdbb2
--color=bg+:#3c3836
--color=gutter:#3c3836
--color=hl+:#fabd2f
--color=info:#83a598
--color=border:#3c3836
--color=prompt:#bdae93
--color=pointer:#83a598
--color=marker:#fe8019
--color=spinner:#83a598
--color=header:#3c3836"

# Ignore files specified in .gitignore.
export FZF_DEFAULT_COMMAND='ag --hidden -g ""'

# Bind 'FZF_DEFAULT_COMMAND' to CTRL + t.
export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND"

# Set up nvm.
export NVM_DIR=$HOME/.nvm && mkdir -p $NVM_DIR
source $(brew --prefix nvm)/nvm.sh

# Set up Go.
export GOPATH=$HOME/go
export PATH=$PATH:$GOPATH/bin

# Set up Java.
# openjdk@19 is marked as keg-only, so it isn't symlinked to `brew --prefix`.
# This is because it's an alternative version of the main OpenJDK formula.
export PATH="$(brew --prefix)/opt/openjdk@19/bin:$PATH"

# For compilers to find openjdk@19, CPPFLAGS is set.
export CPPFLAGS="-I/opt/homebrew/opt/openjdk@19/include"

# Set up jenv.
export PATH="$HOME/.jenv/bin:$PATH"
eval "$(jenv init -)"

# Set up pyenv.
# See: https://github.com/pyenv/pyenv
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init --path)"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"

# Set up rbenv.
eval "$(rbenv init -)"

# Set default AWS profile.
export AWS_PROFILE=master.root

# Set default Python virtualenv.
if command -v pyenv >/dev/null; then
  if [[ "$(pyenv version-name)" != "default" ]]; then
    pyenv activate default
  fi
fi
