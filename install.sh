rm ~/.gitconfig
ln -s ~/Workspace/dotfiles/.gitconfig ~/.gitconfig

rm ~/.zshrc
ln -s ~/Workspace/dotfiles/.zshrc ~/.zshrc

rm ~/.tmux.conf
ln -s ~/Workspace/dotfiles/.tmux.conf ~/.tmux.conf

rm ~/.vimrc
ln -s ~/Workspace/dotfiles/.vimrc ~/.vimrc

mkdir -p .config/mpv
rm ~/.config/mpv/mpv.conf
ln -s Workspace/dotfiles/mpv.conf ~/.config/mpv/mpv.conf

rm ~/Library/Application\ Support/Spectacle/Shortcuts.json
ln -s ~/Workspace/dotfiles/Shortcuts.json ~/Library/Application\ Support/Spectacle/Shortcuts.json

rm ~/.agignore
ln -s ~/Workspace/dotfiles/.agignore ~/.agignore
