#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/resolve_pr_conflicts.sh <target-branch> [feature-branch]

Examples:
  scripts/resolve_pr_conflicts.sh main work
  scripts/resolve_pr_conflicts.sh main

Notes:
- Requires a clean working tree.
- If conflicts occur, resolve files then run `git rebase --continue`.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

# Helper to resolve PR conflicts against target branch.
target_branch="${1:-main}"
feature_branch="${2:-$(git rev-parse --abbrev-ref HEAD)}"

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "Error: not inside a git repository" >&2
  exit 1
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Error: working tree is not clean. Commit or stash changes first." >&2
  exit 4
fi

if ! git show-ref --verify --quiet "refs/heads/${feature_branch}"; then
  echo "Error: local branch '${feature_branch}' not found" >&2
  exit 1
fi

echo "[1/7] Fetching remote branches..."
if git remote | grep -q '^origin$'; then
  git fetch origin
else
  echo "Warning: no 'origin' remote configured; using local branches only."
fi

echo "[2/7] Checking out feature branch: ${feature_branch}"
git checkout "${feature_branch}"

echo "[3/7] Updating feature branch"
if git remote | grep -q '^origin$' && git show-ref --verify --quiet "refs/remotes/origin/${feature_branch}"; then
  git pull --rebase origin "${feature_branch}"
else
  echo "Skipping pull --rebase: remote feature branch not found"
fi

echo "[4/7] Rebasing onto target: ${target_branch}"
if git remote | grep -q '^origin$' && git show-ref --verify --quiet "refs/remotes/origin/${target_branch}"; then
  base_ref="origin/${target_branch}"
else
  if git show-ref --verify --quiet "refs/heads/${target_branch}"; then
    base_ref="${target_branch}"
  else
    echo "Error: target branch '${target_branch}' not found locally or on origin" >&2
    exit 1
  fi
fi

set +e
git rebase "${base_ref}"
rebase_code=$?
set -e

if [[ $rebase_code -ne 0 ]]; then
  echo "[5/7] Rebase stopped due to conflicts."
  echo "Resolve conflicts, then run:"
  echo "  git add <resolved-files>"
  echo "  git rebase --continue"
  echo "Or abort with:"
  echo "  git rebase --abort"

  conflict_files=$(git diff --name-only --diff-filter=U || true)
  if [[ -n "${conflict_files}" ]]; then
    echo "Conflicted files:"
    echo "${conflict_files}" | sed 's/^/  - /'
  fi

  marker_files=$(rg -l '^<<<<<<<|^=======$|^>>>>>>>' . || true)
  if [[ -n "${marker_files}" ]]; then
    echo "Files still containing conflict markers:"
    echo "${marker_files}" | sed 's/^/  - /'
  fi
  exit 2
fi

echo "[5/7] Rebase finished without conflicts."

echo "[6/7] Final safety check for conflict markers..."
if rg -l '^<<<<<<<|^=======$|^>>>>>>>' . >/tmp/conflict_markers.txt; then
  echo "Error: conflict markers found in files:"
  cat /tmp/conflict_markers.txt | sed 's/^/  - /'
  exit 3
fi

echo "[7/7] Done. Push updated branch with:"
if git remote | grep -q '^origin$'; then
  echo "  git push --force-with-lease origin ${feature_branch}"
else
  echo "  git push --force-with-lease <remote> ${feature_branch}"
fi
