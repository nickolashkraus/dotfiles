# General

- Apply @rules/typography.md to every piece of generated text, regardless of
  destination: source code, comments, commit messages, PR descriptions, GitHub
  issues, Linear issues, Notion pages, Slack messages, blog posts, scratch
  notes, and chat responses to me. Run the pre-flight checklist at the top of
  `typography.md` before emitting any text, and re-scan the output for
  violations before sending or saving. The destination is never a reason to
  relax the rules, and "it's just chat" or "it's just a commit message" is not
  an exception. A typography violation is a defect. The only carve-out is
  reproducing existing content verbatim (quoted passages, file contents being
  edited in place, captured log output).
- Never reference or link to internal or local-only documents (e.g., scratch
  notes under `~/nickolashkraus/agent-os/`, files on disk that are not in
  a public repo, private working docs) from external content (GitHub PRs,
  Notion pages, Linear issues, Slack messages, blog posts, ConductorOne
  justifications, ticket descriptions). Readers cannot resolve the link, and
  the reference leaks internal context. This includes GitHub URLs into the
  `agent-os` repo (e.g., `github.com/nickolashkraus/agent-os/...`) since the
  repo is private. When the underlying detail is useful, inline a summary
  instead. Internal context belongs in memory or daily task files, not in
  external posts.
- Default to brief in chat responses. State results and decisions directly;
  skip preamble, recap, and trailing summaries. A simple question gets a direct
  answer, not headers and sections. When more detail is warranted, surface
  a one-line offer ("Want the full breakdown?") rather than emitting it
  preemptively. This rule applies to chat responses only, not to persistent
  artifacts (PR bodies, ADRs, Linear issues, Notion pages, commit messages)
  where @rules/writing.md density guidance governs.
