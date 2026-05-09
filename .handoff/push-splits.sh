#!/usr/bin/env bash
# Push the three split repos to GitHub via gh CLI (HTTPS).
# Run this on your LOCAL machine — NOT in the Claude sandbox.
#
# One-time setup (skip whichever steps you've already done):
#   1. Install gh: https://cli.github.com/  (macOS: `brew install gh`)
#   2. Log in:     gh auth login
#                  -> Choose: GitHub.com  |  HTTPS  |  Login with a web browser
#                  -> When asked, sign in as the account that owns the
#                     three target repos (alexanderrko).
#   3. Verify:     gh auth status
#                  -> Should print:  Logged in to github.com account alexanderrko
#   4. Wire git:   gh auth setup-git
#                  -> Configures git to use gh's token for HTTPS pushes.
#
# Run it:
#   cd into the folder containing the four files (this script + 3 .bundle files)
#   chmod +x push-splits.sh
#   ./push-splits.sh

set -euo pipefail

OWNER="alexanderrko"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKDIR="$(mktemp -d -t splits-XXXXXX)"

# --- preflight --------------------------------------------------------------
if ! command -v gh >/dev/null 2>&1; then
  echo "ERROR: 'gh' CLI not found. Install from https://cli.github.com/ then re-run." >&2
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "ERROR: not authenticated with gh. Run: gh auth login" >&2
  exit 1
fi

ACTIVE_ACCOUNT="$(gh api user --jq .login 2>/dev/null || echo '?')"
if [ "$ACTIVE_ACCOUNT" != "$OWNER" ]; then
  echo "WARNING: gh is logged in as '$ACTIVE_ACCOUNT', expected '$OWNER'." >&2
  echo "  If '$ACTIVE_ACCOUNT' has push access to $OWNER/* repos this may still work." >&2
  echo "  Otherwise: gh auth switch  (or  gh auth login --hostname github.com)" >&2
  read -r -p "Continue anyway? [y/N] " ans
  [ "$ans" = "y" ] || [ "$ans" = "Y" ] || exit 1
fi

# Make sure git uses gh's token for HTTPS pushes.
gh auth setup-git >/dev/null 2>&1 || true

echo "Working in $WORKDIR"

# --- per-repo push ----------------------------------------------------------
push_one() {
  local repo="$1" force_flag="${2:-}"
  local bundle="$SCRIPT_DIR/$repo.bundle"

  echo
  echo "=== $repo ==="
  if [ ! -f "$bundle" ]; then
    echo "  ERROR: bundle not found: $bundle" >&2
    exit 1
  fi

  git clone "$bundle" "$WORKDIR/$repo"
  (
    cd "$WORKDIR/$repo"
    git remote remove origin 2>/dev/null || true
    git remote add origin "https://github.com/$OWNER/$repo.git"
    git push -u origin main $force_flag
  )
}

push_one nsw-auction-tracker
push_one breathing-exercises
push_one portfolio-tracker  --force   # has a placeholder commit to overwrite

echo
echo "All three repos pushed."
echo "Working dir (safe to delete): $WORKDIR"
echo
echo "Optional cleanup of the handoff branch in AlexanderRKO/AlexanderRKO:"
echo "  git push origin --delete claude/handoff-split-bundles"
