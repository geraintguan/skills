# comment-cleaner

Removes low-value, redundant code comments — the kind LLMs scatter everywhere
(`# increment i`, `// loop over users`) — while keeping the comments that actually
carry information. When a comment held context that a name could hold instead, it
refactors the name and drops the comment; when the context can't live in a name,
it keeps the comment and tells you why.

It ships as:

- a **skill** you can invoke any time, and
- a **Stop hook** that runs the cleanup automatically when a coding task finishes
  (Claude Code plugin install only — see below).

## Install

There are two ways to install, depending on whether you want the automatic Stop
hook. Both require this repository to be pushed to GitHub at `geraintguan/skills`
(replace with your fork if different).

### Option A — Claude Code plugin (recommended: skill **+** auto-run hook)

This repo is its own plugin marketplace. From inside Claude Code:

```
/plugin marketplace add geraintguan/skills
/plugin install comment-cleaner@scalesignal-skills
```

You can also point the marketplace at a local clone instead of GitHub:

```
/plugin marketplace add /path/to/skills
```

This installs the skill **and** registers the Stop hook, so cleanup runs
automatically after coding tasks. Invoke it manually any time with
`/comment-cleaner:comment-cleaner`.

### Option B — skills.sh / `skills` CLI (skill only, no hook)

[skills.sh](https://www.skills.sh/docs) installs the skill into your agent's
skills directory. It works with Claude Code and 70+ other agents, but it installs
**only the skill** — the Stop hook is a plugin feature and is **not** set up this
way. Use this if you just want on-demand cleanup, or you're on a non–Claude-Code
agent.

```bash
# Install the comment-cleaner skill into the current project (./.claude/skills/)
npx skills add geraintguan/skills --skill comment-cleaner

# Install globally for your user (~/.claude/skills/) and target Claude Code
npx skills add geraintguan/skills --skill comment-cleaner -g -a claude-code -y
```

The CLI discovers the skill from this repo's `skills/comment-cleaner/SKILL.md`
(it reads the bundled `.claude-plugin` manifests too). You can also install
straight from the subdirectory:

```bash
npx skills add https://github.com/geraintguan/skills/tree/main/skills/comment-cleaner
```

Manage it with `npx skills list`, `npx skills update`, and `npx skills remove`.

> **Which should I pick?** Want cleanup to happen automatically after coding
> tasks → **Option A** (the hook only exists there). Just want to run it on demand,
> or you're not on Claude Code → **Option B**.

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

This hook is only active with the **Option A** plugin install.

### Turning the auto-run off

Don't want the automatic behavior but still want the skill? Disable hooks for this
plugin in `/plugin`, or delete `hooks/hooks.json` from your local copy. The skill
remains usable on demand regardless. (Option B never installs the hook in the
first place.)

## Layout

```
.claude-plugin/plugin.json              # plugin manifest
.claude-plugin/marketplace.json         # marketplace listing (this repo)
hooks/hooks.json                        # registers the Stop hook
hooks/stop_comment_check.sh             # gate + scope logic for the hook
skills/comment-cleaner/SKILL.md         # the skill
skills/comment-cleaner/scripts/scope.sh # scope resolver (git + sh)
```
