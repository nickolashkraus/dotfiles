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
# INSTALLATION
#   Symlink file to Oh My Zsh themes directory:
#
#     ln -s nhk.zsh-theme ~/.oh-my-zsh/custom/themes/nhk.zsh-theme
#
#   Install Powerline fonts to render custom/private symbols (e.g., \uE0A0):
#
#     git clone https://github.com/powerline/fonts.git --depth=1
#     cd fonts
#     ./install.sh
#     cd ..
#     rm -rf fonts
###############################################################################

ZSH_THEME_GIT_PROMPT_PREFIX=" on %{$fg_bold[default]%}\uE0A0 "
ZSH_THEME_GIT_PROMPT_SUFFIX="%{$reset_color%}"
ZSH_THEME_GIT_PROMPT_DIRTY="%{$reset_color%}%{$fg[red]%}!"
ZSH_THEME_GIT_PROMPT_UNTRACKED="%{$fg[green]%}?"
ZSH_THEME_GIT_PROMPT_CLEAN=""

ZSH_THEME_AWS_PROFILE_PREFIX="["
ZSH_THEME_AWS_PROFILE_SUFFIX="]"
ZSH_THEME_AWS_REGION_PREFIX="["
ZSH_THEME_AWS_REGION_SUFFIX="]"

PROMPT='
%{$fg_bold[default]%}${PWD/#$HOME/~}%{$reset_color%}\
$(git_prompt_info)\
%{$fg[default]%} \
$([ -n "$(virtualenv_prompt_info)" ] && echo "$(virtualenv_prompt_info) ")%{$reset_color%}\
$(aws_prompt_info) \
%{$fg[red]%}%*%{$reset_color%}
$ '
