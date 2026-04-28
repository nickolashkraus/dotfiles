---
name: home-cleanup
description: >
  Review and safely clean a macOS home directory. Use when the user asks to
  clean out $HOME, reclaim disk space, prune caches, or identify files and
  directories that are safe to delete. Always inspect first, present an exact
  delete list with sizes and rationale, and require explicit confirmation
  before deleting anything.
---

# Home Cleanup

## Workflow

1. Inspect before deleting. Start with top-level `ls -la "$HOME"` and `du -sh`
   for visible and dot entries.
2. Drill into large, likely-disposable locations before proposing anything:
   - **Package and tool caches**: `~/.npm`, `~/.cache`, `~/.pyenv/cache`,
     `~/.nvm/.cache`, `~/Library/Caches`.
   - **Application Support cache subdirectories**: Electron cache folders such
     as `Cache`, `Code Cache`, `GPUCache`, and `Service Worker/CacheStorage`
     inside `~/Library/Application Support`.
   - **Finder and shell artifacts**: `.DS_Store` files and `.zcompdump*` shell
     completion dumps.
3. Present a proposed delete list with exact absolute or home-relative paths,
   observed sizes, and brief rationale.
4. Wait for explicit user confirmation before deletion.
5. After deletion, verify remaining sizes and report anything that could not be
   removed.

Use `zsh -f -c 'setopt null_glob; ...'` for glob-heavy scans so missing
dotfiles or cache directories do not produce false errors.

## Default Safe Deletes

These are generally safe to propose when present and large:

- Package manager caches: npm `_cacache`, npm `_npx`, pip, Poetry, Homebrew, Go
  build cache, `node-gyp`, TypeScript, uv, pyenv cache, and nvm cache.
- Browser and application cache roots under `~/Library/Caches`.
- Electron application cache subdirectories, not whole `Application Support`
  folders.
- `.DS_Store` files and generated shell completion dump files.

## Do Not Delete By Default

Do not propose these unless the user explicitly asks and the risk is called
out:

- Credentials or access config: `~/.ssh`, `~/.aws`, `~/.kube`, `~/.gnupg`,
  keychains, and cloud CLI auth files.
- Source trees, project directories, `Archive`, or user documents.
- Browser profiles, application databases, cookies, local storage, IndexedDB,
  application preferences, and session state.
- `~/Library/Messages`, `~/Library/Mail`, `~/Library/Mobile Documents`,
  `~/Pictures`, Photos libraries, iCloud data, or application containers that
  may hold user data.
- Runtime and tool installations such as `~/.pyenv/versions`,
  `~/.nvm/versions`, `~/.rustup/toolchains`, and Claude VM bundles.

## Deletion Rules

- Use `rm -rf --` only after confirmation and quote every path.
- If a running application recreates or holds a cache directory, do one
  verification pass and leave small live remainders alone unless the user wants
  the application closed and retried.
- Never use destructive Git commands or broad home-directory globs for cleanup.
