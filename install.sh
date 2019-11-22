#!/usr/bin/env bash

rm ~/.agignore
ln -s ~/Workspace/dotfiles/.agignore ~/.agignore

rm ~/.cobra.yaml
ln -s ~/Workspace/dotfiles/.cobra.yaml ~/.cobra.yaml

rm ~/.vim/.en.utf-8.add
ln -s ~/Workspace/dotfiles/.en.utf-8.add ~/.vim/.en.utf-8.add

rm ~/.gitconfig
ln -s ~/Workspace/dotfiles/.gitconfig ~/.gitconfig

rm ~/.gitignore
ln -s ~/Workspace/dotfiles/.gitignore ~/.gitignore

rm ~/.powerline.conf
ln -s ~/Workspace/dotfiles/.powerline.conf ~/.powerline.conf

rm ~/.ssh/config
ln -s ~/Workspace/dotfiles/.ssh_config ~/.ssh/config

rm ~/.tmux.conf
ln -s ~/Workspace/dotfiles/.tmux.conf ~/.tmux.conf

rm ~/.vimrc
ln -s ~/Workspace/dotfiles/.vimrc ~/.vimrc

rm ~/.zshrc
ln -s ~/Workspace/dotfiles/.zshrc ~/.zshrc

rm ~/.config/mpv/mpv.conf
ln -s Workspace/dotfiles/mpv.conf ~/.config/mpv/mpv.conf

rm ~/Library/Application\ Support/Spectacle/Shortcuts.json
ln -s ~/Workspace/dotfiles/Shortcuts.json ~/Library/Application\ Support/Spectacle/Shortcuts.json
