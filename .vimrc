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

" Disable vi compatibility mode (enables Vim's enhanced features).
set nocompatible

" Disable Markdown syntax highlighting via vim-polyglot (use vim-markdown
" instead).
"
" NOTE: This variable must be set *before* vim-polyglot is loaded.
let g:polyglot_disabled = ['markdown']

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
" vim-plug Configuration
"
" vim-plug is a minimalist and fast plugin manager for Vim and Neovim. As of
" 2025, vim-plug remains the most widely-used plugin manager across Vim and
" Neovim, thanks to its speed, ease of use, and robust features.
"
" See: https://github.com/junegunn/vim-plug
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

call plug#begin()

" Language
Plug 'dense-analysis/ale'
Plug 'fatih/vim-go', { 'do': ':GoUpdateBinaries' }
Plug 'godlygeek/tabular'
Plug 'preservim/vim-markdown'
Plug 'sheerun/vim-polyglot'

" Completion
Plug 'jiangmiao/auto-pairs'
Plug 'ycm-core/YouCompleteMe', { 'do': {info -> BuildYCM(info)} }

" Code Display
Plug 'morhetz/gruvbox'

" Integrations
Plug 'airblade/vim-gitgutter'
Plug 'junegunn/fzf', { 'do': { -> fzf#install() } }
Plug 'junegunn/fzf.vim'
Plug 'sjl/gundo.vim'
Plug 'vim-test/vim-test'

" Interface
Plug 'preservim/nerdtree'
Plug 'Xuyuanp/nerdtree-git-plugin'
Plug 'vim-airline/vim-airline'
Plug 'vim-airline/vim-airline-themes'

" Commands
Plug 'tpope/vim-commentary'
Plug 'tpope/vim-fugitive'
Plug 'tpope/vim-repeat'
Plug 'tpope/vim-surround'
Plug 'junegunn/vim-easy-align'

" Other
Plug 'tpope/vim-sensible'
Plug 'sjl/vitality.vim'

" NOTE: plug#end() automatically executes `filetype plugin indent on` and
" `syntax enable`.
call plug#end()

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
" Gruvbox Configuration
"
" Gruvbox is a popular retro-inspired colorscheme for Vim and other text
" editors. It's designed with warm, earthy tones that are easy on the eyes for
" long coding sessions.
"
" NOTE: The Gruvbox configuration must come before custom color
" configurations.
"
" See: https://github.com/morhetz/gruvbox
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

" Set background (light vs. dark mode).
set background=dark

" Set colorscheme (prepended with `silent!` to ignore errors if not yet
" installed).
silent! colorscheme gruvbox

" Use 24-bit color (true-color).
if (has('termguicolors'))
  set termguicolors
endif

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
" Basic Configuration
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

" Set character encoding.
set encoding=utf-8
scriptencoding utf-8

" Set split behavior.
set splitbelow  " Horizontal split (:split, :sp) below current pane.
set splitright  " Vertical split (:vsplit, :vs) right of current pane.

" Show line numbers.
set number

" Configure indentation settings.
set tabstop=2     " Width of a tab character (in spaces).
set shiftwidth=2  " Indent width (in spaces).
set expandtab     " Use spaces instead of tabs.

" Configure status line.
set laststatus=2  " Always show the status line.
set noshowmode    " Removes duplicate mode message (use vim-airline instead).

" Configure automatic formatting.
"   r  Automatically insert the current comment leader after hitting <Enter>.
"   o  Automatically insert the current comment leader after hitting 'o' or 'O'.
"   c  Auto-wrap comments using 'textwidth'. Insert the current comment leader.
"   q  Allow formatting of comments with 'gq'.
"   n  When formatting text, recognize numbered lists.
"   1  Don't break a line after a one-letter word.
"   j  Remove a comment leader when joining lines.
set formatoptions=rocqn1j

" Set IncSearch color.
highlight IncSearch cterm=bold ctermfg=166 ctermbg=235 guifg=#d65d0e guibg=#282828

" Set Error color.
highlight Error cterm=bold ctermfg=167 ctermbg=235 guifg=#fb4934 guibg=#282828

" Set SignColumn color.
highlight SignColumn ctermbg=235 guibg=#282828

" Toggle 'set paste' with <F10>.
set pastetoggle=<F10>

" Set updatetime to 100 ms (default is 4000 ms). Recommended by several
" plugins.
set updatetime=100

" Show vertical column at 80th character.
set colorcolumn=80

" Start editing with all folds open.
set foldlevelstart=99

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
" Advanced Configuration
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

" Remap window selection (Ctrl + [hjkl]).
nnoremap <C-H> <C-W><C-H>
nnoremap <C-J> <C-W><C-J>
nnoremap <C-K> <C-W><C-K>
nnoremap <C-L> <C-W><C-L>

" Remap <Leader> key to <Space>.
nnoremap <space> <nop>
let g:mapleader = "\<Space>"

" Remap Ctrl + i (go to newer entry in jump list) to <Leader> + i.
nnoremap <Leader>i <C-I>

" Remap Ctrl + o (go to older entry in jump list) to <Leader> + o.
nnoremap <Leader>o <C-O>

" Remap <Leader>y/<Leader>p to copy/paste to the + register (system clipboard).
nnoremap <Leader>y "+y
vnoremap <Leader>y "+y
nnoremap <Leader>p "+p
vnoremap <Leader>p "+p

" Remap 'Q' to playback the recording put into the q register.
noremap Q @q

" Substitute all occurrences of the word under the cursor.
nnoremap <Leader>s :%s/\<<C-r><C-w>\>//g<Left><Left>

" Copy the relative path of the current buffer to the system clipboard.
command! CopyRelPath let @+ = expand('%')
nnoremap <Leader>cp :CopyRelPath<CR>

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

" Alphabetize selected text (normal, remove duplicates, reverse).
"   abc   Alphabetize selected text
"   abcu  Alphabetize and remove duplicates
"   abc!  Reverse alphabetize
vnoremap <Leader>abc  :sort<CR>
vnoremap <Leader>abcu :sort u<CR>
vnoremap <Leader>abc! :sort!<CR>

" Center search results after jumping.
"   n   Next search result
"   N   Previous search result
"   *   Search for word under cursor forward
"   #   Search for word under cursor backward
"   g*  Search for partial match forward
"   g#  Search for partial match backward
nnoremap n  nzz
nnoremap N  Nzz
nnoremap *  *zz
nnoremap #  #zz
nnoremap g* g*zz
nnoremap g# g#zz

" Configure spellchecking.
"   ]s  Next misspelled word
"   [s  Previous misspelled word
"   z=  Suggest corrections
"   zg  Add word to dictionary
"   zb  Remove word from dictionary
set spelllang=en_us
set spellfile=$HOME/.config/vim/spell/en.utf-8.add
nnoremap <Leader>sp :setlocal spell!<CR>

" Set spellcheck colors.
highlight SpellBad   cterm=underline ctermfg=167 ctermbg=235 gui=underline guifg=#fb4934 guibg=#282828 guisp=#fb4934
highlight SpellCap   cterm=underline ctermfg=109 ctermbg=235 gui=underline guifg=#83a598 guibg=#282828 guisp=#83a598
highlight SpellLocal cterm=underline ctermfg=108 ctermbg=235 gui=underline guifg=#8ec07c guibg=#282828 guisp=#8ec07c
highlight SpellRare  cterm=underline ctermfg=175 ctermbg=235 gui=underline guifg=#d3869b guibg=#282828 guisp=#d3869b

" Configure autocommands.
augroup vimrc
  autocmd!

  " Configure filetype-specific automatic formatting.
  "   t  Auto-wrap text at textwidth.
  autocmd FileType markdown,text,gitcommit setlocal formatoptions=trcqn1j

  " Configure filetype-specific spellchecking.
  autocmd FileType markdown,text,gitcommit setlocal spell

  " Automatically write all buffers on focus loss / buffer switch.
  autocmd FocusLost,BufLeave * silent! wa

  " Open packages installed via Homebrew in readonly, nomodifiable mode
  autocmd BufReadPre,BufNewFile /opt/homebrew/Cellar/* setlocal readonly nomodifiable

augroup END

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
" auto-pairs
"
" auto-pairs is a popular Vim plugin that automatically inserts or deletes
" brackets, parentheses, and quotes in pairs.
"
" See: https://github.com/jiangmiao/auto-pairs
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

" No further configuration.

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
" ALE Configuration
"
" ALE (Asynchronous Lint Engine) is a popular Vim plugin that provides
" real-time linting and fixing capabilities. ALE is particularly popular
" because it brings modern IDE-like features to Vim while maintaining the
" editor's philosophy of being fast and customizable.
"
" NOTE: Though ALE offers Language Server support for autocomplete,
" go-to-definition, and find references, this functionality is fulfilled by
" YouCompleteMe.
"
" See: https://github.com/dense-analysis/ale
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

" Disable all LSP integrations (use YouCompleteMe instead).
let g:ale_disable_lsp = 1

" Enable fix/lint on save.
let g:ale_fix_on_save = 1
let g:ale_lint_on_save = 1

" Only use linters explicitly set via g:ale_linters.
let g:ale_linters_explicit = 1

" Configure fixers and linters (Go, Python, JavaScript, TypeScript, Shell).
"
" Go:
"
"   goimports
"
"     Adds, removes, and sorts import lines. In addition to fixing imports,
"     goimports also formats code in the same style as gofmt (i.e., it can be
"     used as a replacement).
"
"     See: https://pkg.go.dev/golang.org/x/tools/cmd/goimports
"
"   golangci-lint
"
"     Go linters runner which integrates multiple linters. By default,
"     golangci-lint runs an essential subset of all available Go linters:
"     errcheck, gosimple, govet, ineffassign, staticcheck, unused. To enable
"     all linters, use the `--enable-all` flag.
"
"     See: https://golangci-lint.run
"
" Python:
"
"   ruff
"
"     Ruff is an ultra-fast Python linter, formatter, and code quality tool,
"     written in Rust. As of 2025, Ruff is the most popular linter and
"     formatter for Python.
"
"     NOTE: For the fixers, 'ruff' will run `ruff check --fix`, which will
"     attempt to apply fixes to resolve lint violations. `ruff_format` will
"     run `ruff format`, which simply formats the code.
"
"     NOTE: Ruff uses a global ruff.toml located at
"     $XDG_CONFIG_HOME/ruff/ruff.toml.
"
"   mypy
"
"     mypy is a static type checker for Python that analyzes code for
"     type-related errors without executing it. It's designed to catch type
"     mismatches, attribute errors, and other issues that would cause runtime
"     errors. As of 2025, mypy is the most popular static type checker for
"     Python.
"
" JavaScript:
"
"   eslint
"
"     ESLint is a popular static code analysis tool for JavaScript and
"     TypeScript that identifies and reports problems in your code. It's
"     designed to make code more consistent and avoid bugs. As of 2025, ESLint
"     is the most commonly used JavaScript and TypeScript linter.
"
"   prettier
"
"     Prettier is an opinionated code formatter that automatically formats
"     your code to ensure consistency across your entire codebase.  As of
"     2025, Prettier is by far the most popular code formatter for JavaScript,
"     TypeScript, and web development in general.
"
"     NOTE: Prettier uses a global .prettierrc located at
"     $XDG_CONFIG_HOME/prettier/.prettierrc.
"
" TypeScript:
"
"   tsc
"
"     tsc (TypeScript Compiler) is the official TypeScript compiler that
"     converts TypeScript code to JavaScript, but it also serves as a powerful
"     type checker. When used for linting/analysis, it focuses purely on
"     TypeScript's type system validation.
"
" Shell:
"
"   shfmt
"
"     shfmt is a shell script formatter that automatically formats shell
"     scripts (bash, POSIX sh, mksh) for consistency and readability. As of
"     2025, shfmt is the most popular tool for shell script formatting.
"
"   shellcheck
"
"     ShellCheck is a static analysis tool specifically designed for shell
"     scripts that identifies bugs, portability issues, and suspicious
"     constructs in bash, sh, and other shell scripts. It's considered
"     essential for shell script development. As of 2025, shellcheck is the
"     most popular tool for shell script linting.
let g:ale_fixers = {
\   '*': ['remove_trailing_lines', 'trim_whitespace'],
\   'go': ['goimports'],
\   'python': ['ruff', 'ruff_format'],
\   'javascript': ['eslint', 'prettier'],
\   'typescript': ['eslint', 'prettier'],
\   'sh': ['shfmt'],
\   'css': ['prettier'],
\   'scss': ['prettier'],
\   'html': ['prettier'],
\   'json': ['prettier'],
\   'yaml': ['prettier'],
\   'yml': ['prettier'],
\   'xml': ['xmllint'],
\   'dockerfile': ['hadolint'],
\   'terraform': ['terraform'],
\}

let g:ale_linters = {
\   'go': ['golangci-lint'],
\   'python': ['ruff', 'mypy'],
\   'javascript': ['eslint'],
\   'typescript': ['eslint', 'tsc'],
\   'sh': ['shellcheck'],
\   'markdown': ['cspell', 'vale'],
\   'yaml': ['yamllint'],
\   'dockerfile': ['hadolint'],
\   'terraform': ['terraform', 'tflint', 'tfsec'],
\}

let g:ale_linters_ignore = {
\   'markdown': ['cspell', 'vale'],
\   'text': ['cspell', 'vale'],
\   'javascript': ['cspell'],
\   'typescript': ['cspell'],
\}

" Configure mypy.
"
" See: https://mypy.readthedocs.io/en/stable/running_mypy.html#following-imports
" let g:ale_python_mypy_options = '--follow-imports=silent'

" Configure Ruff.
" Disable E501 (line too long).
" let g:ale_python_ruff_options = '--ignore=E501'

" Configure shfmt (see shfmt --help).
let g:ale_sh_shfmt_options = '-i 2 -ci'

" Configure message format.
let g:ale_echo_msg_info_str = 'I'
let g:ale_echo_msg_warning_str = 'W'
let g:ale_echo_msg_error_str = 'E'
" let g:ale_echo_msg_format = '[%linter%] %s [%severity%]'

" Set ALE sign colors.
highlight ALEInfoSign    ctermfg=109 ctermbg=235 guifg=#83a598 guibg=#282828
highlight ALEWarningSign ctermfg=214 ctermbg=235 guifg=#fabd2f guibg=#282828
highlight ALEErrorSign   ctermfg=167 ctermbg=235 guifg=#fb4934 guibg=#282828

" Do not open a window (location list) if there are no errors or warnings.
let g:ale_open_list = 1

" Do not show errors or warnings with virtual-text (i.e., inline text).
let g:ale_virtualtext_cursor = 'disabled'

" Navigate between errors.
nnoremap <silent> [e <Plug>(ale_previous_wrap)
nnoremap <silent> ]e <Plug>(ale_next_wrap)

" Show error details in preview window.
nnoremap <silent> <Leader>ad <Plug>(ale_detail)

" Only lint on enter and save.
"   - Do not lint on text change.
"   - Do not lint on insert leave.
" This configuration enables better performance and fewer distractions.
let g:ale_lint_on_text_changed = 'never'
let g:ale_lint_on_insert_leave = 0

" ALE commands.
nnoremap <silent> <Leader>af :ALEFix<CR>
nnoremap <silent> <Leader>ai :ALEInfo<CR>
nnoremap <silent> <Leader>ar :ALEReset<CR>
nnoremap <silent> <Leader>at :ALEToggle<CR>

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
" vim-go Configuration
"
" vim-go is a popular Vim plugin that provides comprehensive Go development
" support within Vim. It's designed to make Vim feel like a full-featured IDE
" for Go programming.
"
" NOTE: After installation, run:
"
"   :GoInstallBinaries
"
" See: https://github.com/fatih/vim-go
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

" Disable automatic linting (use ALE instead).
let g:go_fmt_autosave = 0
let g:go_imports_autosave = 0
let g:go_metalinter_autosave = 0
let g:go_metalinter_autosave_enabled = []
let g:go_metalinter_enabled = []

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
" Tabular Configuration
"
" Tabular is a popular Vim plugin for text alignment and formatting. It's
" designed to help you align text in columns, making it easier to create
" well-formatted tables, code, and other structured text.
"
" See: https://github.com/godlygeek/tabular
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

" In visual mode, the alignment would apply to the selected lines. In normal
" mode Tabular attempts to guess the range.
if exists(':Tabularize')
  " Manual alignment mappings for pipe characters (e.g., Markdown tables).
  nnoremap <silent> <Leader><Bar> :Tabularize /<Bar><CR>
  vnoremap <silent> <Leader><Bar> :Tabularize /<Bar><CR>
endif

" Auto-align on pipe insert (convenient for real-time table editing).
inoremap <silent> <Bar> <Bar><Esc>:call <SID>align()<CR>a

" Function: s:align()
" Automatically aligns table columns when inserting pipe characters.
"
" This function detects when a pipe character is inserted in a table-like
" context and automatically aligns the columns using Tabularize. It preserves
" the cursor position relative to the table structure after alignment.
"
" Courtesy of Tim Pope (https://gist.github.com/tpope/287147).
"
" Args: None
" Returns: None
function! s:align()
  let p = '^\s*|\s.*\s|\s*$'
  if exists(':Tabularize') && getline('.') =~# '^\s*|' && (getline(line('.')-1) =~# p || getline(line('.')+1) =~# p)
    let column = strlen(substitute(getline('.')[0:col('.')],'[^|]','','g'))
    let position = strlen(matchstr(getline('.')[0:col('.')],'.*|\s*\zs.*'))
    Tabularize/|/l1
    normal! 0
    call search(repeat('[^|]*|',column).'\s\{-\}'.repeat('.',position),'ce',line('.'))
  endif
endfunction

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
" vim-markdown Configuration
"
" vim-markdown is a Vim plugin that enhances Markdown editing by adding
" features that are not available in Vim by default.
"
" See: https://github.com/preservim/vim-markdown
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

" Enable YAML front matter highlighting.
let g:vim_markdown_frontmatter = 1

" Enable TOML front matter.
let g:vim_markdown_toml_frontmatter = 1

" Enable JSON front matter.
let g:vim_markdown_json_frontmatter = 1

" Enable math syntax highlighting.
let g:vim_markdown_math = 1

" Show table of contents.
nnoremap <silent> <Leader>toc :Toc<CR>

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
" vim-polyglot Configuration
"
" vim-polyglot is a language pack plugin for Vim and Neovim that bundles
" syntax highlighting, indentation, and filetype detection for hundreds of
" programming and markup languages—all in one plugin.
"
" See: https://github.com/sheerun/vim-polyglot
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

" No further configuration.

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
" YouCompleteMe Configuration
"
" YouCompleteMe (YCM) is a popular code completion engine for Vim. It provides
" fast, intelligent autocompletion for multiple programming languages.
"
" NOTE: After installation, run:
"
"   python ./install.py --all
"
" If using a version of Python installed via pyenv, the '--enable-framework'
" option is required:
"
"   PYTHON_CONFIGURE_OPTS="--enable-shared" pyenv install <version>
"
" See: https://github.com/ycm-core/YouCompleteMe
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

" Disable diagnostic display (errors and warnings) (use ALE instead).
let g:ycm_show_diagnostics_ui = 0

" Disable documentation popup.
let g:ycm_auto_hover = ''

" Enable semantic highlighting.
" Semantic highlighting colors buffer text according to the underlying semantic
" type of the symbol, rather than classic regex-based syntax highlighting.
let g:ycm_enable_semantic_highlighting = 1

" Remap YCM completion to Ctrl + j instead of Ctrl + Space.
" The 'ycm_key_invoke_completion' option controls the key mapping used to
" invoke the completion menu for semantic completion. This key mapping can be
" used to trigger semantic completion anywhere, which can be useful when
" searching for top-level functions and classes in the current file.
" NOTE: Ctrl + Space opens Alfred.
let g:ycm_key_invoke_completion = '<C-j>'

" Defines the max size (in Kb) for a file to be considered for completion.
let g:ycm_disable_for_files_larger_than_kb = 512

" Close preview window after completion is accepted.
let g:ycm_autoclose_preview_window_after_completion = 1

" Close completion menu with Ctrl + y or Enter.
let g:ycm_key_list_stop_completion = ['<C-y>', '<CR>']

" YCM commands.
"
" NOTE: The GoTo command tries to perform the *most sensible* GoTo operation
" it can.  Currently, this means that it tries to look up the symbol under the
" cursor and jumps to its definition if possible. If the definition is not
" accessible from the current translation unit, it jumps to the symbol's
" declaration.
nnoremap <silent> <Leader>g  :YcmCompleter GoTo<CR>
nnoremap <silent> <Leader>gs :split \| :YcmCompleter GoTo<CR>
nnoremap <silent> <Leader>gv :vsplit \| :YcmCompleter GoTo<CR>
nnoremap <silent> <Leader>gd <Plug>(YCMGoToDefinition)
nnoremap <silent> <Leader>gi <Plug>(YCMGoToImplementation)
nnoremap <silent> <Leader>gr <Plug>(YCMGoToReferences)
nnoremap <silent> <Leader>fd <Plug>(YCMFindSymbolInDocument)
nnoremap <silent> <Leader>fs <Plug>(YCMFindSymbolInWorkspace)
nnoremap <silent> <Leader>yd <Plug>(YCMGetDoc)
nnoremap <silent> <Leader>yt <Plug>(YCMGetType)
nnoremap <silent> <Leader>rn <Plug>(YCMRefactorRename)
nnoremap <silent> <Leader>ych <Plug>(YCMCallHierarchy)
nnoremap <silent> <Leader>yth <Plug>(YCMTypeHierarchy)
nnoremap <silent> K <Plug>(YCMGetDoc)

" Function: BuildYCM(info)
" Post-update hook for YouCompleteMe plugin installation.
"
" This function is called automatically by vim-plug when YouCompleteMe is
" installed or updated. It runs the YCM installation script to compile the
" necessary components for code completion functionality.
"
" A post-update hook is executed inside the directory of the plugin and only
" run when the repository has changed, but you can force it to run
" unconditionally with the bang-versions of the commands: PlugInstall! and
" PlugUpdate!.
"
" See: https://github.com/junegunn/vim-plug#post-update-hooks
"
" Args:
"   info (dict): Dictionary containing plugin information:
"                - name: name of the plugin
"                - status: 'installed', 'updated', or 'unchanged'
"                - force: set on PlugInstall! or PlugUpdate!
" Returns: None
function! BuildYCM(info)
  if a:info.status == 'installed' || a:info.force
    !./install.py --all
  endif
endfunction

" Toggle YCM for the current buffer.
nnoremap <silent> <Leader>ytg :call ToggleYcm()<CR>

" Function: ToggleYcm()
" Sets b:ycm_largefile directly, which has the effect of enabling or disabling
" YCM.
"
"   let threshold = g:ycm_disable_for_files_larger_than_kb * 1024
"   let b:ycm_largefile =
"         \ threshold > 0 && getfsize( expand( a:buffer ) ) > threshold
"
" See: https://github.com/ycm-core/YouCompleteMe/blob/master/autoload/youcompleteme.vim
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

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
" vim-gitgutter Configuration
"
" vim-gitgutter is a popular Vim plugin that visually integrates Git diff
" information with the buffer's gutter (i.e., the sign column to the left of
" the line numbers).
"
" Mappings:
"
"   ]c          Jump to next hunk
"   [c          Jump to previous hunk
"   <Leader>hp  Preview hunk
"   <Leader>hs  Stage hunk
"   <Leader>hu  Undo  hunk
"
" See: https://github.com/airblade/vim-gitgutter
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

" Set vim-gitgutter sign colors.
highlight GitGutterAdd          ctermfg=142 ctermbg=235 guifg=#b8bb26 guibg=#282828
highlight GitGutterChange       ctermfg=214 ctermbg=235 guifg=#fabd2f guibg=#282828
highlight GitGutterChangeDelete ctermfg=214 ctermbg=235 guifg=#fabd2f guibg=#282828
highlight GitGutterDelete       ctermfg=167 ctermbg=235 guifg=#fb4934 guibg=#282828

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
" NERDTree
"
" NERDTree is a popular file system explorer plugin for the Vim text editor.
" It provides a tree-style navigation panel that displays your project's
" directory structure in a sidebar, making it easier to browse and manage
" files without leaving Vim.
"
" See: https://github.com/preservim/nerdtree
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

" Show hidden files by default.
let g:NERDTreeShowHidden = 1

" Ignore specific files.
let g:NERDTreeIgnore=[
      \ '\.git$[[dir]]',
      \ '\.mypy_cache$[[dir]]',
      \ '\.pytest_cache$[[dir]]',
      \ '__pycache__$[[dir]]',
      \ '\.DS_Store$[[file]]',
      \ '\.pyc$[[file]]',
      \ '\.swo$[[file]]',
      \ '\.swp$[[file]]',
      \ '\~$[[file]]'
      \ ]

" Do not show 'Bookmarks' and 'Press ? for help' text.
let g:NERDTreeMinimalUI = 1

" Set window width.
let g:NERDTreeWinSize = 35

" Toggle NERDTree (if closed, open it; if open, close it).
nnoremap <C-n> :NERDTreeToggle<CR>

" Find the file for the active buffer in the NERDTree window.
nnoremap <C-f> :NERDTreeFind<CR>

" Use case-sensitive sort of nodes.
let g:NERDTreeCaseSensitiveSort = 1

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
" nerdtree-git-plugin
"
" nerdtree-git-plugin is an extension for NERDTree that shows Git status flags
" for files and directories directly in the file tree.
"
" See: https://github.com/Xuyuanp/nerdtree-git-plugin
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

" No further configuration.

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
" vim-airline Configuration
"
" vim-airline is a lightweight status/tabline plugin for Vim that enhances the
" appearance and functionality of the default statusline.
"
" See: https://github.com/vim-airline/vim-airline
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

" Enable Powerline fonts.
let g:airline_powerline_fonts = 1

" Disable ALE integration.
let g:airline#extensions#ale#enabled = 0

" Disable detection of whitespace errors.
let g:airline#extensions#whitespace#enabled = 0

" Enable branch information (requires vim-fugitive).
let g:airline#extensions#branch#enabled = 1

" Enable hunk information (requires vim-gitgutter).
let g:airline#extensions#hunks#enabled = 1

" Enable NERDTree integration. See NERDTreeStatusline.
let g:airline#extensions#nerdtree_statusline = 1

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
" vim-airline-themes Configuration
"
" vim-airline-themes is a companion plugin to vim-airline that provides a
" large collection of predefined color themes specifically for the airline
" statusline.
"
" See: https://github.com/vim-airline/vim-airline-themes
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

" Use Gruvbox theme.
let g:airline_theme = 'gruvbox'

" Patch Gruvbox theme.
let g:airline_theme_patch_func = 'AirlineThemePatch'
function! AirlineThemePatch(palette)
  let a:palette.normal.airline_a = ['#282828', '#7c6f64', 235, 243]
  let a:palette.normal.airline_z = ['#282828', '#7c6f64', 235, 243]
endfunction

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
" fzf Configuration
"
" fzf is a general-purpose command-line fuzzy finder. It helps you quickly
" search and select items from a list using a fast, interactive fuzzy search
" interface. It's written in Go and works in any Unix-like terminal
" environment.
"
" NOTE: fzf is installed via Homebrew. The junegunn/fzf Vim plugin will pick
" up the fzf binary if it is available on the system path. If fzf is not found
" on $PATH, it will ask to download the latest binary.
"
" See:
"   - https://github.com/junegunn/fzf
"   - https://junegunn.github.io/fzf
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

" No further configuration.

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
" fzf.vim Configuration
"
" fzf.vim wraps fzf functionality into Vim commands and key mappings.
"
" See:
"   - https://github.com/junegunn/fzf.vim
"   - https://github.com/junegunn/fzf/blob/master/README-VIM.md
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

" Initialize configuration dictionary.
let g:fzf_vim = {}

" Set fzf layout.
let g:fzf_layout = {'down': '40%'}
let g:fzf_preview_window = ['right:50%:border-rounded', 'ctrl-/']

" Generate a quickfix list from selected lines.
function! s:generate_quickfix_list(lines)
  call setqflist(map(copy(a:lines), '{ "filename": v:val, "lnum": 1 }'))
  copen
  cc
endfunction

" Set key bindings for opening selected files.
let g:fzf_action = {
      \ 'ctrl-q': function('s:generate_quickfix_list'),
      \ 'ctrl-t': 'tab split',
      \ 'ctrl-s': 'split',
      \ 'ctrl-v': 'vsplit' }

" Search files with Ctrl - p.
map <C-P> :Files<CR>

" Set fzf colorscheme.
"
"   fg:      #ebdbb2 - fg1
"   fg+:     #d5c4a1 - fg2
"   bg:      #282828 - bg0
"   bg+:     #3c3836 - bg1
"   hl:      #fabd2f - yellow (bright)
"   hl+:     #d79921 - yellow (neutral)
"   info:    #665c54 - bg3
"   marker:  #83a598 - blue (bright)
"   prompt:  #665c54 - bg3
"   spinner: #665c54 - bg3
"   pointer: #83a598 - blue (bright)
"   header:  #665c54 - bg3
"   border:  #3c3836 - bg1
"   label:   #665c54 - bg3
"   query:   #ebdbb2 - fg1
"
" See:
"   - https://github.com/junegunn/fzf/wiki/Color-schemes
"   - https://vitormv.github.io/fzf-themes
let g:fzf_colors = {
      \ 'fg':         ['fg', 'GruvboxFg1'],
      \ 'fg+':        ['fg', 'CursorLine', 'CursorColumn', 'GruvboxFg2'],
      \ 'bg':         ['bg', 'GruvboxBg0'],
      \ 'bg+':        ['bg', 'CursorLine', 'CursorColumn'],
      \ 'preview-fg': ['fg', 'GruvboxFg1'],
      \ 'preview-bg': ['bg', 'GruvboxBg0'],
      \ 'hl':         ['fg', 'GruvboxYellow'],
      \ 'hl+':        ['fg', 'GruvboxYellowBold'],
      \ 'info':       ['fg', 'GruvboxBg3'],
      \ 'marker':     ['fg', 'GruvboxBlue'],
      \ 'prompt':     ['fg', 'GruvboxBg3'],
      \ 'spinner':    ['fg', 'GruvboxBg3'],
      \ 'pointer':    ['fg', 'GruvboxBlue'],
      \ 'header':     ['fg', 'GruvboxBg3'],
      \ 'border':     ['fg', 'GruvboxBg1'],
      \ 'gutter':     ['fg', 'GruvboxBg1'],
      \ 'label':      ['fg', 'GruvboxBg3'],
      \ 'query':      ['fg', 'GruvboxFg1'],
      \ }

" Hide statusline when fzf starts in a terminal buffer.
"
" See: https://github.com/junegunn/fzf/blob/master/README-VIM.md#hide-statusline
autocmd! FileType fzf set laststatus=0 noshowmode noruler
  \| autocmd BufLeave <buffer> set laststatus=2 showmode ruler

" Do not open files in NERDTree buffer.
nnoremap <silent> <expr> <C-P> (expand('%') =~ 'NERD_tree' ? "\<c-w>\<c-w>" : '').":Files\<cr>"

" Set terminal colors.
"
" The terminal_ansi_colors array uses the standard ANSI color order:
"
"   let g:terminal_ansi_colors = [
"         \ 'color0',  'color1',  'color2',  'color3',
"         \ 'color4',  'color5',  'color6',  'color7',
"         \ 'color8',  'color9',  'color10', 'color11',
"         \ 'color12', 'color13', 'color14', 'color15'
"         \]
"
" which corresponds to:
"
"   let g:terminal_ansi_colors = [
"         \ 'black',        'red',           'green',        'yellow',
"         \ 'blue',         'purple',        'cyan',         'white',
"         \ 'bright_black', 'bright_red',    'bright_green', 'bright_yellow',
"         \ 'bright_blue',  'bright_purple', 'bright_aqua',  'bright_white'
"         \]
"
" See: https://github.com/junegunn/fzf/blob/master/README-VIM.md#fzf-inside-terminal-buffer
let g:terminal_ansi_colors = [
      \ '#282828', '#cc241d', '#98971a', '#d79921',
      \ '#458588', '#b16286', '#689d6a', '#a89984',
      \ '#928374', '#fb4934', '#b8bb26', '#fabd2f',
      \ '#83a598', '#d3869b', '#8ec07c', '#ebdbb2'
      \]
