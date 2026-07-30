"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
" nerdtree-git-plugin Override
"
" DESCRIPTION
"   Overrides gitstatus#util#BuildGitStatusCommand from nerdtree-git-plugin
"   to honor the gitgutter diff base (see ToggleGitGutterDiffBase in .vimrc).
"   The plugin hard-codes 'git status', which only covers uncommitted
"   changes. When a base is set, the command is replaced with a pipeline that
"   reports every file changed since the base ('git diff --name-status') plus
"   untracked files, formatted as v1 porcelain.
"
"   The output must be NUL-separated, like 'git status -z'. The plugin's job
"   layer reads with out_mode 'nl', where Vim strips real newlines and
"   concatenates the lines with no separator; NUL bytes instead survive as
"   newlines in the resulting Vim string, which is what the parser splits on.
"
"   This lives in after/autoload (rather than .vimrc) because Vim raises
"   E746 when a function in the gitstatus#util# namespace is defined in
"   a script other than autoload/gitstatus/util.vim. The override is sourced
"   by the explicit 'runtime! autoload/gitstatus/util.vim' in .vimrc, which
"   sources all matches on 'runtimepath' in order: the plugin's copy first,
"   then this one.
"
" INSTALLATION
"   Symlink directory to $HOME/.vim/after:
"
"     ln -s .vim/after $HOME/.vim/after
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

" The guard also prevents a re-source from capturing the override itself in
" s:BuildGitStatusCommand, which would recurse.
if exists('g:loaded_nerdtree_git_status_util_after')
  finish
endif
if !exists('*gitstatus#util#BuildGitStatusCommand')
  finish
endif
let g:loaded_nerdtree_git_status_util_after = 1

" Handle on the plugin's builder for the no-base case. funcref() binds to the
" function itself, so the redefinition below does not affect it.
let s:BuildGitStatusCommand = funcref('gitstatus#util#BuildGitStatusCommand')

function! gitstatus#util#BuildGitStatusCommand(root, opts) abort
  let l:base = get(g:, 'gitgutter_diff_base', '')
  if empty(l:base)
    return s:BuildGitStatusCommand(a:root, a:opts)
  endif
  let l:git = get(a:opts, 'NERDTreeGitStatusGitBinPath', 'git')
        \ . ' -C ' . shellescape(a:root)
  let l:script = '{ ' . l:git . ' diff --name-status --no-renames -z '
        \ . shellescape(l:base)
        \ . ' | tr ''\0'' ''\n'''
        \ . ' | awk ''NR % 2 == 1 { s = $0; next }'
        \ . ' { printf(" %s %s\n", (s == "D") ? "D" : "M", $0) }'''
        \ . '; ' . l:git . ' status --porcelain -z --untracked-files='
        \ . get(a:opts, 'NERDTreeGitStatusUntrackedFilesMode', 'normal')
        \ . ' | tr ''\0'' ''\n'' | grep ''^??'''
        \ . '; } | tr ''\n'' ''\0'''
  return ['sh', '-c', l:script]
endfunction
