#!/usr/bin/env bash

rm ~/.agignore
ln -s ~/Workspace/dotfiles/.agignore ~/.agignore

rm ~/.gitconfig
ln -s ~/Workspace/dotfiles/.gitconfig ~/.gitconfig

rm ~/.gitignore
ln -s ~/Workspace/dotfiles/.gitignore ~/.gitignore

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
