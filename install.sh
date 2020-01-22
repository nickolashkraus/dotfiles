# vim: fdm=marker
#!/usr/bin/env bash

# ~                                                                        {{{1
# -----------------------------------------------------------------------------

rm ~/.agignore
ln -s ~/Workspace/dotfiles/.agignore ~/.agignore

rm ~/.cobra.yaml
ln -s ~/Workspace/dotfiles/.cobra.yaml ~/.cobra.yaml

rm ~/.gitconfig
ln -s ~/Workspace/dotfiles/.gitconfig ~/.gitconfig

rm ~/.gitignore
ln -s ~/Workspace/dotfiles/.gitignore ~/.gitignore

rm ~/.powerline.conf
ln -s ~/Workspace/dotfiles/.powerline.conf ~/.powerline.conf

rm ~/.tmux.conf
ln -s ~/Workspace/dotfiles/.tmux.conf ~/.tmux.conf

rm ~/.vimrc
ln -s ~/Workspace/dotfiles/.vimrc ~/.vimrc

rm ~/.zshrc
ln -s ~/Workspace/dotfiles/.zshrc ~/.zshrc


# ~/.config                                                                {{{1
# -----------------------------------------------------------------------------

rm -rf ~/.config/mpv
mkdir -p ~/.config/mpv
ln -s ~/Workspace/dotfiles/.mpv/mpv.conf ~/.config/mpv/mvp.conf

rm -rf ~/.config/powerline
mkdir -p ~/.config/powerline
mkdir -p ~/.config/powerline/colorschemes/tmux
mkdir -p ~/.config/powerline/themes/tmux

ln -s ~/Workspace/dotfiles/.powerline/colorschemes/tmux/default.json \
  ~/.config/powerline/colorschemes/tmux/default.json
ln -s ~/Workspace/dotfiles/.powerline/colorschemes/tmux/solarized.json \
  ~/.config/powerline/colorschemes/tmux/solarized.json

ln -s ~/Workspace/dotfiles/.powerline/colorschemes/default.json \
  ~/.config/powerline/colorschemes/default.json
ln -s ~/Workspace/dotfiles/.powerline/colorschemes/solarized.json \
  ~/.config/powerline/colorschemes/solarized.json

ln -s ~/Workspace/dotfiles/.powerline/themes/tmux/default.json \
  ~/.config/powerline/themes/tmux/default.json
ln -s ~/Workspace/dotfiles/.powerline/themes/powerline_terminus.json \
  ~/.config/powerline/themes/powerline_terminus.json

ln -s ~/Workspace/dotfiles/.powerline/colors.json ~/.config/powerline/colors.json
ln -s ~/Workspace/dotfiles/.powerline/config.json ~/.config/powerline/config.json


# ~/.ssh                                                                   {{{1
# -----------------------------------------------------------------------------

rm ~/.ssh/config
ln -s ~/Workspace/dotfiles/.ssh_config ~/.ssh/config


# ~/.vim                                                                   {{{1
# -----------------------------------------------------------------------------

rm ~/.vim/.en.utf-8.add
ln -s ~/Workspace/dotfiles/.en.utf-8.add ~/.vim/.en.utf-8.add


# ~/Library                                                                {{{1
# -----------------------------------------------------------------------------

rm ~/Library/Application\ Support/Spectacle/Shortcuts.json
ln -s ~/Workspace/dotfiles/Shortcuts.json \
  ~/Library/Application\ Support/Spectacle/Shortcuts.json
