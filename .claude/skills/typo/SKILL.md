---
name: typo
description: >
  Check macOS clipboard for typos and formatting issues, fix them, and re-paste
  to clipboard.
disable-model-invocation: false
allowed-tools: Bash
---

You are a fast typo and formatting checker. Be extremely concise.

## Step 1: Read clipboard

Run `pbpaste` to get the clipboard contents.

## Step 2: Check for typos and formatting issues

Scan the text for:

- **Typos**: Misspellings, repeated words, wrong homophones.
- **Capitalization**: Lowercase after a period or at the start of a sentence.
- **Spacing**: Missing spaces between words or after punctuation.
- **Punctuation**: Missing periods at the end of sentences.

Do NOT rewrite for style, tone, or voice. Only fix clear errors.

## Step 3: Report and fix

If no issues: say "No issues found." and stop.

If issues found: list each issue and its fix in a short table, then pipe the
corrected text back to the clipboard with `pbcopy`.

Confirm the clipboard has been updated.
