"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
" Vim Configuration
"
" DESCRIPTION
"   Configuration file for Vim.
"
"   Vim (short for Vi IMproved) is a highly configurable, powerful text editor
"   used primarily for programming and system administration. It is an
"   enhanced version of the Unix vi editor, offering many features for
"   efficient text manipulation.
"
"   See: https://www.vim.org
"
" INSTALLATION
"   Symlink file to $HOME/.vimrc:
"
"     ln -s .vimrc $HOME/.vimrc
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

" Vundle                                                                   {{{1
" -----------------------------------------------------------------------------

set nocompatible              " be iMproved, required
filetype off                  " required

" set the runtime path to include Vundle and initialize
set rtp+=~/.vim/bundle/Vundle.vim
call vundle#begin()
" alternatively, pass a path where Vundle should install plugins
"call vundle#begin('~/some/path/here')

" let Vundle manage Vundle, required
Plugin 'VundleVim/Vundle.vim'

Plugin 'Chiel92/vim-autoformat'
Plugin 'Vimjas/vim-python-pep8-indent'
Plugin 'Xuyuanp/nerdtree-git-plugin'
Plugin 'airblade/vim-gitgutter'
Plugin 'altercation/vim-colors-solarized'
Plugin 'dense-analysis/ale'
Plugin 'fatih/vim-go'
Plugin 'hashivim/vim-terraform'
Plugin 'jiangmiao/auto-pairs'
Plugin 'junegunn/fzf'
Plugin 'mileszs/ack.vim'
Plugin 'morhetz/gruvbox'
Plugin 'preservim/nerdtree'
Plugin 'preservim/vim-markdown'
Plugin 'pseewald/vim-anyfold'
Plugin 'sheerun/vim-polyglot'
Plugin 'sjl/vitality.vim'
Plugin 'tpope/vim-commentary'
Plugin 'tpope/vim-fugitive'
Plugin 'tpope/vim-sensible'
Plugin 'tpope/vim-sleuth'
Plugin 'tpope/vim-surround'
Plugin 'vim-airline/vim-airline'
Plugin 'vim-airline/vim-airline-themes'
Plugin 'ycm-core/YouCompleteMe'

" All of your Plugins must be added before the following line
call vundle#end()            " required
filetype plugin indent on    " required
" To ignore plugin indent changes, instead use:
"filetype plugin on
"
" Brief help
" :PluginList       - lists configured plugins
" :PluginInstall    - installs plugins; append `!` to update or just :PluginUpdate
" :PluginSearch foo - searches for foo; append `!` to refresh local cache
" :PluginClean      - confirms removal of unused plugins; append `!` to auto-approve removal
"
" see :h vundle for more details or wiki for FAQ
" Put your non-Plugin stuff after this line

" Basic                                                                    {{{1
" -----------------------------------------------------------------------------

" enable syntax highlighting
syntax enable

" specify the character encoding
scriptencoding utf-8

" vertical split (:split, :sp) below current pane
set splitbelow

" horizontal split (:vsplit, :vs) right of current pane
set splitright

" show line numbers
set number

" tab width set to 2
set tabstop=2

" indents will have width of 2
set shiftwidth=2

" expand tabs to spaces
set expandtab

" enable 256-bit color
set t_Co=256

" always display status line
set laststatus=2

" hide mode
set noshowmode

" set vertical column color
highlight ColorColumn ctermbg=darkgray

" set spell check language
set spelllang=en_us

" set spell check file
set spellfile=$HOME/.vim/.en.utf-8.add

" automatically remove trailing whitespace before write (exclude Markdown)
autocmd BufWritePre * if &filetype !~ '\(markdown\|md\)' | %s/\s\+$//e | endif

" enable normal backspace behavior
set backspace=indent,eol,start

" set pmenu (pop-up menu) color
highlight Pmenu ctermfg=gray ctermbg=darkgray

" set 'set paste' toggle to <F10>
set pastetoggle=<F10>

