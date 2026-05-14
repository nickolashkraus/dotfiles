# Typography

## Pre-flight checklist (apply before generating Markdown prose)

- No em dashes (`—`). Use commas, parentheses, semicolons, or rewrite.
- No smart quotes. Straight only.
- After a colon: capitalize if a sentence/clause follows; lowercase if a value
  or list-fragment follows.
- Bulleted/numbered list items use `**Element**: Description.` Never use ` - `
  or ` — ` as the lead-in separator.
- Wrap lines at <80 characters at the last word boundary.

## Rules

- Never use em dashes.
- Never use smart quotes, only straight quotes.
- Do not add periods to the end of bulleted list items by default. Add a period
  only when the item is a complete sentence or contains multiple sentences
  (where internal punctuation makes a terminal period necessary for clarity).
- Keep lines <80 characters for human readability. Break lines at the last word
  boundary before column 80, maximizing line length. Use the Vim `gq`
  formatting behavior.
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
- Capitalize the first word after a colon when it begins a complete sentence or
  independent clause.
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
