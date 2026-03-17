# Typography

- Never use em dashes.
- Never use smart quotes, only straight quotes.
- Add a period to the end of bulleted lists.
- Keep lines &lt;80 characters for human readability. Break lines at the last
  word boundary before column 80, maximizing line length. Use the Vim `gq`
  formatting behavior.
- For lists, use the format (when appropriate):

  ```markdown
  - **Element**: A short description
  ```

- When formatting Markdown tables, use the following format:

  | Column 1 | Column 2 | Column 3 |
  | -------- | -------- | -------- |
  | x        | y        | z        |

- For Markdown files, use HTML escape characters (&lt;, &gt;, etc.). Escape \$.
  These characters break syntax highlighting in Vim, except when inside
  backticks (`<br>`).
- Markdown reference links should use `[text][label]`. Do not use the
  `[label][]` shorthand or bare `[label]` form, even when the text and label
  are the same.
- Use double space instead of `<br>` for newlines in Markdown.
- Always put colons outside of bold text (ex: **Bold**:).
- For YAML strings, follow these conventions:
  - Use unquoted strings by default when the value contains no special
    characters.
  - Use double quotes when the value contains special characters that require
    escape sequences (e.g., `\n`, `\t`, `\\`).
  - Use single quotes when the value contains YAML-special characters (e.g.,
    `:`, `#`, `{`, `}`, `[`, `]`, `,`, `&`, `*`, `!`, `|`, `>`, `'`, `"`, `%`,
    `@`, `` ` ``) but no escape sequences are needed.
  - Never mix quoting styles within the same file. Pick one style for values
    that need quoting and apply it consistently.
  - Use literal block scalars (`|`) for multi-line strings that must preserve
    newlines.
  - Use folded block scalars (`>`) for multi-line strings that should be joined
    into a single line.
