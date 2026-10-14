# Typography

## Pre-flight checklist (apply before generating Markdown prose)

- No em dashes (`—`). Use commas, parentheses, semicolons, or rewrite.
- No smart quotes. Straight only.
- Capitalize the first word after a colon when the colon ends a label or
  lead-in: List elements (`**Element**: Description`), bold callouts
  (`**NOTE**: ...`), line-initial link lead-ins (`[Link](url): Description`),
  and other line-initial labels. When a colon joins two clauses inside
  a flowing sentence, keep lowercase ("the entry was also stale: it
  declared..."). Non-alphabetic starts (paths like `~/dir`, code spans like
  `` `foo` ``, numbers like `5min`, URLs) are naturally exempt because there is
  no letter to capitalize. Conventional-commit subject lines
  (`fix(rules): flag x`) are exempt; the spec lowercases both the type and the
  description (see rules/git.md).
- Bulleted/numbered list items use `**Element**: Description.` Never use ` - `
  or ` — ` as the lead-in separator.
- Write "ID" in prose, never "id" or "Id". Code references in backticks keep
  their verbatim casing (`id`, `user_id`, `userId`).
- American spellings, not British. Watch `-ize` over `-ise`
  (canonicalize, normalize), `-or` over `-our` (behavior, color), `-ed` over
  `-led` (modeled, labeled, canceled), and `-er` over `-re` (center).
- Wrap lines at <80 characters at the last word boundary.

## Rules

- Never use em dashes.
- Never use smart quotes, only straight quotes.
- Use American English spellings in all prose. The common pairs: `-ize` and
  `-ization` over `-ise` and `-isation` (canonicalize, normalize, organize,
  recognize, prioritize), `-or` over `-our` (behavior, color, favor), a single
  `l` before a suffix (modeled, labeled, canceled, traveled, fulfill), `-er`
  over `-re` (center, meter, fiber), and `-se` over `-ce` for nouns (defense,
  license, practice). Prefer `toward` to `towards`, `among` to `amongst`,
  `while` to `whilst`, and `learned` to `learnt`.

  Three things are exempt, because changing them would be wrong rather than
  pedantic:

  - **Identifiers and literals keep their own spelling.** A column, field,
    enum member, function or env var named the British way stays that way in
    backticks and in code, and so does a third-party API field. Write "the
    `cancelled` column" rather than renaming it in prose.
  - **Quoted material is reproduced verbatim.** Documentation excerpts, log
    output, error messages, commit subjects being cited, and anything inside
    a blockquote.
  - **Proper nouns keep their spelling.** Company names, product names and
    titles.

  This applies wherever @rules/general.md already sends typography: source,
  comments, docstrings, commit messages, PR descriptions, Linear issues,
  Notion pages, Slack messages and chat. It does not license rewriting
  existing prose you were not otherwise editing.
- Always write "ID" (capitalized) in prose: "session ID", "the agent's ID".
  Never "id" or "Id". It is an abbreviation of "identifier", and lowercase
  "id" reads as the Freudian term. When referring to a literal field, column,
  or variable, use backticks with the verbatim casing (`id`, `user_id`,
  `session.id`, `userId`). The colon-capitalization rule does not force
  a backticked `id` to `Id`; code spans are exempt.
- Do not add periods to the end of bulleted list items by default. Add a period
  only when the item is a complete sentence or contains multiple sentences
  (where internal punctuation makes a terminal period necessary for clarity).
- Keep lines <80 characters for human readability. Break lines at the last word
  boundary before column 80, maximizing line length. Use the Vim `gq`
  formatting behavior. This rule applies to files in the repo: Markdown docs,
  code comments, commit messages. For text written to platforms that handle
  their own wrapping (Slack messages, GitHub PR/issue comments, Notion pages,
  emails), let lines run to natural length. Hard line breaks render poorly in
  those contexts.
- For lists, use the format (when appropriate):

  ```markdown
  - **Element**: A short description
  ```

- In bulleted or numbered lists, use a colon after the lead-in element, not
  a dash. For example:
  `` `GET /foo`: Does something ``
  not
  `` `GET /foo` - Does something ``

- When formatting Markdown tables, use the following format:

  | Column 1 | Column 2 | Column 3 |
  | -------- | -------- | -------- |
  | x        | y        | z        |

  Pad all columns to equal width with a 1-space buffer on each side. When
  modifying a table, always reformat the entire table to maintain even spacing.

- Use backticks for inline code, file names, commands, resource names, and
  configuration values (e.g., `python`, `app.py`, `GET /api/users`).
- Always use single backticks. Never use double backticks (``code``). This
  includes Python docstrings: do not switch to reStructuredText conventions
  inside `"""..."""`. The codebase reads as Markdown everywhere, including
  comments and docstrings.
- Markdown reference links should use `[text][label]`. Do not use the
  `[label][]` shorthand or bare `[label]` form, even when the text and label
  are the same.
- Use double space instead of `<br>` for newlines in Markdown.
- Capitalize environment names: Dev, Staging, Prod. Treat them as proper nouns.
- Always put colons outside of bold text (e.g., **Bold**:).
- For YAML strings, follow these conventions:
  - Use unquoted strings by default when the value contains no special
    characters.
  - Use double quotes when the value contains special characters or
    YAML-special characters (e.g., `:`, `#`, `{`, `}`, `[`, `]`, `,`, `&`, `*`,
    `!`, `|`, `>`, `'`, `"`, `%`, `@`, `` ` ``). This includes escape sequences
    (e.g., `\n`, `\t`, `\\`).
  - Use literal block scalars (`|`) for multi-line strings that must preserve
    newlines.
  - Use folded block scalars (`>`) for multi-line strings that should be joined
    into a single line.
- Always put periods outside double quotes unless the quote actually contains
  a period.
- Place footnote markers after all punctuation (e.g., `sentence.[^1]`, not
  `sentence[^1].`).
- Use a comma before "but" when it joins two independent clauses.
