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
source "$HOME/.config/shell/aliases.sh"
source "$HOME/.config/shell/exports.sh"
source "$HOME/.config/shell/functions.sh"
source "$HOME/.config/shell/utilities.sh"
