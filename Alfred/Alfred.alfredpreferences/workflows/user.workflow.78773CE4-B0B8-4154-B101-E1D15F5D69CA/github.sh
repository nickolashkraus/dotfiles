#!/bin/bash
#
# Alfred Script Filter for the GitHub keywords:
#
#   github.sh repo <owner> <clone-dir> <query>  # <repo>[/<path>]
#   github.sh pr <owner> <clone-dir> <query>    # <repo> [number], <repo>#<number>
#
# The repo is a short name below, or the name, a prefix, the initials (ms for
# membership-service) or a substring of a repo cloned under <clone-dir>. Every
# match is listed, best first, and the query as typed comes last, so a repo
# that is not cloned still opens by its full name. Runs under macOS bash 3.2.

mode="$1"
owner="$2"
dir="$3"
query="${4:-}"
max_items=8

short_name() {
  [[ "${owner}" == Function-Health ]] || return 1
  case "$1" in
    sre) echo sre-infra-terraform ;;
    mjs) echo member-journey-services ;;
    mam) echo member-app-middleware ;;
    ts) echo transaction-service ;;
    memb | ms) echo membership-service ;;
    ppp) echo ppp-service ;;
    ent) echo enterprise-service ;;
    admin) echo admin-app-fe-next ;;
    fe) echo frontend-mono ;;
    agent-os) echo nickolashkraus/agent-os ;;
    *) return 1 ;;
  esac
}

# Clones under the directory that match, ranked exact, prefix, initials, then
# substring, and shorter names first within a rank.
cloned_matches() {
  ls -1p "${dir}" 2>/dev/null | awk -v q="$1" '
    /\/$/ {
      name = substr($0, 1, length($0) - 1)
      n = tolower(name)
      k = split(n, parts, /[-_.]/)
      initials = ""
      for (i = 1; i <= k; i++) initials = initials substr(parts[i], 1, 1)
      if (n == q) r = 1
      else if (index(n, q) == 1) r = 2
      else if (initials == q) r = 3
      else if (index(n, q) > 0) r = 4
      else next
      printf "%d\t%d\t%s\n", r, length(n), name
    }' | sort -t $'\t' -k1,1n -k2,2n -k3,3 | cut -f3
}

candidates=""
add_candidate() {
  case $'\n'"${candidates}" in *$'\n'"$1"$'\n'*) return ;; esac
  candidates+="$1"$'\n'
}

items=""
add_item() {
  [[ -n "${items}" ]] && items+=","
  items+=$(printf '{"title":"%s","subtitle":"%s","arg":"%s","autocomplete":"%s","valid":%s,"text":{"copy":"%s"}}' \
    "$1" "$2" "$2" "$3" "$4" "$2")
}

finish() {
  printf '{"items":[%s]}\n' "${items}"
  exit 0
}

usage() {
  case "${mode}" in
    pr) add_item "Open a pull request" "ghpr <repo> [number], e.g. ppp 616 or mam#4192" "" false ;;
    *) add_item "Open a ${owner} repository" "<repo>[/<path>], e.g. ms or ppp/actions" "" false ;;
  esac
  finish
}

if [[ "${mode}" == pr ]]; then
  query="${query//#/ }"
  read -r name number extra <<<"${query}"
  path=""
  [[ -n "${name}" ]] || usage
  [[ -z "${extra}" && ( -z "${number}" || "${number}" =~ ^[0-9]+$ ) ]] || usage
else
  read -r name extra <<<"${query}"
  if [[ -z "${name}" ]]; then
    add_item "Open ${owner}" "https://github.com/${owner}" "" true
    finish
  fi
  [[ -z "${extra}" ]] || usage
  path=""
  if [[ "${name}" == */* ]]; then
    path="/${name#*/}"
    name="${name%%/*}"
  fi
  [[ "${path}" =~ ^[A-Za-z0-9_./-]*$ ]] || usage
fi

if [[ "${mode}" == pr && "${name}" == */* ]]; then
  add_candidate "${name}"
else
  lower=$(tr '[:upper:]' '[:lower:]' <<<"${name}")
  short=$(short_name "${lower}") && add_candidate "${short}"
  while IFS= read -r repo; do
    add_candidate "${repo}"
  done < <(cloned_matches "${lower}" | head -n $((max_items - 1)))
  [[ -n "${short}" ]] || add_candidate "${name}"
fi

while IFS= read -r repo; do
  [[ -n "${repo}" ]] || continue
  [[ "${repo}" == */* ]] && full="${repo}" || full="${owner}/${repo}"
  [[ "${full}" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || continue
  [[ "${full}" == "${owner}/"* ]] && complete="${full#"${owner}"/}" || complete="${full}"
  url="https://github.com/${full}"
  if [[ "${mode}" != pr ]]; then
    add_item "${full}${path}" "${url}${path}" "${complete}${path}" true
  elif [[ -n "${number}" ]]; then
    add_item "${full}#${number}" "${url}/pull/${number}" "${complete} ${number}" true
  else
    add_item "${full} pull requests" "${url}/pulls" "${complete} " true
  fi
done <<<"${candidates}"

[[ -n "${items}" ]] || usage
finish
