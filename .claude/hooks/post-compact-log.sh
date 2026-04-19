#!/usr/bin/env bash
#
# DESCRIPTION
#   Append a concise compact summary to a daily log file.
#   Reads session metadata and compact_summary from stdin JSON, extracts key
#   sections, and writes a short entry.
#
# USAGE
#   post-compact-log.sh
#
# STDIN
#   JSON with session_id, cwd, compact_summary, etc.

for cmd in jq python3; do
  if ! [ -x "$(command -v ${cmd})" ]; then
    echo "ERROR: ${cmd} is not installed." >&2
    exit 1
  fi
done

log_dir="/Users/nickolas/nickolashkraus/agent-os/notes/daily/logs"

input=$(cat)

session_id=$(echo "${input}" | jq -r '.session_id // empty')
cwd=$(echo "${input}" | jq -r '.cwd // empty')
compact_summary=$(echo "${input}" | jq -r '.compact_summary // empty')

[ -n "${compact_summary}" ] || exit 0

summary=$(printf '%s\n' "${compact_summary}" | python3 -c '
import re, sys, textwrap

text = sys.stdin.read()

# Strip <analysis> block and <summary> tags.
text = re.sub(r"<analysis>.*?</analysis>", "", text, flags=re.DOTALL)
text = re.sub(r"</?summary>", "", text)
text = text.strip()

# Parse numbered sections (e.g., "1. Primary Request and Intent:").
sections = {}
current = None
for line in text.split("\n"):
    m = re.match(r"^\d+\.\s+(.+?):\s*$", line)
    if m:
        current = m.group(1).strip()
        sections[current] = []
    elif current is not None:
        sections[current].append(line)

# Join and strip leading indentation.
for key in sections:
    content = "\n".join(sections[key])
    content = re.sub(r"(?m)^   ", "", content)
    sections[key] = content.strip()

def first_sentences(text, n=2):
    """Return the first n sentences.

    Periods inside backticks are ignored so that inline code like
    `/review --staged. Re-stage if changes.` is not treated as
    a sentence boundary.
    """
    # Mask backtick-enclosed content to avoid splitting on
    # periods inside code spans.
    placeholder_map = {}
    counter = [0]

    def _mask(m):
        key = f"\x00CODE{counter[0]}\x00"
        placeholder_map[key] = m.group(0)
        counter[0] += 1
        return key

    masked = re.sub(r"`[^`]+`", _mask, text.strip())
    sentences = re.split(r"(?<=[.!?])\s+", masked)
    result = " ".join(sentences[:n]).strip()

    # Restore masked spans.
    for key, val in placeholder_map.items():
        result = result.replace(key, val)
    return result

def truncate_bullets(text, max_items=5):
    """Keep only the first max_items bullet points."""
    lines = text.strip().split("\n")
    kept = []
    count = 0
    for line in lines:
        if re.match(r"^\s*[-*]\s", line):
            count += 1
            if count > max_items:
                continue
        kept.append(line)
    return "\n".join(kept).strip()

def has_bullets(text):
    """Check whether text contains bullet list items."""
    return bool(re.search(r"(?m)^\s*[-*]\s", text))

def wrap_paragraph(text, width=79):
    """Wrap a paragraph to width."""
    return textwrap.fill(text, width=width)

def wrap_bullets(text, width=79):
    """Wrap each bullet line, indenting continuation."""
    out = []
    for line in text.split("\n"):
        m = re.match(r"^(\s*[-*]\s+)", line)
        if m:
            indent = " " * len(m.group(1))
            out.append(textwrap.fill(
                line, width=width, subsequent_indent=indent
            ))
        else:
            out.append(line)
    return "\n".join(out)

def format_section(label, text, max_sentences=3):
    """Format a section with label, preserving structure.

    If the text contains bullet points, they are kept as a list
    under the label. Otherwise, the first few sentences are
    extracted and wrapped as a paragraph.
    """
    if has_bullets(text):
        # Split into prose (before first bullet) and bullets.
        lines = text.split("\n")
        prose = []
        bullet_start = 0
        for i, line in enumerate(lines):
            if re.match(r"^\s*[-*]\s", line):
                bullet_start = i
                break
            prose.append(line)
        else:
            bullet_start = len(lines)

        prose_text = " ".join(prose).strip()
        bullets = "\n".join(lines[bullet_start:]).strip()
        bullets = wrap_bullets(truncate_bullets(bullets))

        if prose_text:
            header = wrap_paragraph(
                f"**{label}**: {first_sentences(prose_text, 2)}"
            )
            return f"{header}\n{bullets}"
        return f"**{label}**:\n{bullets}"

    return wrap_paragraph(
        f"**{label}**: {first_sentences(text, max_sentences)}"
    )

parts = []

intent = sections.get("Primary Request and Intent", "")
if intent:
    parts.append(format_section("Intent", intent))

work = sections.get("Current Work", "")
if work:
    parts.append(format_section("Work", work))

findings = sections.get(
    "Key Technical Concepts", sections.get("Key Decisions", "")
)
if findings:
    parts.append(format_section("Findings", findings))

pending = sections.get("Pending Tasks", "")
if pending:
    parts.append(format_section("Pending", pending))

if parts:
    print("\n\n".join(parts))
else:
    print(textwrap.fill(text[:500], width=79))
')

[ -n "${summary}" ] || exit 0

d=$(date +%Y-%m-%d)
t=$(date +%H:%M)
short_id=${session_id:0:8}
dir_name=$(basename "${cwd}")

mkdir -p "${log_dir}"
f="${log_dir}/${d}.md"
[ -f "${f}" ] || printf '# %s\n' "${d}" >"${f}"
printf '\n## %s | %s | %s\n\n%s\n' "${t}" "${dir_name}" "${short_id}" "${summary}" >>"${f}"
