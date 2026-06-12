#!/usr/bin/env bash
set -u

# Codex Stop hooks validate stdout as hook-control JSON. This script is
# side-effect-only, so keep stdout empty and send all diagnostics to stderr.
exec 1>&2

log() {
  printf '[auto-commit-push] %s\n' "$*"
}

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [ -z "$ROOT" ]; then
  log "Not inside a git repo. Skip."
  exit 0
fi

cd "$ROOT"

BRANCH="$(git branch --show-current)"

if [ -z "$BRANCH" ]; then
  log "Detached HEAD. Skip auto push."
  exit 0
fi

# Chặn tuyệt đối push vào branch chính
PROTECTED_BRANCHES=("main" "master" "prod" "production" "develop")

for protected in "${PROTECTED_BRANCHES[@]}"; do
  if [[ "$BRANCH" == "$protected" ]]; then
    log "Blocked: auto commit/push is not allowed on protected branch: $BRANCH"
    log "Create a feature branch first, for example: git checkout -b agent/auto-work"
    exit 0
  fi
done

if ! git update-index -q --refresh; then
  log "Unable to refresh git index. Skip auto push."
  exit 0
fi

# Không có thay đổi thì bỏ qua
if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
  log "No changes to commit."
  exit 0
fi

if ! git add -A; then
  log "git add failed. Skip auto push."
  exit 0
fi

if git diff --cached --quiet; then
  log "Nothing staged."
  exit 0
fi

MSG="chore(agent): auto update $(date '+%Y-%m-%d %H:%M:%S')"

if ! git commit -m "$MSG"; then
  log "git commit failed. Skip auto push."
  exit 0
fi

# Nếu branch chưa có upstream thì tự set
if git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
  if ! git push; then
    log "git push failed."
    exit 0
  fi
else
  if ! git push -u origin "$BRANCH"; then
    log "git push -u failed."
    exit 0
  fi
fi

log "Committed and pushed auto update on $BRANCH."
