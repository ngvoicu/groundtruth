#!/bin/bash
# Installs the daily discovery's launchd agent (docs/discovery.md). Never run it without the owner's OK: it copies
# harness/discover.py (with listed_schema.py and scan_secrets.py, which it uses) into $G/bin, writes
# ~/Library/LaunchAgents/dev.providers.groundtruth.discovery.plist and loads it (launchctl bootstrap); from then on
# $G/bin/discover.py runs every day at 22:30 on this Mac, reading the owner's Provimux. The agent runs that copy, never
# a checkout's file: to update it, install again from the checkout you want.
#
#   scripts/install-discovery.sh --owner-ok [--publish] [--client-home <dir>] [--print]
#   scripts/install-discovery.sh --uninstall --owner-ok
#
#   --owner-ok         required: says the owner agreed (nothing is written without it)
#   --publish          the agent passes --publish: it puts listed.json on GitHub's main through gh when it changed
#                      (else it writes $G/listed.json only)
#   --uninstall        removes the agent (with --owner-ok); $G/bin is left as it is
#   --client-home DIR  $G (default: $GROUNDTRUTH_CLIENT_HOME, else ~/groundtruth-clients): mode 700
#   --print            changes nothing, whatever else is given: prints what it would copy and the plist it would
#                      install (or, with --uninstall, what it would remove)
#   --target DIR       another folder than ~/Library/LaunchAgents, and no launchctl (the tests)
set -euo pipefail
LABEL=dev.providers.groundtruth.discovery
repo=$(cd "$(dirname "$0")/.." && pwd -P)
template="$repo/scripts/launchd/$LABEL.plist"
files="discover.py listed_schema.py scan_secrets.py"
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
  echo "removed $dest (the copy in \$G/bin is left as it is)"
  exit 0
fi
python=$(command -v python3)
case $home in /*) ;; *) echo "--client-home must be an absolute path" >&2; exit 2 ;; esac
[ -d "$home" ] || { echo "$home does not exist: create it first (mkdir -m 700)" >&2; exit 1; }
perm=$(stat -c %a "$home" 2>/dev/null || stat -f %Lp "$home")
[ "$perm" = 700 ] || { echo "$home is mode $perm, not 700: refused" >&2; exit 1; }
for v in "$home" "$python" "$PATH"; do
  case $v in *'&'*|*'<'*|*'>'*|*'|'*) echo "a path with &, <, > or | cannot go into the plist: $v" >&2; exit 1 ;; esac
done
if [ $publish -eq 1 ]; then flag=--publish; edit1="s|__ARG1__|--publish|"
else flag=''; edit1='/<string>__ARG1__<\/string>/d'; fi
plist=$(sed -e "$edit1" -e "s|__PYTHON__|$python|g" -e "s|__CLIENT_HOME__|$home|g" -e "s|__PATH__|$PATH|g" "$template")
source=$(git -C "$repo" rev-parse --short HEAD 2>/dev/null || echo "not a git checkout")
if [ $print -eq 1 ]; then
  echo "would copy harness/{${files// /,}} of $repo (commit $source) into $home/bin" >&2
  printf '%s\n' "$plist"
  exit 0
fi
bin="$home/bin"
mkdir -p "$bin"
chmod 700 "$bin"
for f in $files; do
  cp "$repo/harness/$f" "$bin/.$f.tmp"
  chmod 600 "$bin/.$f.tmp"
  mv "$bin/.$f.tmp" "$bin/$f"
done
echo "copied harness/{${files// /,}} (commit $source) into $bin"
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
