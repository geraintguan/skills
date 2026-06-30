# comment-cleaner

A Claude Code plugin that removes low-value, redundant code comments — the kind
LLMs scatter everywhere (`# increment i`, `// loop over users`) — while keeping
the comments that actually carry information. When a comment held context that a
name could hold instead, it refactors the name and drops the comment; when the
context can't live in a name, it keeps the comment and tells you why.

It ships as:

- a **skill** (`/comment-cleaner:comment-cleaner`) you can invoke any time, and
- a **Stop hook** that runs the cleanup automatically when a coding task finishes.

## Install

This repo is its own plugin marketplace. From Claude Code:

```
/plugin marketplace add geraintguan/skills
/plugin install comment-cleaner@scalesignal-skills
```

(or point the marketplace at a local clone with `/plugin marketplace add /path/to/skills`.)

## What it does

For the comments in scope, each is sorted into one of four buckets:

| Bucket | Action |
| --- | --- |
| Restates the code (`# add one` over `i += 1`) | **removed** |
| Context a better name could hold (`d = 7  # days`) | **name refactored** (`retention_days = 7`), comment dropped |
| Functional directive / doc / TODO / legal / genuine "why" | **kept** |
| Useful context a name can't capture | **kept and reported** |

**Scope** when invoked manually, in order: staged changes → else the current
branch's commits vs. the default branch → else the whole tracked codebase.

## The Stop hook (automatic cleanup)

When a turn finishes, `hooks/stop_comment_check.sh` checks whether the task
changed any code and, if so, asks Claude to run the skill over **just those
changed files** before stopping. It is:

- **Bounded** — scoped to the files the task touched, so it never auto-expands to
  "the whole codebase" on a clean `main`.
- **Loop-safe** — it steps aside on the follow-up stop (`stop_hook_active`), so
  running the skill can't re-trigger it.
- **Fail-open** — any error or "nothing changed" just lets Claude stop normally.

### Turning the auto-run off

Don't want the automatic behavior but still want the skill? Either uninstall and
reinstall without the hook, or disable hooks for this plugin in `/plugin`, or
simply delete `hooks/hooks.json` from your local copy. The skill remains usable
on demand regardless.

## Layout

```
.claude-plugin/plugin.json        # plugin manifest
.claude-plugin/marketplace.json   # marketplace listing (this repo)
hooks/hooks.json                  # registers the Stop hook
hooks/stop_comment_check.sh        # gate + scope logic for the hook
skills/comment-cleaner/SKILL.md   # the skill
skills/comment-cleaner/scripts/scope.sh   # scope resolver (git + sh)
```
