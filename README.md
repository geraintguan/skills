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
.claude-plugin/marketplace.json         # marketplace listing: one plugin per skill
skills/comment-cleaner/SKILL.md         # the skill
skills/comment-cleaner/scripts/scope.sh # scope resolver (git + sh)
skills/pr-review-guide/SKILL.md         # the review-guide skill
skills/pr-review-guide/scripts/         # build.py (config → page), tests_inventory.py, usage.py (build tokens and cost)
skills/pr-review-guide/assets/          # template.html, example config and usage, demo repo script
skills/pr-review-guide/references/      # config.md (schema and writing rules)
```

---

# pr-review-guide

Builds an interactive review guide for a pull request or branch diff, published as an
artifact. A reviewer can go through it in order and miss nothing. The page has:

- **Overview:** summary, before/after, a mermaid architecture diagram, a code-layout
  table and key decisions.
- **Sections in review order:** changes grouped as Added / Modified / Deleted, each
  tagged High / Medium / Low impact.
- **Diffs:** syntax-highlighted, with file-level and line-level notes. Each test file
  gets a table of the tests it changed (inputs, expected output, why).
- **Checklist:** reviewed ticks saved in the browser. Reviewed files and finished
  sections collapse, in the page and the sidebar.

Ask for it in plain words ("make an artifact to help me review PR #123") or run
the slash command.

## Install

Same two options as comment-cleaner.

### Option A — Claude Code plugin

From inside Claude Code:

```
/plugin marketplace add geraintguan/skills
/plugin install pr-review-guide@geraintguan-skills
```

Invoke it with `/pr-review-guide:pr-review-guide`.

### Option B — skills.sh / `skills` CLI

```bash
# Install the pr-review-guide skill into the current project (./.claude/skills/)
npx skills add geraintguan/skills --skill pr-review-guide

# Install globally for your user (~/.claude/skills/) and target Claude Code
npx skills add geraintguan/skills --skill pr-review-guide -g -a claude-code -y
```

Or straight from the subdirectory:

```bash
npx skills add https://github.com/geraintguan/skills/tree/main/skills/pr-review-guide
```

## Try it

Build a guide from the bundled demo:

```bash
sh skills/pr-review-guide/assets/demo/make_repo.sh /tmp/pr-review-guide-demo
python3 skills/pr-review-guide/scripts/build.py \
  skills/pr-review-guide/assets/example-config.json /tmp/demo-review.html
```
