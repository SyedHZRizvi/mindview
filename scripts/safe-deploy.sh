#!/bin/sh
# MindView safe-deploy wrapper.
# Runs scripts/verify-baseline.py first; only invokes wrangler if it passes.
# Use this INSTEAD of calling `wrangler pages deploy .` directly.
#
# By default deploys to STAGING (--branch=staging → https://staging.mindview.pages.dev).
# To deploy to PRODUCTION (--branch=main → https://mindview.pages.dev), set
#   TARGET=production sh scripts/safe-deploy.sh
# This MUST only be done after the owner has reviewed staging.
#
# Override the baseline check (only if you must — and you should also update CLAUDE.md):
#   FORCE=1 sh scripts/safe-deploy.sh

set -e

# Find repo root
REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$REPO_ROOT"

echo "→ Verifying baseline…"
if ! python3 scripts/verify-baseline.py; then
  if [ "$FORCE" = "1" ]; then
    echo ""
    echo "⚠️  Baseline check failed but FORCE=1 — proceeding anyway."
    echo "   If this is a deliberate baseline change, update CLAUDE.md"
    echo "   and scripts/verify-baseline.py in the SAME commit."
  else
    echo ""
    echo "❌ Refusing to deploy — baseline drift detected."
    echo "   Fix the failures above, or re-run with FORCE=1 if you really"
    echo "   know what you're doing."
    exit 1
  fi
fi

echo ""
echo "→ Deploying to Cloudflare Pages…"
if [ -z "$CLOUDFLARE_API_TOKEN" ]; then
  echo "⚠️  CLOUDFLARE_API_TOKEN not set. Export it before running."
  exit 1
fi
if [ -z "$CLOUDFLARE_ACCOUNT_ID" ]; then
  echo "⚠️  CLOUDFLARE_ACCOUNT_ID not set. Export it before running."
  exit 1
fi

# Try project-local wrangler; fall back to global / npx
WRANGLER="$(command -v wrangler || true)"
if [ -z "$WRANGLER" ] && [ -x "/tmp/wrangler-install/node_modules/.bin/wrangler" ]; then
  WRANGLER="/tmp/wrangler-install/node_modules/.bin/wrangler"
fi
if [ -z "$WRANGLER" ]; then
  echo "❌ wrangler not found. Install with: npm install -g wrangler"
  exit 1
fi

# Default branch is staging. Owner sets TARGET=production for live deploy.
BRANCH="${BRANCH:-staging}"
if [ "$TARGET" = "production" ]; then
  BRANCH="main"
  echo "🚨  TARGET=production — deploying to live https://mindview.pages.dev/"
  echo "    (staging.mindview.pages.dev is the review URL; production should"
  echo "     only be deployed AFTER owner has reviewed staging)"
else
  echo "→ Deploying to STAGING (https://staging.mindview.pages.dev/)"
  echo "  (To deploy to production after review: TARGET=production sh scripts/safe-deploy.sh)"
fi

"$WRANGLER" pages deploy . \
  --project-name=mindview \
  --branch="$BRANCH" \
  --commit-dirty=true
