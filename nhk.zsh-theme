###############################################################################
# Oh My Zsh Theme
# vim:ft=zsh ts=2 sw=2 sts=2
#                                     _     _
#                               _ __ | |__ | | __
#                              | '_ \| '_ \| |/ /
#                              | | | | | | |   <
#                              |_| |_|_| |_|_|\_\
#
#               This is the personal Zsh theme of Nickolas Kraus.
#
# DESCRIPTION
#   My personal Zsh theme.
#
#   Colorscheme:
#     • #a89984 (Gruvbox: light4)
#     • #98971a (Gruvbox: neutral_green)
#     • #cc241d (Gruvbox: neutral_red)
#     • #d5c4a1 (Gruvbox: light2)
#
#   Example:
#
#     ~/nickolashkraus/dotfiles on  master! [default] [master.root] 13:37:00
#     |---------- 1 ----------| |---- 2 ---| |-- 3 --| |---- 4 ----| |-- 5 -|
#
#     1: ${PWD/#$HOME/~} - Shows current directory, replacing home path with ~
#     2: $(git_prompt_info) - Shows Git branch and status information
#     3: $(virtualenv_prompt_info) - Shows virtualenv info
#     4: $(aws_prompt_info) - Shows AWS profile/region
#     5: %* - Shows current time (HH:MM:SS format)
#
# INSTALLATION
#   Symlink file to Oh My Zsh themes directory:
#
#     ln -s nhk.zsh-theme $ZSH_CUSTOM/themes/nhk.zsh-theme
#
#   Install Powerline fonts to render custom/private symbols (e.g., \uE0A0):
#
#     git clone https://github.com/powerline/fonts.git --depth=1
#     cd fonts
#     ./install.sh
#     cd ..
#     rm -rf fonts
###############################################################################

ZSH_THEME_GIT_PROMPT_PREFIX="%F{#a89984} on \uE0A0 "
ZSH_THEME_GIT_PROMPT_SUFFIX="%{$reset_color%}"
ZSH_THEME_GIT_PROMPT_DIRTY="%{$reset_color%}%F{#cc241d}!"
ZSH_THEME_GIT_PROMPT_UNTRACKED="%{$reset_color%}%F{#98971a}?"
ZSH_THEME_GIT_PROMPT_CLEAN=""

ZSH_THEME_AWS_PROFILE_PREFIX="%F{#a89984}["
ZSH_THEME_AWS_PROFILE_SUFFIX="]%{$reset_color%}"
ZSH_THEME_AWS_REGION_PREFIX="%F{#a89984}["
ZSH_THEME_AWS_REGION_SUFFIX="]%{$reset_color%}"

PROMPT='
%F{#d5c4a1}${PWD/#$HOME/~}%{$reset_color%}\
$(git_prompt_info)\
%F{#a89984} \
$([ -n "$(virtualenv_prompt_info)" ] && echo "$(virtualenv_prompt_info) ")%{$reset_color%}\
$(aws_prompt_info) \
%F{#cc241d}%*%{$reset_color%}
$ '
