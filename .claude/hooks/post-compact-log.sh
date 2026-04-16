#!/usr/bin/env bash
#
# DESCRIPTION
#   Append the compact summary to a daily log file.
#   The summary is read from stdin as JSON with a .summary field.
#
# USAGE
#   post-compact-log.sh
#
# ARGUMENTS
#   None
#
# OPTIONS
#   None
#
# EXAMPLES
#   None

# Colors
red='\033[0;31m'
reset='\033[0m'

if ! [ -x "$(command -v jq)" ]; then
  echo -e "${red}ERROR: jq is not installed.${reset}" >&2
  exit 1
fi

log_dir="/Users/nickolas/nickolashkraus/agent-os/notes/daily/logs"

summary=$(jq -r '.summary // empty')
[ -n "${summary}" ] || exit 0

d=$(date +%Y-%m-%d)
t=$(date +%H:%M)

mkdir -p "${log_dir}"
f="${log_dir}/${d}.md"
[ -f "${f}" ] || printf '# %s\n' "${d}" >"${f}"
printf '\n## %s\n\n%s\n' "${t}" "${summary}" >>"${f}"
