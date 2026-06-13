#!/bin/bash
# Run this after installing Xcode Command Line Tools:
#   xcode-select --install
#
# Then:
#   chmod +x connect-github.sh
#   ./connect-github.sh

set -euo pipefail

REPO_URL="https://github.com/maneeshism125-tech/24x7sherpa.git"
ROOT="$(cd "$(dirname "$0")" && pwd)"

cd "$ROOT"

if ! command -v git >/dev/null 2>&1; then
  echo "Git is not available. Install Xcode Command Line Tools first:"
  echo "  xcode-select --install"
  exit 1
fi

if [ ! -d .git ]; then
  git init
  git remote add origin "$REPO_URL"
  git fetch origin
  git checkout -B main
  git branch --set-upstream-to=origin/main main 2>/dev/null || true
  echo "Git initialized and connected to $REPO_URL"
else
  if git remote get-url origin >/dev/null 2>&1; then
    echo "Remote already set: $(git remote get-url origin)"
  else
    git remote add origin "$REPO_URL"
    echo "Added remote: $REPO_URL"
  fi
fi

echo ""
echo "Next steps:"
echo "  git pull origin main    # sync latest from GitHub"
echo "  git status              # check local changes"
echo "  git push origin main    # push commits (after git add/commit)"
