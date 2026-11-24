#!/bin/bash
# Installs the daily discovery's launchd agent (docs/discovery.md). Never run it without the owner's OK: it writes
# ~/Library/LaunchAgents/dev.providers.groundtruth.discovery.plist and loads it (launchctl bootstrap), and from then
# on harness/discover.py runs every day at 22:30 on this Mac, reading the owner's Provimux.
#
#   scripts/install-discovery.sh --owner-ok [--publish] [--client-home <dir>] [--print]
#   scripts/install-discovery.sh --uninstall --owner-ok
#
#   --owner-ok         required: says the owner agreed (nothing is written without it)
#   --publish          the agent passes --publish: it writes listed.json in $G/discovery-repo and pushes it to
#                      GitHub when it changed (else it writes $G/listed.json only); never in this checkout
#   --uninstall        removes the agent (with --owner-ok)
#   --client-home DIR  where the logs go, $G (default: $GROUNDTRUTH_CLIENT_HOME, else ~/groundtruth-clients)
#   --print            changes nothing, whatever else is given: prints the plist it would install (or, with
#                      --uninstall, what it would remove)
#   --target DIR       another folder than ~/Library/LaunchAgents, and no launchctl (the tests)
#
# The repository is the checkout this script lies in.
set -euo pipefail
LABEL=dev.providers.groundtruth.discovery
repo=$(cd "$(dirname "$0")/.." && pwd -P)
template="$repo/scripts/launchd/$LABEL.plist"
ok=0 publish=0 print=0 uninstall=0 target="" home="${GROUNDTRUTH_CLIENT_HOME:-$HOME/groundtruth-clients}"
while [ $# -gt 0 ]; do
  case $1 in
    --owner-ok) ok=1 ;;
    --publish) publish=1 ;;
    --client-home) home=$2; shift ;;
    --print) print=1 ;;
    --uninstall) uninstall=1 ;;
    --target) target=$2; shift ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done
load=1
if [ -n "$target" ]; then load=0; else target="$HOME/Library/LaunchAgents"; fi
dest="$target/$LABEL.plist"
if [ $print -eq 1 ] && [ $uninstall -eq 1 ]; then
  echo "would remove $dest (and launchctl bootout gui/$(id -u)/$LABEL); nothing changed"
  exit 0
fi
if [ $print -eq 0 ] && [ $ok -ne 1 ]; then
  echo "refused: the discovery agent is installed or removed only with the owner's OK (--owner-ok); nothing changed" >&2
  exit 1
fi
if [ $uninstall -eq 1 ]; then
  [ $load -eq 1 ] && launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "${dest:?}"
  echo "removed $dest"
  exit 0
fi
python=$(command -v python3)
case $home in /*) ;; *) echo "--client-home must be an absolute path" >&2; exit 2 ;; esac
[ -d "$home" ] || { echo "$home does not exist: create it first (mkdir -m 700)" >&2; exit 1; }
perm=$(stat -c %a "$home" 2>/dev/null || stat -f %Lp "$home")
[ "$perm" = 700 ] || { echo "$home is mode $perm, not 700: refused" >&2; exit 1; }
for v in "$repo" "$home" "$python" "$PATH"; do
  case $v in *'&'*|*'<'*|*'>'*|*'|'*) echo "a path with &, <, > or | cannot go into the plist: $v" >&2; exit 1 ;; esac
done
# With --publish: `discover.py --publish`; without: `discover.py --out $G/listed.json`, never this checkout's file.
if [ $publish -eq 1 ]; then flag=--publish; edit1="s|__ARG1__|--publish|"; edit2='/<string>__ARG2__<\/string>/d'
else flag=''; edit1="s|__ARG1__|--out|"; edit2="s|__ARG2__|$home/listed.json|"; fi
plist=$(sed -e "$edit1" -e "$edit2" -e "s|__PYTHON__|$python|g" -e "s|__REPO__|$repo|g" \
            -e "s|__CLIENT_HOME__|$home|g" -e "s|__PATH__|$PATH|g" "$template")
if [ $print -eq 1 ]; then printf '%s\n' "$plist"; exit 0; fi
mkdir -p "$target"
printf '%s\n' "$plist" > "$dest.tmp"
if command -v plutil >/dev/null; then plutil -lint "$dest.tmp" >/dev/null
else "$python" -c 'import plistlib, sys; plistlib.load(open(sys.argv[1], "rb"))' "$dest.tmp"; fi
mv "$dest.tmp" "$dest"
echo "wrote $dest (daily at 22:30${flag:+, $flag})"
if [ $load -eq 1 ]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$dest"
  echo "loaded: launchctl print gui/$(id -u)/$LABEL shows it"
fi
