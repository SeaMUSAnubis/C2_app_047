#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [ -z "$ROOT" ]; then
  echo "Not inside a git repo. Skip."
  exit 0
fi

cd "$ROOT"

BRANCH="$(git branch --show-current)"

if [ -z "$BRANCH" ]; then
  echo "Detached HEAD. Skip auto push."
  exit 1
fi

# Chặn tuyệt đối push vào branch chính
PROTECTED_BRANCHES=("main" "master" "prod" "production" "develop")

for protected in "${PROTECTED_BRANCHES[@]}"; do
  if [[ "$BRANCH" == "$protected" ]]; then
    echo "Blocked: auto commit/push is not allowed on protected branch: $BRANCH"
    echo "Create a feature branch first, for example:"
    echo "git checkout -b agent/auto-work"
    exit 1
  fi
done

git update-index -q --refresh

# Không có thay đổi thì bỏ qua
if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
  echo "No changes to commit."
  exit 0
fi

git add -A

if git diff --cached --quiet; then
  echo "Nothing staged."
  exit 0
fi

MSG="chore(agent): auto update $(date '+%Y-%m-%d %H:%M:%S')"

git commit -m "$MSG"

# Nếu branch chưa có upstream thì tự set
if git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
  git push
else
  git push -u origin "$BRANCH"
fi
