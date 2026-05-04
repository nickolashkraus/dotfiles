# Writing

This guide codifies the writing style used by Nickolas Kraus. Follow these
conventions when writing or editing blog posts, articles, and essays.

## Voice and Tone

- Write in active voice. Reserve passive voice for describing system behavior
  where the acting agent is the infrastructure itself.
- Be direct and confident. State assertions plainly without hedging or
  over-qualifying.
- Maintain a professional but approachable tone. Not stiff academic prose, not
  casual slang.
- Inject personality through dry humor, self-aware asides, and footnotes rather
  than through the main body text.
- Do not apologize for complexity. Present technical information
  matter-of-factly with the expectation that the reader can follow along.
- Vary register by content type: use precise, economical language for technical
  posts; allow richer, more literary vocabulary for personal essays and
  reviews.

## Person

- Use "I" freely for personal experience, methodology, decisions, and opinions.
- Use "we" when walking the reader through a shared exercise or describing team
  efforts.
- Use "you" and imperative mood for instructions ("Create the required
  directories", "Mount the root partition").
- Do not use "I think" or "in my opinion" as softeners. State opinions as
  convictions.

## Sentence Structure

- Keep sentences short to medium length (10-25 words on average).
- Favor declarative statements. Follow a short declarative sentence with
  a longer explanatory one for rhythm.
- Use rhetorical questions as structural transitions: "First, what is a FIT
  file?"
- Use semicolons to join related independent clauses when appropriate, but do
  not overuse them.

## Paragraphs

- Keep paragraphs short: 1-4 sentences for technical content, up to 5-6 for
  essays.
- Use single-sentence paragraphs for transitional or summary statements.
- Always use a single introductory sentence before a code block. Do not launch
  into a code block without context.

## Structure and Headers

- Use `##` (H2) as the primary structural divider, `###` for subsections,
  `####` for sub-subsections.
- Use descriptive, action-oriented headers, not clever or vague ones.
- Use the "Problem / Solution" structure for posts that solve a specific issue.
- Use numbered "Step N:" headers for tutorial walkthroughs.
- Use "## Overview" to open longer posts when appropriate.
- Use "## Conclusion" or "## Summary" sparingly and only in longer posts. Keep
  it to 1-3 sentences.
- Use Title Case for section headers.

## Openings

- Lead with personal context or a concrete statement, then state the article's
  purpose: "In the course of building an MCP server, I became somewhat of an
  expert on..."
- For tutorials, a direct declarative statement restating the purpose is
  acceptable: "This article details the steps for creating and hosting a static
  website on AWS."
- For opinion or narrative posts, open in medias res with a concrete statement
  or anecdote: "Today, my team fired an engineer who was obviously OE."
- Cross-reference previous work when building on a prior article: "In
  a previous article, I detailed the steps for..."
- Never open with a generic "In this article, we will..." without first
  providing personal context.

## Closings

- For tutorials, use the signature "You now have..." pattern: "You now have
  your own static website hosted on AWS!"
- For opinion posts, close with a reflective or philosophical statement.
- Point readers to the relevant code repository when applicable.
- Do not use formulaic sign-offs like "Thanks for reading" or "Let me know in
  the comments."
- It is acceptable to simply end when the content is complete, without a formal
  conclusion.

## Introducing Technical Concepts

- Name the thing, then define it in one to two sentences: "Hugo is a static
  site generator. The purpose of a static site generator is to render content
  into HTML files *before* the request for the content is made..."
- Expand acronyms on first use.
- Use blockquotes for official documentation excerpts, citing the source.
- Frame complex topics around a problem the reader likely faces, followed by
  the solution.
- When explaining multiple sub-components, define each individually before
  showing how they compose together.

## Code Examples

- Always precede a code block with a short introductory sentence ending in
  a colon: "Generate RSA key pair:"
- Place the filename as inline code on its own line before the code block when
  showing file contents:
  ```
  `template.yaml`
  ```
- Use fenced code blocks with language identifiers (`bash`, `python`, `yaml`,
  `hcl`, `json`, etc.).
- Use the `$` prompt prefix for shell commands that show expected output. Use
  bare commands for commands the reader should execute.
- Follow code with a **NOTE** in bold or a bulleted breakdown when further
  explanation is needed.
- Use "has the following form:" when introducing resource or schema
  definitions.

## Lists

- Use numbered lists for sequential steps and ordered procedures.
- Use bulleted lists for non-sequential items, features, or options.
- Introduce lists with a colon at the end of the preceding sentence: "The
  following are the characteristics of security group rules:"
- Keep lists short (3-6 items). Avoid deeply nested lists.

## Formatting Conventions

- Use `**NOTE**:` callouts for supplementary information, caveats, and tips.
- Use `**WARNING**:` for critical caveats.
- Use backticks for inline code, file names, commands, resource names, and
  configuration values.
- Use bold for labels and key terms, not for general emphasis.
- Use italics for emphasis on specific words, for introducing terms, and for
  book titles.
- Use footnotes for tangential commentary, retrospective observations, humor,
  and self-corrections. Footnotes are the pressure valve for personality.

## Punctuation

- Never use em dashes. Use commas, parentheses, or rewrite the sentence.
- Never use smart quotes. Use straight quotes only.
- Use colons to introduce code blocks, lists, and explanations.
- Use parenthetical asides for brief clarifications and acronym expansions:
  "(i.e., nickolaskraus.io)".
- Use exclamation marks sparingly, only in congratulatory closings ("Done!",
  "You now have...!").
- Use ellipsis sparingly.

## Markdown Conventions

- Use reference-style links (`[text][label]` with `[label]: URL` at the bottom
  of the file). Never use inline links.
- Hard-wrap lines at approximately 80 characters.
- Use fenced code blocks, never indented code blocks.

## Transitions

- Use functional, understated transitions: "First,", "Next,", "However,",
  "Additionally,", "Furthermore,", "In addition,".
- Use "This is where..." to pivot from problem to solution.
- Use "It should be noted that..." for important qualifications.
- Use "Simply" to signal ease: "Simply pass the exception..."
- Avoid decorative or flowery transitions.

## Analogies and Allusions

- Use extended analogies to clarify complex technical concepts, developing them
  fully rather than as throwaway comparisons.
- Cultural, literary, and historical allusions are welcome when they serve the
  point.
- Keep analogies out of purely reference-style posts.

## Content-Type Adaptation

- **Tutorials**: Numbered steps, **NOTE** callouts, code-heavy, personal
  narrative framing, "You now have..." closing.
- **Reference posts**: Impersonal, structured, heavy on tables and lists,
  minimal narrative.
- **Opinion posts**: Assertive, prescriptive, blunt, with clear
  recommendations. Personal experience as evidence.
- **Reviews**: Literary register, richer vocabulary, thematic structure.
- **Curated notes**: Organized distillation of another source, minimal original
  prose, heavy code examples.

## What to Avoid

- Filler introductions, unnecessary recaps, and artificial length.
- SEO padding or motivational preambles.
- Hedging language and excessive qualifiers.
- Deeply nested lists or dense walls of text.
- Generic sign-offs or calls to action.
- Exclamation marks outside of congratulatory closings.
