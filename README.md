# dotfiles

## Installation

```bash
ln -s ~/path/to/remote/dotfile ~/path/to/local/dotfile
```

From *Essential System Administration* by Æleen Frisch

> "Symbolic links are pointer files that refer to a different file or directory elsewhere in the filesystem. Symbolic links may span filesystems, because they point to a Unix pathname, not to a specific inode."

## Applications

### Chrome

```bash
https://www.google.com/chrome/browser/desktop/index.html
```

### iTerm2

```bash
curl -LOk https://iterm2.com/downloads/stable/iTerm2-3_1_4.zip
unzip iTerm2-3_1_4.zip
```

### zsh

```bash
sh -c "$(curl -fsSL https://raw.githubusercontent.com/robbyrussell/oh-my-zsh/master/tools/install.sh)"
```

### Homebrew

```bash
/usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
```

### tmux

```bash
brew install tmux
```

### Powerline fonts

```bash
git clone https://github.com/powerline/fonts.git --depth=1
cd fonts
./install.sh
cd ..
rm -rf fonts
```

### Vim

```bash
brew install vim --with-override-system-vi
```

### Vundle

```bash
git clone https://github.com/VundleVim/Vundle.vim.git ~/.vim/bundle/Vundle.vim
```

### Spectacle

```bash
curl -LOk https://s3.amazonaws.com/spectacle/downloads/Spectacle+1.2.zip
unzip Spectacle+1.2.zip
```
