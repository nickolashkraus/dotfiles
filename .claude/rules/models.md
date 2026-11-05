# Models

Opus is the floor. The latest Opus (`opus`) is the default for every session,
subagent, workflow and harness script.

- **Below Opus**: Never use Sonnet or Haiku. Never pass them to `Agent`,
  a workflow, skill frontmatter or `claude --model`, and never write them into
  a script. Cost and speed are not reasons to drop below Opus. A harness check
  that needs to be faster lowers `--effort`, not the model.
- **Fable**: Reserved for special occasions when the bleeding edge is needed.
  Never choose it on your own. Say in one line why the work needs it and wait
  for my yes, then start the prompt or command with `# user-approved:` (or put
  `// user-approved:` in a workflow script).
- **Scope**: This governs how we work, not what we build. A product's own model
  choice follows that product's requirements.

## Enforcement

- **`availableModels`** (`settings.json`): Allows only `opus` and `fable`. Any
  other request, including a full model ID or a subagent's `model`, runs on
  Opus without an error.
- **`ANTHROPIC_MODEL`** (`settings.json`): Starts new sessions on `opus` over
  a default saved by `/model` and over the Function Health org default of
  Sonnet.
- **`hooks/model-policy.py`**: Blocks a below-Opus or unapproved Fable model
  named by `Agent`, a workflow or `claude --model`.

`claude --setting-sources ""`, which `pr-body` uses, skips `settings.json`, so
those callers have to name `opus` themselves.

Claude Code's own background helpers are not covered: `availableModels` exempts
them, and they still use Haiku.
