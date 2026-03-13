#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/resolve_pr_conflicts.sh <target-branch> [feature-branch] [--prefer ours|theirs]

Examples:
  scripts/resolve_pr_conflicts.sh main work
  scripts/resolve_pr_conflicts.sh main --prefer theirs

Notes:
- Requires a clean working tree.
- Default mode is interactive on conflict.
- --prefer theirs/ours will auto-resolve all conflicted files during rebase.
EOF
}

prefer_mode=""
positionals=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --prefer)
      if [[ $# -lt 2 ]]; then
        echo "Error: --prefer requires a value (ours|theirs)" >&2
        exit 1
      fi
      prefer_mode="$2"
      shift 2
      ;;
    *)
      positionals+=("$1")
      shift
      ;;
  esac
done

if [[ -n "$prefer_mode" && "$prefer_mode" != "ours" && "$prefer_mode" != "theirs" ]]; then
  echo "Error: --prefer must be 'ours' or 'theirs'" >&2
  exit 1
fi

target_branch="${positionals[0]:-main}"
feature_branch="${positionals[1]:-$(git rev-parse --abbrev-ref HEAD)}"

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

if [[ $rebase_code -ne 0 && -n "$prefer_mode" ]]; then
  echo "[5/7] Conflict detected. Auto-resolving with --prefer ${prefer_mode}"
  while true; do
    conflict_files=$(git diff --name-only --diff-filter=U || true)
    if [[ -z "$conflict_files" ]]; then
      break
    fi

    while IFS= read -r file; do
      [[ -z "$file" ]] && continue
      git checkout --"${prefer_mode}" -- "$file"
      git add "$file"
    done <<< "$conflict_files"

    set +e
    git rebase --continue
    continue_code=$?
    set -e

    if [[ $continue_code -eq 0 ]]; then
      break
    fi

    # If there are no conflict files, this likely needs manual edit or commit message edit.
    next_conflicts=$(git diff --name-only --diff-filter=U || true)
    if [[ -z "$next_conflicts" ]]; then
      break
    fi
  done

  set +e
  git rebase --continue >/dev/null 2>&1
  set -e

  if git rebase --show-current-patch >/dev/null 2>&1; then
    rebase_code=2
  else
    rebase_code=0
  fi
fi

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
