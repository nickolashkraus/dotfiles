# vim: fdm=marker
#!/usr/bin/env bash

# ${HOME}                                                                    {{{1
# -----------------------------------------------------------------------------

WORKSPACE=NickolasHKraus

rm "${HOME}/.agignore"
ln -s "${HOME}/${WORKSPACE}/dotfiles/.agignore" "${HOME}/.agignore"

rm "${HOME}/.cobra.yaml"
ln -s "${HOME}/${WORKSPACE}/dotfiles/.cobra.yaml" "${HOME}/.cobra.yaml"

rm "${HOME}/.gitconfig"
ln -s "${HOME}/${WORKSPACE}/dotfiles/.gitconfig" "${HOME}/.gitconfig"

rm "${HOME}/.gitignore"
ln -s "${HOME}/${WORKSPACE}/dotfiles/.gitignore" "${HOME}/.gitignore"

rm "${HOME}/.powerline.conf"
ln -s "${HOME}/${WORKSPACE}/dotfiles/.powerline.conf" "${HOME}/.powerline.conf"

rm "${HOME}/.tmux.conf"
ln -s "${HOME}/${WORKSPACE}/dotfiles/.tmux.conf" "${HOME}/.tmux.conf"

rm "${HOME}/.vimrc"
ln -s "${HOME}/${WORKSPACE}/dotfiles/.vimrc" "${HOME}/.vimrc"

rm "${HOME}/.zshrc"
ln -s "${HOME}/${WORKSPACE}/dotfiles/.zshrc" "${HOME}/.zshrc"


# ${HOME}/.config                                                            {{{1
# -----------------------------------------------------------------------------

rm -rf "${HOME}/.config/mpv"
mkdir -p "${HOME}/.config/mpv"
ln -s "${HOME}/${WORKSPACE}/dotfiles/.mpv/mpv.conf" "${HOME}/.config/mpv/mvp.conf"

rm -rf "${HOME}/.config/powerline"
mkdir -p "${HOME}/.config/powerline"
mkdir -p "${HOME}/.config/powerline/colorschemes/tmux"
mkdir -p "${HOME}/.config/powerline/themes/tmux"

ln -s "${HOME}/${WORKSPACE}/dotfiles/.powerline/colorschemes/tmux/default.json" \
  "${HOME}/.config/powerline/colorschemes/tmux/default.json"
ln -s "${HOME}/${WORKSPACE}/dotfiles/.powerline/colorschemes/tmux/solarized.json" \
  "${HOME}/.config/powerline/colorschemes/tmux/solarized.json"

ln -s "${HOME}/${WORKSPACE}/dotfiles/.powerline/colorschemes/default.json" \
  "${HOME}/.config/powerline/colorschemes/default.json"
ln -s "${HOME}/${WORKSPACE}/dotfiles/.powerline/colorschemes/solarized.json" \
  "${HOME}/.config/powerline/colorschemes/solarized.json"

ln -s "${HOME}/${WORKSPACE}/dotfiles/.powerline/themes/tmux/default.json" \
  "${HOME}/.config/powerline/themes/tmux/default.json"
ln -s "${HOME}/${WORKSPACE}/dotfiles/.powerline/themes/powerline_terminus.json" \
  "${HOME}/.config/powerline/themes/powerline_terminus.json"

ln -s "${HOME}/${WORKSPACE}/dotfiles/.powerline/colors.json" \
  "${HOME}/.config/powerline/colors.json"
ln -s "${HOME}/${WORKSPACE}/dotfiles/.powerline/config.json" \
  "${HOME}/.config/powerline/config.json"


# ${HOME}/.k9s                                                               {{{1
# -----------------------------------------------------------------------------

rm "${HOME}"/.k9s/*
ln -s "${HOME}/${WORKSPACE}/dotfiles/.k9s/config.yml" "${HOME}/.k9s/config.yml"
ln -s "${HOME}/${WORKSPACE}/dotfiles/.k9s/skin.yml" "${HOME}/.k9s/skin.yml"

# ${HOME}/.ssh                                                               {{{1
# -----------------------------------------------------------------------------

rm "${HOME}/.ssh/config"
ln -s "${HOME}/${WORKSPACE}/dotfiles/.ssh/config" "${HOME}/.ssh/config"


# ${HOME}/.vim                                                               {{{1
# -----------------------------------------------------------------------------

rm "${HOME}/.vim/.en.utf-8.add"
ln -s "${HOME}/${WORKSPACE}/dotfiles/.en.utf-8.add" "${HOME}/.vim/.en.utf-8.add"


# ${HOME}/Library                                                            {{{1
# -----------------------------------------------------------------------------

rm "${HOME}"/Library/Application\ Support/Spectacle/Shortcuts.json
ln -s "${HOME}/${WORKSPACE}/dotfiles/Shortcuts.json" \
  "${HOME}"/Library/Application\ Support/Spectacle/Shortcuts.json
