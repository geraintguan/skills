# comment-cleaner

Removes low-value, redundant code comments — the kind LLMs scatter everywhere
(`# increment i`, `// loop over users`) — while keeping the comments that actually
carry information. When a comment held context that a name could hold instead, it
refactors the name and drops the comment; when the context can't live in a name,
it keeps the comment and tells you why.

## Install

There are two ways to install. Both require this repository to be pushed to
GitHub at `geraintguan/skills` (replace with your fork if different).

### Option A — Claude Code plugin

This repo is its own plugin marketplace. From inside Claude Code:

```
/plugin marketplace add geraintguan/skills
/plugin install comment-cleaner@geraintguan-skills
```

You can also point the marketplace at a local clone instead of GitHub:

```
/plugin marketplace add /path/to/skills
```

Invoke it with `/comment-cleaner:comment-cleaner`.

### Option B — skills.sh / `skills` CLI

[skills.sh](https://www.skills.sh/docs) installs the skill into your agent's
skills directory. It works with Claude Code and 70+ other agents.

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

## What it does

For the comments in scope, each is sorted into one of four buckets:

| Bucket | Action |
| --- | --- |
| Restates the code (`# add one` over `i += 1`) | **removed** |
| Context a better name could hold (`d = 7  # days`) | **name refactored** (`retention_days = 7`), comment dropped |
| Functional directive / doc / TODO / legal / genuine "why" | **kept** |
| Useful context a name can't capture | **kept and reported** |

**Scope**, unless you name specific files: staged changes → else the current
branch's commits vs. the default branch → else the whole tracked codebase.

## Layout

```
.claude-plugin/plugin.json              # plugin manifest
.claude-plugin/marketplace.json         # marketplace listing (this repo)
skills/comment-cleaner/SKILL.md         # the skill
skills/comment-cleaner/scripts/scope.sh # scope resolver (git + sh)
```
