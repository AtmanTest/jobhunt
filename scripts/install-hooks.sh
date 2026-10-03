#!/bin/bash
# Install pre-commit and pre-push hooks
# Run: bash scripts/install-hooks.sh

HOOKS_DIR="$(git rev-parse --show-toplevel)/.git/hooks"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cp "$SCRIPT_DIR/../.git/hooks/pre-commit" "$HOOKS_DIR/pre-commit" 2>/dev/null || true
cp "$SCRIPT_DIR/../.git/hooks/pre-push" "$HOOKS_DIR/pre-push" 2>/dev/null || true
chmod +x "$HOOKS_DIR/pre-commit" "$HOOKS_DIR/pre-push" 2>/dev/null || true

echo "Hooks installed."
