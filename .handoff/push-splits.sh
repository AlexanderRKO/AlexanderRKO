#!/usr/bin/env bash
# Push the three split repos to GitHub.
# Run this on your LOCAL machine (not in the Claude sandbox).
# Prereqs: git, gh CLI authenticated, or HTTPS/SSH credentials configured.
#
# Usage:
#   1. Download the three .bundle files from /tmp/splits-bundles/ in the sandbox:
#        - nsw-auction-tracker.bundle
#        - breathing-exercises.bundle
#        - portfolio-tracker.bundle
#   2. Place this script next to them.
#   3. chmod +x push-splits.sh && ./push-splits.sh

set -euo pipefail

OWNER="alexanderrko"
WORKDIR="$(mktemp -d -t splits-XXXXXX)"
echo "Working in $WORKDIR"

push_one() {
  local repo="$1" bundle="$2" force_flag="${3:-}"
  echo
  echo "=== $repo ==="
  git clone "$bundle" "$WORKDIR/$repo"
  cd "$WORKDIR/$repo"
  git remote remove origin 2>/dev/null || true
  git remote add origin "git@github.com:$OWNER/$repo.git"
  git push -u origin main $force_flag
  cd - >/dev/null
}

push_one nsw-auction-tracker  ./nsw-auction-tracker.bundle
push_one breathing-exercises  ./breathing-exercises.bundle
push_one portfolio-tracker    ./portfolio-tracker.bundle --force   # has placeholder commit to overwrite

echo
echo "All three repos pushed."
echo "You can delete $WORKDIR and the .bundle files now."
