#!/bin/sh
# Install MindView git hooks into .git/hooks/
# Run once after `git clone`.

set -e
REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$REPO_ROOT"

if [ ! -d .git/hooks ]; then
  echo "❌ .git/hooks/ not found — are you running this from a clone?"
  exit 1
fi

for hook in scripts/git-hooks/*; do
  name=$(basename "$hook")
  cp "$hook" ".git/hooks/$name"
  chmod +x ".git/hooks/$name"
  echo "  installed: .git/hooks/$name"
done

echo ""
echo "✅ Git hooks installed."
echo "   Next commit will run scripts/verify-baseline.py automatically."
echo "   Override with:  git commit --no-verify  (and only if you really mean it)."
