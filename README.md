# dotfiles

## Installation

```bash
ln -s ~/path/to/remote/dotfile ~/path/to/local/dotfile
```

From *Essential System Administration* by Æleen Frisch

> "Symbolic links are pointer files that refer to a different file or directory elsewhere in the filesystem. Symbolic links may span filesystems, because they point to a Unix pathname, not to a specific inode."

### Git

```bash
xcode-select --install
```

### iTerm2

```bash
curl -LOk https://iterm2.com/downloads/stable/iTerm2-3_2_3.zip
unzip -q iTerm2-3_2_3.zip
mv iTerm.app /Applications
rm iTerm2-3_2_3.zip
```

### Zsh

```bash
sh -c "$(curl -fsSL https://raw.githubusercontent.com/robbyrussell/oh-my-zsh/master/tools/install.sh)"
```

### Powerline

```bash
pip install --user powerline-status
```

### Powerline fonts

```bash
git clone https://github.com/powerline/fonts.git --depth=1
cd fonts
./install.sh
cd ..
rm -rf fonts
```

### Homebrew

```eash
/usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
```

### tmux

```bash
brew install tmux
```

### Vim

```bash
brew install vim --with-override-system-vi
```

### Vundle

```bash
git clone https://github.com/VundleVim/Vundle.vim.git ~/.vim/bundle/Vundle.vim
```

### mpv

```bash
brew install mpv
```

### Spectacle

```bash
curl -LOk https://s3.amazonaws.com/spectacle/downloads/Spectacle+1.2.zip
unzip -q Spectacle+1.2.zip
mv Spectacle.app /Applications
rm Spectacle+1.2.zip
```

### ag

```bash
brew install ag
```

### fzf

```bash
brew install fzf
$(brew --prefix)/opt/fzf/install
```
