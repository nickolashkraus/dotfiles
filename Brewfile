###############################################################################
# Brewfile (Homebrew Packages)
#
# DESCRIPTION
#   Brewfile for Homebrew.
#
#   Homebrew is a package manager for macOS and Linux that makes it easy to
#   install, manage, and update software from the command line.
#
#   See: https://brew.sh
#
#   A Brewfile is a declarative interface for installing/upgrading packages
#   with Homebrew. This file was created using a combination of `brew bundle
#   dump` and `brew leaves`.
#
#   See: https://docs.brew.sh/Brew-Bundle-and-Brewfile
#
# INSTALLATION
#   Install via Homebrew:
#
#     brew bundle check || brew bundle install
###############################################################################

# The databricks tap is third-party, so a one-time `brew trust --formula
# databricks/tap/databricks` is required before `brew bundle install` can
# resolve it. Homebrew refuses to load the formula otherwise.
tap "conductorone/cone"
tap "databricks/tap"
tap "derailed/k9s"
tap "felixkratz/formulae"
tap "hashicorp/tap"
tap "koekeishiya/formulae"
tap "oven-sh/bun"

brew "awscli"
brew "bash"
brew "bat"
brew "bun"
brew "bzip2"
brew "cmake"
brew "conductorone/cone/cone"
brew "curl"
brew "databricks/tap/databricks"
brew "felixkratz/formulae/borders"
brew "ffmpeg@4"
brew "fzf"
brew "gh"
brew "git"
brew "gnu-sed"
brew "gnupg"
brew "go"
brew "googleworkspace-cli"
brew "hatch"
brew "helm"
brew "httpie"
brew "hugo"
brew "jq"
brew "k9s"
brew "kind"
brew "koekeishiya/formulae/skhd"
brew "koekeishiya/formulae/yabai"
brew "libpq"
brew "mas"
brew "minikube"
brew "mpv"
brew "nginx"
brew "nmap"
brew "node"
brew "numpy"
brew "nvm"
brew "openjdk"
brew "openjdk@11"
brew "perl"
brew "pipx"
brew "pyenv"
brew "pyenv-virtualenv"
brew "python-setuptools"
brew "ripgrep"
brew "shellcheck"
brew "shfmt"
brew "telnet"
brew "terraform-docs"
brew "tfenv"
brew "tflint"
brew "tfsec"
brew "the_silver_searcher"
brew "tmux"
brew "tree"
brew "universal-ctags"
brew "vale"
brew "vim"
brew "yamllint"
brew "yt-dlp"
brew "zlib"
brew "zoxide"

# Docker Desktop is intentionally absent. Its cask upgrade requires sudo to
# remove privileged helpers, which fails in the unattended system-update run.
# Docker Desktop self-updates instead.
cask "alfred"
cask "firefox"
cask "gcloud-cli"
cask "gimp"
cask "iterm2"
cask "linear"
cask "notion"
cask "obsidian"
cask "slack"

mas "Fantastical", id: 975937182
mas "Gifox", id: 1461845568
mas "Todoist", id: 585829637
