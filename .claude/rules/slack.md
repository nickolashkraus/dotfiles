# Slack

- Follow @rules/typography.md for all Slack content.
- ALWAYS send messages using the `slack_send_message_draft` tool, never
  `slack_send_message`. The user reviews and approves drafts before they
  are sent.

## Tables

To render tabular data as a native Slack table, the clipboard must carry an
HTML `<table>` (the format Slack's paste-import recognizes). Plain-text TSV
pasted as text does NOT render as a table; Slack's TSV-to-table trick only
fires when the clipboard holds spreadsheet rich data (HTML), not plain text.

When the user asks to render a table in Slack, set their clipboard with an HTML
table plus a TSV plain-text fallback, then have them paste into the composer.
Use the macOS clipboard write below (AppKit if available, else `osascript` with
the `«class HTML»` type):

```python
html = (
    "<table>"
    "<tr><th>col1</th><th>col2</th></tr>"
    "<tr><td>a</td><td>b</td></tr>"
    "</table>"
)
tsv = "col1\tcol2\na\tb\n"

try:
    from AppKit import NSPasteboard
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    pb.setString_forType_(html, "public.html")
    pb.setString_forType_(tsv, "public.utf8-plain-text")
except Exception:
    import subprocess
    hexhtml = html.encode("utf-8").hex()
    script = 'set the clipboard to {«class HTML»:«data HTML%s», string:"%s"}' % (
        hexhtml,
        tsv.replace("\\", "\\\\").replace('"', '\\"'),
    )
    subprocess.run(["osascript", "-e", script], check=True)
```

- Strip Markdown formatting (e.g., `**bold**` becomes `bold`). Slack applies
  its own styling.
- The first row is the column headers (use `<th>`).
- Guaranteed fallback when HTML import fails: Wrap a monospace-aligned
  ASCII/box-drawing table in a triple-backtick code block. It renders correctly
  because Slack code blocks preserve alignment.
