#!/bin/bash
# Installs the weekly Monday night's launchd agent (docs/weekly-night.md, "Once, staff with the owner's OK").
# Never run it without the owner's OK: it writes ~/Library/LaunchAgents/dev.providers.groundtruth.weekly-night.plist
# and loads it (launchctl bootstrap), and from then on the night runs every Monday at 23:00 on this Mac.
#
#   scripts/install-weekly-night.sh --owner-ok [--dry-run-nights] [--client-home <dir>] [--print]
#   scripts/install-weekly-night.sh --uninstall --owner-ok
#
#   --owner-ok         required: says the owner agreed (nothing is written without it)
#   --dry-run-nights   the agent passes --dry-run instead of --go (step G6, the dry-run Monday)
#   --client-home DIR  the night's folder, $G (default: $GROUNDTRUTH_CLIENT_HOME, else ~/groundtruth-clients)
#   --print            writes nothing: prints the plist it would install
#   --target DIR       another folder than ~/Library/LaunchAgents, and no launchctl (the tests)
#
# The repository is the checkout this script lies in. The wake is the owner's own step:
#   sudo pmset repeat wakeorpoweron M 22:55:00
set -euo pipefail
LABEL=dev.providers.groundtruth.weekly-night
repo=$(cd "$(dirname "$0")/.." && pwd -P)
template="$repo/scripts/launchd/$LABEL.plist"
ok=0 mode=--go print=0 uninstall=0 target="" home="${GROUNDTRUTH_CLIENT_HOME:-$HOME/groundtruth-clients}"
while [ $# -gt 0 ]; do
  case $1 in
    --owner-ok) ok=1 ;;
    --dry-run-nights) mode=--dry-run ;;
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
if [ $print -eq 0 ] && [ $ok -ne 1 ]; then
  echo "refused: the night's agent is installed only with the owner's OK (--owner-ok); nothing written" >&2
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
[ -d "$home" ] || { echo "$home does not exist: create it first (mkdir -m 700), as docs/weekly-night.md says" >&2; exit 1; }
perm=$(stat -f %Lp "$home" 2>/dev/null || stat -c %a "$home")
[ "$perm" = 700 ] || { echo "$home is mode $perm, not 700: refused" >&2; exit 1; }
for v in "$repo" "$home" "$python" "$PATH"; do
  case $v in *'&'*|*'<'*|*'>'*|*'|'*) echo "a path with &, <, > or | cannot go into the plist: $v" >&2; exit 1 ;; esac
done
plist=$(sed -e "s|__PYTHON__|$python|g" -e "s|__MODE__|$mode|g" -e "s|__REPO__|$repo|g" \
            -e "s|__CLIENT_HOME__|$home|g" -e "s|__PATH__|$PATH|g" "$template")
if [ $print -eq 1 ]; then printf '%s\n' "$plist"; exit 0; fi
mkdir -p "$target"
printf '%s\n' "$plist" > "$dest.tmp"
plutil -lint "$dest.tmp" >/dev/null
mv "$dest.tmp" "$dest"
echo "wrote $dest (the night: $mode, Mondays at 23:00)"
if [ $load -eq 1 ]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$dest"
  echo "loaded: launchctl print gui/$(id -u)/$LABEL shows it"
  echo "the wake, the owner's own step: sudo pmset repeat wakeorpoweron M 22:55:00"
fi