" set updatetime to 100 ms
set updatetime=100

" set background color
set background=dark

" load the gruvbox colorscheme
colorscheme gruvbox

" set automatic formatting options
set formatoptions+=r

" set SignColumn color
highlight SignColumn ctermbg=235

" set IncSearch color
" 166 = orange
highlight IncSearch ctermfg=235 ctermbg=166

" set Error color
" 167 = bright red
highlight Error ctermfg=235 ctermbg=167

" Autocommands                                                             {{{1
" -----------------------------------------------------------------------------

" `:autocmd` adds to the list of autocommands regardless of whether they are
" already present. When your .vimrc file is sourced twice, the autocommands
" will appear twice. To avoid this, define your autocommands in a group, so
" that you can easily clear them:
"
"   augroup vimrc
"     " Remove all vimrc autocommands
"     autocmd!
"     au BufNewFile,BufRead *.html so <sfile>:h/html.vim
"   augroup END
"
" If you don't want to remove all autocommands, you can instead use a variable
" to ensure that Vim includes the autocommands only once:
"
"   :if !exists("autocommands_loaded")
"   :  let autocommands_loaded = 1
"   :  au ...
"   :endif

if !exists("autocommands_loaded")
  let autocommands_loaded = 1

  " show vertical column at 80th character
  autocmd BufReadPost,BufNewFile * set colorcolumn=80

  " enable spellcheck for ['gitcommit', 'markdown']
  autocmd FileType gitcommit setlocal spell
  autocmd FileType markdown setlocal spell

  " auto save all files when focus is lost or when switching buffers
  autocmd FocusLost,BufLeave * :wa

  " reduce timeout when entering or leaving INSERT mode
  augroup FastEscape
    autocmd InsertEnter * set timeoutlen=100
    autocmd InsertLeave * set timeoutlen=1000
  augroup END

  " open packages installed via Homebrew in readonly, nomodifiable mode
  autocmd BufReadPre,BufNewFile /opt/homebrew/cellar/* setlocal readonly nomodifiable
  autocmd! BufReadPre,BufNewFile /opt/homebrew/Cellar/* setlocal readonly nomodifiable

  " close location list window when buffer with errors is closed
  augroup CloseLoclistWindowGroup
      autocmd!
      autocmd QuitPre * if empty(&buftype) | lclose | endif
  augroup END

endif

" Remap                                                                    {{{1
" -----------------------------------------------------------------------------

" remap pane selection to CTRL + [jklh]
nnoremap <C-H> <C-W><C-H>
nnoremap <C-J> <C-W><C-J>
nnoremap <C-K> <C-W><C-K>
nnoremap <C-L> <C-W><C-L>

" remap leader key ('\') to '<Space>'
nnoremap <space> <nop>
let g:mapleader = "\<Space>"

" remap CTRL + I (go to newer entry in jump list) to <leader> + I
nnoremap <leader>i <C-I>

" remap CTRL + O (go to older entry in jump list) to <leader> + O
nnoremap <leader>o <C-O>

" remap CTRL + ] (jump to the definition of the keyword under the cursor) to
" <leader> + ]
nnoremap <leader>] <C-]>

" substitute all occurrences of the word under the cursor
nnoremap <leader>s :%s/\<<C-r><C-w>\>/

" set <leader>y to copy to the "* register (system clipboard)
noremap <leader>y "*y

" set <leader>p to paste from the "* register (system clipboard)
noremap <leader>p "*p

" set 'Q' to playback the recording put into the q register
noremap Q @q

" Plugins                                                                  {{{1
" -----------------------------------------------------------------------------

" Language                                                                 {{{2
" -----------------------------------------------------------------------------

" dense-analysis/ale                                                       {{{3
" -----------------------------------------------------------------------------

" set the background color for ALE error signs
highlight ALEErrorSign ctermfg=darkred ctermbg=235

" set the background color for ALE info signs
highlight ALEInfoSign ctermfg=darkyellow ctermbg=235

" set the background color for ALE warning signs
highlight ALEWarningSign ctermfg=darkyellow ctermbg=235

" do not automatically open a window for the location list
let g:ale_open_list = 1

" do not show problems with virtual-text (i.e. inline text)
let g:ale_virtualtext_cursor = 'disabled'

" disable LSP linters and `tsserver`
"
" >If you are running ALE in combination with another LSP client, you may wish
" >to disable ALE's LSP functionality entirely. You can change the setting to 1
" >to always disable all LSP functionality.
"
" See: https://github.com/dense-analysis/ale/tree/master#how-can-i-use-ale-with-other-lsp-clients
"
" NOTE: This also disables `tsserver` for TypeScript.
let g:ale_disable_lsp = 0

" configure mypy
"
" See: https://mypy.readthedocs.io/en/stable/running_mypy.html#following-imports
let g:ale_python_mypy_options = '--follow-imports=silent'

" TODO: Remove when updating ALE:
"
"   https://github.com/dense-analysis/ale/pull/4730
let g:ale_go_golangci_lint_package=1

" TODO: Add ALE fixers.
"
" See: https://github.com/dense-analysis/ale#fixing

" enable ALE to fix files on save
let g:ale_fix_on_save = 1

" set prettier as the fixer for appropriate file types
let g:ale_fixers = {
\   'javascript': ['prettier'],
\   'typescript': ['prettier'],
\   'css': ['prettier'],
\   'scss': ['prettier'],
\   'html': ['prettier'],
\   'json': ['prettier']
\}

" disable E501 error (line too long) for flake8 in ALE
let g:ale_python_flake8_options = '--ignore=E501'

" disable E501 error (line too long) for pycodestyle in ALE
let g:ale_python_pycodestyle_options = '--ignore=E501'

" disable ALE in status line
let g:ale_statusline_enabled = 0

" ALE settings for location list management
let g:ale_keep_list_window_open = 0
let g:ale_open_list = 1
let g:ale_set_loclist = 0

" let g:ale_linters = {
" \   'go': [],
" \}

" fatih/vim-go                                                             {{{3
" -----------------------------------------------------------------------------
" let g:go_metalinter_enabled = 0
" let g:go_fmt_autosave = 1
" let g:go_asmfmt_autosave = 1

" preservim/nerdtree                                                       {{{3
" -----------------------------------------------------------------------------

" toggle NERDTree (if closed, open it; if open, close it)
nnoremap <C-n> :NERDTreeToggle<CR>

" find the file for the active buffer in the NERDTree window
nnoremap <C-f> :NERDTreeFind<CR>

" show hidden files by default
let g:NERDTreeShowHidden=1

" ignore specific files
let g:NERDTreeIgnore=['\.pyc$', '\~$', '\.swp$', '\.mypy_cache$', '\.pytest_cache$', '__pycache__$']

" set sorting of nodes to be case-sensitive
let g:NERDTreeCaseSensitiveSort=2

let g:NERDTreeWinSize = 35

" YouCompleteMe                                                            {{{2
" -----------------------------------------------------------------------------

" defines the max size (in Kb) for a file to be considered for completion. If
" this option is set to 0 then no check is made on the size of the file you're
" opening. Default: 1000
let g:ycm_disable_for_files_larger_than_kb = 512

" toggle YCM with <F2>
" noremap <F2> :call ToggleYcm()<CR>

" Function: ToggleYcm()
" Sets b:ycm_largefile directly, thereby enabling or disabling YCM.
"
"   let threshold = g:ycm_disable_for_files_larger_than_kb * 1024
"   let b:ycm_largefile =
"         \ threshold > 0 && getfsize( expand( a:buffer ) ) > threshold
"
" Args: None
" Returns: None
function! ToggleYcm()
  if b:ycm_largefile == 0
    let b:ycm_largefile = 1
    echo 'YCM has been disabled.'
  else
    let b:ycm_largefile = 0
    echo 'YCM has been enabled.'
  endif
endfunction

" close preview window after completion
let g:ycm_autoclose_preview_window_after_completion=1

" map GoTo subcommand to <leader> + g
map <leader>g :YcmCompleter GoTo<CR>

" Horizontal split
nnoremap <leader>gs :split \| :YcmCompleter GoTo<CR>

" Vertical split
nnoremap <leader>gv :vsplit \| :YcmCompleter GoTo<CR>

" disable YouCompleteMe for file types: ['gitcommit']
let g:ycm_filetype_specific_completion_to_disable = {
      \ 'gitcommit': 1
      \}

let g:ycm_key_list_stop_completion = ['<C-y>', '<CR>']

" disable documentation popup
let g:ycm_auto_hover=""

" manually trigger documentation
nmap <leader>D <plug>(YCMHover)

" disable error checking
let g:ycm_show_diagnostics_ui = 0

" ack                                                                      {{{2
" -----------------------------------------------------------------------------

" use Ag with ack.vim
"   --column: Print column numbers in results.
"   --nogroup: Place the filename at the start of each match line.
"   --hidden: Search hidden files. This option obeys ignored files.
let g:ackprg = 'ag --column --nogroup --hidden'

" do not open files in NERDTree
nnoremap <silent> <expr> <C-O> (expand('%') =~ 'NERD_tree' ? "\<c-w>\<c-w>" : '').":FZF\<cr>"

" prevent automatically opening first result in current buffer
let g:ack_autoclose = 0
let g:ack_autofold_results = 0

" fzf                                                                      {{{2
" -----------------------------------------------------------------------------

" add fzf to Vim runtimepath if installed using Homebrew
set rtp+=/opt/homebrew/bin/fzf

" default key bindings
let g:fzf_action = {
      \ 'ctrl-t': 'tab split',
      \ 'ctrl-s': 'split',
      \ 'ctrl-v': 'vsplit' }

" configure layout
let g:fzf_layout = {'down': '40%'}

" map :FZF to CTRL + o
map <C-O> :FZF<CR>

" ignore files specified in .gitignore
let $FZF_DEFAULT_COMMAND = 'ag --hidden -g ""'

" do not open files in NERDTree
nnoremap <silent> <expr> <C-O> (expand('%') =~ 'NERD_tree' ? "\<c-w>\<c-w>" : '').":FZF\<cr>"

" hide statusline
"
" see: https://github.com/junegunn/fzf.vim#hide-statusline
autocmd! FileType fzf set laststatus=0 noshowmode noruler
  \| autocmd BufLeave <buffer> set laststatus=2 showmode ruler

" set colorscheme
let g:fzf_colors = {
      \ 'fg':         ['fg', 'GruvboxFg1'],
      \ 'bg':         ['bg', 'GruvboxBg0'],
      \ 'preview-fg': ['fg', 'GruvboxFg1'],
      \ 'preview-bg': ['bg', 'GruvboxBg0'],
      \ 'hl':         ['fg', 'GruvboxYellow'],
      \ 'fg+':        ['fg', 'CursorLine', 'CursorColumn', 'GruvboxFg1'],
      \ 'bg+':        ['bg', 'CursorLine', 'CursorColumn'],
      \ 'gutter':     ['fg', 'GruvboxBg1'],
      \ 'hl+':        ['fg', 'GruvboxYellow'],
      \ 'info':       ['fg', 'GruvboxBlue'],
      \ 'border':     ['fg', 'GruvboxBg1'],
      \ 'prompt':     ['fg', 'GruvboxFg3'],
      \ 'pointer':    ['fg', 'GruvboxBlue'],
      \ 'marker':     ['fg', 'GruvboxOrange'],
      \ 'spinner':    ['fg', 'GruvboxBlue'],
      \ 'header':     ['fg', 'GruvboxBg1']
      \ }

" vim-gitgutter                                                            {{{2
" -----------------------------------------------------------------------------
highlight GitGutterAdd ctermfg=darkgreen ctermbg=235
highlight GitGutterChange ctermfg=darkyellow ctermbg=235
highlight GitGutterChangeDelete ctermfg=darkyellow ctermbg=235
highlight GitGutterDelete ctermfg=darkred ctermbg=235

" vim-airline                                                              {{{2
" -----------------------------------------------------------------------------

" gruvbox theme
let g:airline_theme='gruvbox'

" enable Powerline fonts
let g:airline_powerline_fonts = 1

" diable ALE extension (airline-ale)
let g:airline#extensions#ale#enabled = 0

" diable whitespace extension (airline-whitespace)
let g:airline#extensions#whitespace#enabled = 0

" enable branch information (requires vim-fugitive)
let g:airline#extensions#branch#enabled = 1

" enable hunks information (requires vim-fugitive)
let g:airline#extensions#hunks#enabled = 1

let g:airline#extensions#nerdtree_statusline = 1

" vim-anyfold                                                              {{{2
" -----------------------------------------------------------------------------

" activate for all filetypes
autocmd Filetype * AnyFoldActivate

" open all folds
set foldlevel=99

" vim-autoformat                                                           {{{2
" -----------------------------------------------------------------------------

" set :Autoformat command to <F4>
noremap <F4> :Autoformat<CR>

" disable autoformat fallback behavior for file types: ['gitcommit']
autocmd FileType gitcommit let b:autoformat_autoindent=0
autocmd FileType gitcommit let g:autoformat_retab = 0
autocmd FileType gitcommit let g:autoformat_remove_trailing_spaces = 0

" vim-terraform                                                            {{{2
" -----------------------------------------------------------------------------

" allow vim-terraform to align settings automatically with Tabularize
let g:terraform_align=1

" allow vim-terraform to automatically fold (hide until unfolded) sections of
" terraform code. Defaults to 0 which is off.
let g:terraform_fold_sections=1

" allow vim-terraform to automatically format *.tf and *.tfvars files with
" `terraform fmt`. You can also do this manually with the :TerraformFmt
" command.
let g:terraform_fmt_on_save=1

" Other                                                                    {{{2
" -----------------------------------------------------------------------------

" tpope/vim-sensible                                                       {{{3
" -----------------------------------------------------------------------------

" preservim/nerdcommenter                                                  {{{3
" -----------------------------------------------------------------------------

" Add configuration here...
"
" See `:help nerdcommenter.txt` or https://github.com/preservim/nerdcommenter.

" Languages                                                                {{{1
" -----------------------------------------------------------------------------

" Python                                                                   {{{2
" -----------------------------------------------------------------------------

" set Python indentation
autocmd BufNewFile,BufRead *.py:
      \ set autoindent
      \ set expandtab
      \ set fileformat=unix
      \ set shiftwidth=4
      \ set softtabstop=4
      \ set tabstop=4
      \ set textwidth=79

" Shell                                                                    {{{2
" -----------------------------------------------------------------------------
" set global default shell type
let g:is_bash=1

" Vim                                                                      {{{2
" -----------------------------------------------------------------------------

" set Vimscript indentation
autocmd BufNewFile,BufRead *.vim:
      \ set autoindent
      \ set expandtab
      \ set fileformat=unix
      \ set shiftwidth=4
      \ set softtabstop=4
      \ set tabstop=4
      \ set textwidth=79

command! CopyRelPath let @+ = expand('%')
nnoremap <leader>cp :CopyRelPath<CR>

" Function: GetGitHubURL()
" Get the GitHub URL of the file for the current buffer.
"
" Args: None
" Returns: GitHub URL (string), or empty string on error
function! GetGitHubURL()
  " Check if inside Git repository.
  if system('git rev-parse --is-inside-work-tree 2>/dev/null')->trim() !=# 'true'
    echoerr 'Not inside a Git repository'
    return ''
  endif

  " Get remote URL.
  let l:remote = system('git config --get remote.origin.url 2>/dev/null')->trim()
  if v:shell_error != 0 || empty(l:remote)
    echoerr 'No remote origin found'
    return ''
  endif

  " Normalize GitHub URL (handles SSH and HTTPS remotes).
  if l:remote =~? '^git@'
    let l:remote = substitute(l:remote, '^git@[^:]*github\.com:', 'https://github.com/', '')
  else
    let l:remote = substitute(l:remote, '://[^/]*github\.com', '://github.com', '')
  endif

  " Strip trailing .git if present.
  let l:remote = substitute(l:remote, '\.git$', '', '')

  " Determine the repository's default branch (main or master).
  let l:branch = system('git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null')->trim()
  let l:branch = substitute(l:branch, '^refs/remotes/origin/', '', '')

  if empty(l:branch)
    echoerr 'Could not determine default branch'
    return ''
  endif

  " Get the repository's root and relative file path.
  let l:root = system('git rev-parse --show-toplevel 2>/dev/null')->trim()
  if v:shell_error != 0
    echoerr 'Could not determine repository root'
    return ''
  endif

  let l:relpath = expand('%:p')[len(l:root)+1:]

  " Build and return URL.
  let l:url = l:remote . '/blob/' . l:branch . '/' . l:relpath
  return l:url
endfunction

" Function: s:CopyGitHubURL()
" Copy the GitHub URL of the current buffer to the system clipboard.
"
" This function generates a GitHub permalink for the current file and copies it
" to the system clipboard.
"
" Examples:
"   https://github.com/user/repo/blob/main/src/file.py
"
" Args: None
" Returns: None
function! s:CopyGitHubURL()
  " Get GitHub URL of the file.
  let l:url = GetGitHubURL()

  " Do not copy empty URLs, error already shown.
  if empty(l:url)
    return
  endif

  " Copy to clipboard and show confirmation.
  let @+ = l:url
  echo 'Copied: ' . l:url
endfunction

command! CopyGitHubURL call s:CopyGitHubURL()
nnoremap <leader>cpgh :CopyGitHubURL<CR>

" Function: s:CopyGitHubURLWithRange() range
" Copy the GitHub URL of the current buffer to the system clipboard.
"
" This function generates a GitHub permalink for the current file and copies it
" to the system clipboard. When called with a visual selection, it includes
" line range anchors in the URL (e.g., #L13-L37).
"
" Requires the current buffer to be within a Git repository with a GitHub
" remote origin. Git must be available in the system PATH.
"
" Examples:
"   Normal mode: https://github.com/user/repo/blob/main/src/file.py#L13
"   Visual mode: https://github.com/user/repo/blob/main/src/file.py#L13-L37
"
" Args:
"   range: Line range from visual selection (a:firstline, a:lastline).
"          When called from normal mode, both values equal the current line.
"          When called from visual mode, contains the selected line range.
"
" Returns: None
function! s:CopyGitHubURLWithRange() range
  " Get GitHub URL of the file.
  let l:url = GetGitHubURL()

  " Do not copy empty URLs, error already shown.
  if empty(l:url)
    return
  endif

  " Add line numbers if called with a range (visual mode or explicit range).
  if a:firstline == a:lastline
    let l:url .= '#L' . a:firstline
  else
    let l:url .= '#L' . a:firstline . '-L' . a:lastline
  endif

  " Copy to clipboard and show confirmation.
  let @+ = l:url
  echo 'Copied: ' . l:url
endfunction

command! -range CopyGitHubURLWithRange <line1>,<line2>call s:CopyGitHubURLWithRange()
nnoremap <leader>cpghr :CopyGitHubURLWithRange<CR>
vnoremap <leader>cpghr :CopyGitHubURLWithRange<CR>
