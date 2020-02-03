" vim: fdm=marker

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
Plugin 'NickolasHKraus/nerdtree-git-plugin'
Plugin 'Valloric/YouCompleteMe'
Plugin 'Vimjas/vim-python-pep8-indent'
Plugin 'airblade/vim-gitgutter'
Plugin 'altercation/vim-colors-solarized'
Plugin 'fatih/vim-go'
Plugin 'hashivim/vim-terraform'
Plugin 'itchyny/lightline.vim'
Plugin 'jiangmiao/auto-pairs'
Plugin 'mileszs/ack.vim'
Plugin 'pseewald/vim-anyfold'
Plugin 'scrooloose/nerdcommenter'
Plugin 'scrooloose/nerdtree'
Plugin 'sheerun/vim-polyglot'
Plugin 'sjl/vitality.vim'
Plugin 'tpope/vim-fugitive'
Plugin 'tpope/vim-surround'
Plugin 'vim-syntastic/syntastic'

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

" set vertical column color to black
highlight ColorColumn ctermbg=darkgray

" set spell check language
set spelllang=en_us

" set spell check file
set spellfile=$HOME/.vim/.en.utf-8.add

" automatically remove trailing whitespace before write
autocmd BufWritePre * %s/\s\+$//e

" enable normal backspace behavior
set backspace=indent,eol,start

" set pmenu (pop-up menu) color
highlight Pmenu ctermfg=gray ctermbg=darkgray

" set 'set paste' toggle to <F10>
set pastetoggle=<F10>

" set updatetime to 100 ms
set updatetime=100

" degrade colorscheme to set compatible with 256 terminal palette
let g:solarized_termcolors=256

" set background color
set background=dark

" load the solarized colorscheme
colorscheme solarized

" set automatic formatting options
set formatoptions+=r


" Autocommands                                                             {{{1
" -----------------------------------------------------------------------------

" `:autocmd` adds to the list of autocommands regardless of whether they are
" already present. When your .vimrc file is sourced twice, the autocommands
" will appear twice. To avoid this, define your autocommands in a group, so
" that you can easily clear them:
"
" 	augroup vimrc
" 	  " Remove all vimrc autocommands
" 	  autocmd!
" 	  au BufNewFile,BufRead *.html so <sfile>:h/html.vim
" 	augroup END
"
" If you don't want to remove all autocommands, you can instead use a variable
" to ensure that Vim includes the autocommands only once:
"
" 	:if !exists("autocommands_loaded")
" 	:  let autocommands_loaded = 1
" 	:  au ...
" 	:endif

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

  " open packages in readonly, nomodifiable mode
  autocmd BufReadPre,BufNewFile /usr/local/Cellar/* setlocal readonly nomodifiable
  autocmd! BufReadPre,BufNewFile /usr/local/Cellar/* setlocal readonly nomodifiable
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

" YouCompleteMe                                                            {{{2
" -----------------------------------------------------------------------------

" close preview window after completion
let g:ycm_autoclose_preview_window_after_completion=1

" map GoTo subcommand to <leader> + g
map <leader>g :YcmCompleter GoTo<CR>

" disable YouCompleteMe for file types: ['gitcommit']
let g:ycm_filetype_specific_completion_to_disable = {
      \ 'gitcommit': 1
      \}

let g:ycm_key_list_stop_completion = ['<C-y>', '<CR>']


" ack                                                                      {{{2
" -----------------------------------------------------------------------------

" use Ag with ack.vim
let g:ackprg = 'ag --nogroup --nocolor --column'

" do not open files in NERDTree
nnoremap <silent> <expr> <C-O> (expand('%') =~ 'NERD_tree' ? "\<c-w>\<c-w>" : '').":FZF\<cr>"


" fzf                                                                      {{{2
" -----------------------------------------------------------------------------

" add fzf to Vim runtimepath if installed using Homebrew
set rtp+=/usr/local/opt/fzf

" default key bindings
let g:fzf_action = {
      \ 'ctrl-t': 'tab split',
      \ 'ctrl-s': 'split',
      \ 'ctrl-v': 'vsplit' }

" map :FZF to CTRL + o
map <C-O> :FZF<CR>

" ignore files specified in .gitignore
let $FZF_DEFAULT_COMMAND = 'ag --hidden -g ""'

" do not open files in NERDTree
nnoremap <silent> <expr> <C-O> (expand('%') =~ 'NERD_tree' ? "\<c-w>\<c-w>" : '').":FZF\<cr>"


" lightline                                                                {{{2
" -----------------------------------------------------------------------------
let g:lightline = {
      \ 'colorscheme': 'default',
      \ 'active': {
      \   'left': [ [ 'mode', 'paste' ],
      \             [ 'gitbranch', 'readonly', 'filename', 'modified' ] ]
      \ },
      \ 'component_function': {
      \   'gitbranch': 'fugitive#head'
      \ },
      \ }


" nerdcommenter                                                            {{{2
" -----------------------------------------------------------------------------

"add spaces after comment delimiters by default
let g:NERDSpaceDelims = 1


" nerdtree                                                                 {{{2
" -----------------------------------------------------------------------------

" map toggle NERDTree to CTRL + n
map <C-N> :NERDTreeToggle<CR>

" show hidden files by default
let g:NERDTreeShowHidden=1

" ignore specifc files
let g:NERDTreeIgnore=['\.pyc$', '\~$', '\.swp$']

" set sorting of nodes to be case-sensitive
let g:NERDTreeCaseSensitiveSort=1


" syntastic                                                                {{{2
" -----------------------------------------------------------------------------

set statusline+=%#warningmsg#
set statusline+=%{SyntasticStatuslineFlag()}
set statusline+=%*

highlight SyntasticErrorSign ctermfg=darkred ctermbg=235
highlight SyntasticWarningSign ctermfg=darkyellow ctermbg=235

let g:syntastic_always_populate_loc_list = 1
let g:syntastic_auto_loc_list = 1
let g:syntastic_check_on_open = 1
let g:syntastic_check_on_wq = 0

" configure Go syntax checkers
" available checkers:
" go, gofmt, GolangCI-Lint, Golint, Go Meta Linter, gotype, vet
let g:syntastic_go_checkers = ['go', 'gofmt', 'gotype', 'vet']

" configure Python and Python3 syntax checkers
" available checkers:
" Bandit, flake8, Frosted, mypy, Prospector, py3kwarn, pycodestyle, pydocstyle,
" Pyflakes, Pylama, Pylint, python
let g:syntastic_python_checkers = ['flake8', 'pyflakes', 'pylint', 'python']
let g:syntastic_python_flake8_exe = 'python3 -m flake8'

" configure Vim syntax checkers
" available checkers:
" vimlint, vint
let g:syntastic_vim_checkers = ['vimlint', 'vint']


" vim-anyfold                                                              {{{2
" -----------------------------------------------------------------------------

autocmd Filetype * AnyFoldActivate
set foldlevel=99


" vim-autoformat                                                           {{{2
" -----------------------------------------------------------------------------

" set :Autoformat command to <F3>
noremap <F3> :Autoformat<CR>

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
