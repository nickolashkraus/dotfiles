# vim:ft=zsh ts=2 sw=2 sts=2
#                                     _     _
#                               _ __ | |__ | | __
#                              | '_ \| '_ \| |/ /
#                              | | | | | | |   <
#                              |_| |_|_| |_|_|\_\
#
#               This is the personal Zsh theme of Nickolas Kraus.

# Install Powerline fonts in order to render \uE0A0.
#
# Run the following:
#
#   git clone https://github.com/powerline/fonts.git --depth=1
#   cd fonts
#   ./install.sh
#   cd ..
#   rm -rf fonts

ZSH_THEME_GIT_PROMPT_PREFIX=" on %{$fg_bold[default]%}\uE0A0 "
ZSH_THEME_GIT_PROMPT_SUFFIX="%{$reset_color%}"
ZSH_THEME_GIT_PROMPT_DIRTY="%{$reset_color%}%{$fg[red]%}!"
ZSH_THEME_GIT_PROMPT_UNTRACKED="%{$fg[green]%}?"
ZSH_THEME_GIT_PROMPT_CLEAN=""

ZSH_THEME_AWS_PREFIX="["
ZSH_THEME_AWS_SUFFIX="]"

PROMPT='
%{$fg_bold[default]%}${PWD/#$HOME/~}%{$reset_color%}\
$(git_prompt_info)\
%{$fg[default]%} \
$(virtualenv_prompt_info)%{$reset_color%} \
$(aws_prompt_info) \
%{$fg[red]%}%*%{$reset_color%}
$ '
