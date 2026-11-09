"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
" nerdtree-git-plugin Override
"
" DESCRIPTION
"   Overrides gitstatus#getIndicator from nerdtree-git-plugin to add an
"   indicator for 'IntentToAdd', the status that
"   after/autoload/gitstatus/util.vim reports for a file added with
"   'git add -N'. The plugin's lookup fails on a key missing from its own
"   map, even when g:NERDTreeGitStatusIndicatorMapCustom defines it.
"
"   The default is a white four-pointed star (U+2727), a hollow version of
"   the Untracked star. Set 'IntentToAdd' in
"   g:NERDTreeGitStatusIndicatorMapCustom to change it.
"
"   Sourced by the explicit 'runtime! autoload/gitstatus.vim' in .vimrc, for
"   the same reason as the util.vim override.
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

if exists('g:loaded_nerdtree_git_status_after')
  finish
endif
if !exists('*gitstatus#getIndicator')
  finish
endif
let g:loaded_nerdtree_git_status_after = 1

let s:getIndicator = funcref('gitstatus#getIndicator')

function! gitstatus#getIndicator(status) abort
  if a:status ==# 'IntentToAdd'
    return get(get(g:, 'NERDTreeGitStatusIndicatorMapCustom', {}),
          \ 'IntentToAdd', nr2char(10023))
  endif
  return s:getIndicator(a:status)
endfunction
