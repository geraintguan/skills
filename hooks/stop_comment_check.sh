#!/usr/bin/env sh
# Stop hook for the comment-cleaner plugin.
#
# Fires when Claude finishes a turn. If that turn produced code changes, it asks
# Claude — before it actually stops — to run the comment-cleaner skill over just
# those changes and strip the redundant comments.
#
# Two important safety properties:
#   * Loop-safe. When Claude continues *because of* this hook, the next Stop
#     carries stop_hook_active=true; we detect that and step aside, so running
#     the skill can't re-trigger us forever.
#   * Bounded. It hands the skill an explicit list of the changed files instead
#     of letting scope auto-detection run. On the default branch with nothing
#     staged the skill's own scope would be "the entire codebase" — that must
#     never fire automatically on every turn. Scoping to the touched files keeps
#     the auto-run proportional to what the task actually did.
#
# Fails open: any error or unmet condition exits 0, so the session is never
# blocked by this hook.

input=$(cat 2>/dev/null || true)

# --- loop guard -----------------------------------------------------------
case "$input" in
  *'"stop_hook_active":true'* | *'"stop_hook_active": true'*) exit 0 ;;
esac

# --- locate the project ---------------------------------------------------
dir=${CLAUDE_PROJECT_DIR:-$PWD}
cd "$dir" 2>/dev/null || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

# --- what changed in this task? ------------------------------------------
# Tracked edits vs HEAD (covers both staged and unstaged) plus brand-new files.
files=$( { git diff --name-only HEAD 2>/dev/null
           git ls-files --others --exclude-standard 2>/dev/null
         } | sort -u )

scope=""
if [ -n "$files" ]; then
  list=$(printf '%s' "$files" | tr '\n' ',' | sed 's/,/, /g; s/, $//')
  scope="the files you changed in this task: ${list}. Treat exactly these as the target and skip the skill's git scope auto-detection — do not touch any other files"
else
  # Clean working tree: maybe the work was committed on a feature branch.
  base=$(git symbolic-ref refs/remotes/origin/HEAD --short 2>/dev/null || true)
  if [ -z "$base" ]; then
    for c in origin/main origin/master main master; do
      git rev-parse --verify --quiet "$c" >/dev/null 2>&1 && { base=$c; break; }
    done
  fi
  cur=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)
  base_short=${base##*/}
  if [ -n "$base" ] && [ -n "$cur" ] && [ "$cur" != "$base_short" ] \
     && [ -n "$(git merge-base HEAD "$base" 2>/dev/null)" ] \
     && [ -n "$(git rev-list "$(git merge-base HEAD "$base")"..HEAD 2>/dev/null)" ]; then
    scope="the changes this branch ('${cur}') adds versus ${base}; the skill's scope auto-detection will target them correctly"
  fi
fi

# Nothing a task plausibly just changed -> let Claude stop normally.
[ -n "$scope" ] || exit 0

reason="A coding task just finished. Before you stop, use the comment-cleaner skill to review and remove redundant comments in ${scope}. Follow the skill's workflow: delete comments that only restate the code, refactor variable/function names to capture context where a name can replace a comment, and keep functional directives, doc comments, TODOs, and genuine 'why' comments. If there is nothing worth cleaning, say so in one line. Then stop."

# JSON-escape (backslash then double-quote) and emit the block decision.
esc=$(printf '%s' "$reason" | sed 's/\\/\\\\/g; s/"/\\"/g')
printf '{"decision":"block","reason":"%s"}\n' "$esc"
exit 0
