# Models

Opus is the floor and the default. New sessions start on the latest Opus
(`opus`), and so does every subagent, workflow and harness script. Sessions
moved off Fable on 2026-11-18 because it was using up my plan.

- **Below Opus**: Never use Sonnet or Haiku. Never pass them to `Agent`,
  a workflow, skill frontmatter or `claude --model`, and never write them into
  a script. Cost and speed are not reasons to drop below Opus. A harness check
  that needs to be faster lowers `--effort`, not the model.
- **Fable**: Only in a session I switch to it with `/model`. Never choose it
  for a subagent, workflow or script on your own. Say in one line why the
  work needs it and wait for my yes, then start the prompt or command with
  `# user-approved:` (or put `// user-approved:` in a workflow script).
- **Subagents**: Name `opus` on every `Agent` call and workflow, whatever the
  session runs on. A subagent with no model named inherits the session's
  model.
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
  named by `Agent`, a workflow or `claude --model`, and an `Agent` call that
  names no model. A workflow script that names no model is not caught.

`claude --setting-sources ""`, which `pr-body` uses, skips `settings.json`, so
those callers have to name `opus` themselves.

Claude Code's own background helpers are not covered: `availableModels` exempts
them, and they still use Haiku.
