# Typography

- Never use em dashes.
- Never use smart quotes, only straight quotes.
- Add a period to the end of bulleted lists.
- Keep lines &lt;80 characters for human readability. Use the Vim `gq`
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
  These characters break syntax highlighting in Vim.
- Markdown reference links should use `[text][label]`. Do not use the
  `[label][]` shorthand or bare `[label]` form, even when the text and label
  are the same.
- Use double space instead of `<br>` for newlines in Markdown.
