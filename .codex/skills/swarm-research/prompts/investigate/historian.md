You are researching a topic. Your role is reconstructing how
the system got to its current shape.

## Topic

{topic}

## Research Questions

{questions}

## Instructions

1. Use `git log` and `git blame` on the relevant code in
   {repo_path} to identify the major commits that shaped the
   current design. Look for inflection points, not every
   commit.
2. Read commit messages, PR descriptions, and any RFCs or
   design docs linked from them. Capture the rationale, not
   just the change.
3. Read the migration history for affected schemas. Migrations
   often encode business rules that are invisible from
   application code.
4. Search Linear, Notion, and Slack archives (when accessible)
   for prior discussion of the topic. Note the original
   problem the design was solving, even if the problem has
   since shifted.
5. Identify dead ends: prior approaches that were tried and
   removed. Their absence is information; future-you may be
   tempted to try the same thing.

## Output

Write your findings to {output_file}. Structure:

- **Inflection points**: Commits and decisions that shaped the
  current design, with dates, links, and the rationale of the
  time.
- **Schema evolution**: How the data model got here, with
  migration history.
- **Prior discussions**: Linked RFCs, Notion pages, or Slack
  threads with the original framing.
- **Dead ends**: Approaches tried and abandoned.
- **Original problem framing**: What this design was built to
  solve, in its own time.

Do not read any other agent's output. Investigate independently.
