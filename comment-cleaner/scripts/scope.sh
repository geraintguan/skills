#!/usr/bin/env sh
# Resolve the comment-cleaner scope and emit exactly the material to review.
#
# This encodes the skill's scope contract deterministically so the model never
# has to re-derive it (and never picks the wrong merge-base / diff range):
#   1. staged files exist        -> the staged diff
#   2. else, not on default branch -> this branch's commits vs the merge-base
#   3. else (on default branch)  -> every tracked file
#
# It prints a SCOPE: line, a BASE: line, then either a ---DIFF--- (with context
# so comments can be judged in situ) or a ---FILES--- list. Identifying which
# lines are comments is left to the model: only act on comments on added (+)
# lines for the diff scopes; on the default branch, every comment is in scope.
set -eu

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
    echo "ERROR: not inside a git work tree"
    exit 1
}

default_branch() {
    d=$(git symbolic-ref refs/remotes/origin/HEAD --short 2>/dev/null || true)
    if [ -n "$d" ]; then echo "$d"; return; fi
    for c in origin/main origin/master main master; do
        if git rev-parse --verify --quiet "$c" >/dev/null 2>&1; then
            echo "$c"; return
        fi
    done
    echo ""
}

if [ -n "$(git diff --cached --name-only)" ]; then
    echo "SCOPE: staged"
    echo "BASE: staged changes (git diff --cached)"
    echo "---DIFF---"
    git diff --cached --unified=3
    exit 0
fi

base=$(default_branch)
cur=$(git rev-parse --abbrev-ref HEAD)
base_short=${base##*/}
if [ -n "$base" ] && [ "$cur" != "$base_short" ]; then
    mb=$(git merge-base HEAD "$base" 2>/dev/null || true)
    if [ -n "$mb" ]; then
        echo "SCOPE: branch"
        echo "BASE: $base (commits ${mb} .. HEAD)"
        echo "---DIFF---"
        git diff --unified=3 "$mb" HEAD
        exit 0
    fi
fi

echo "SCOPE: all"
echo "BASE: entire tracked codebase (on default branch, nothing staged)"
echo "---FILES---"
git ls-files
