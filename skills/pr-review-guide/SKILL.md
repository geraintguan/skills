---
name: pr-review-guide
description: >-
  Builds an interactive review guide for a pull request or branch diff and publishes
  it as an artifact. The guide has a high-level overview (summary, before/after,
  architecture diagram, code layout, key decisions). Sections follow review order,
  each listing its changes as Added / Modified / Deleted with High / Medium / Low
  impact tags. Each changed test file gets a table of the tests it changed. Diffs are
  syntax-highlighted, with file-level and line-level notes, a reviewed checklist, and
  collapsing for reviewed sections. Use it whenever the user asks for an artifact,
  page, guide or walkthrough to help them (or someone else) review a PR, branch,
  commit range or diff, even if they don't name this skill.
---

# PR review guide

The guide helps one person review a change fast and miss nothing. It puts the diff
in an order that makes sense and says where the risk is. It also explains what each
test covers. The layout and behaviour are fixed by `assets/template.html`. Your job
is the content: a JSON config that `scripts/build.py` turns into one HTML page.

## What the page contains

From top to bottom:

1. **Header.** Title, PR link, line counts, the tokens and estimated cost of building
   the guide, and legends for impact levels and test types.
2. **Overview.** Summary, before/after cards, a mermaid architecture diagram, a
   code-layout table, and key decisions.
3. **Sections, in review order.** Each section has:
   - a caret, plus counts per impact level
   - a one-line lead saying where to start
   - collapsible Added / Modified / Deleted lists, where every item has an impact tag
   - its files' diffs, with an "About this file" note and inline line notes
   - on each test file, above its diff, a Tests table, collapsed by default: change,
     test name, Unit / Integration / E2E, inputs, expected output, and why the test changed
4. **Sidebar and toolbar.** The sidebar lists every file, has collapsible sections, and
   shows progress. The toolbar has hide tests/stories, hide line notes, and expand or
   collapse all.

Reviewing is tracked in the viewer's browser. Ticking a file collapses it. Once every
file in a section is ticked, the section turns green and collapses, in the page and
in the sidebar.

## Workflow

### 1. Scope the diff

- Work out the base: `git fetch` first, then `git merge-base origin/<base-branch> HEAD`.
  For a PR, `gh pr view <n> --json baseRefName,headRefName,title,url` gives the branches.
- List what changed: `git diff --stat <base> HEAD` and `git diff --name-status <base> HEAD`.
- Pick out generated or bulk files: machine translations, lockfiles, snapshots and
  codegen. These go in `skip_prefixes`. Name them in `meta_extra` so the reader knows
  they were left out. Keep the source-of-truth file in, for example the base locale.
- If the repo has confidentiality rules for PRs (a CLAUDE.md or AGENTS.md), they apply
  to the page too. The page is shareable.

### 2. Read the change before writing anything

Read the full diff of every source file. Read the old version of anything you will
describe as "before", with `git show "<base>:<path>"`. In zsh, write `"${B}:path"`,
not `"$B:path"`, because zsh reads `$B:h` and the like as modifiers.

For a large diff, delegate reading by area to parallel subagents. Ask each for facts
with function names and line numbers, not prose.

### 3. Plan the sections

Order the sections the way a reviewer should read them:

1. The core new piece first.
2. Then the shared wrappers and infrastructure that use it.
3. Then each consumer.
4. Then supporting changes and copy.

Inside a section, list source files first, then tests, then stories. A consumer's
source, test, story and small call-site changes share one section. Deleted files go
with whatever replaced them. Every changed file outside `skip_prefixes` must be in a
section. The builder exits with an error if one is missing.

### 4. Write the config

Use `references/config.md` for every key, the impact-level rules and the writing rules.
Start from `assets/example-config.json`. Write the config in a scratch directory, not
in the user's repo.

The parts, in the order to write them:

- **Overview.** Say what the change does and why, before and after. The diagram shows
  what uses what, with a one-line caption. The layout table has the paths and what each
  does in this PR. Decisions mark the ones the user made.
- **Section `lead` and `changes`.** Sort into Added, Modified and Deleted, and tag each
  High, Medium or Low. Name the real functions. State the concrete behaviour, including
  any threshold or default that moved from old to new.
- **File `note` and line `lines`.** Narrate freely at file and line level. Line notes
  belong on the lines a reviewer must understand: invariants, fallbacks and guards, hook
  or call order, cache and fetch behaviour, analytics meaning, and behaviour that differs
  from the base. Every line note must point at a line in the diff, or the build fails.
- **Section `tests`.** See step 5.

Define library and framework terms in one clause the first time they appear, for
example "RTK Query cache". Readers ask.

Draw every diagram with [Mermaid](https://mermaid.js.org/), never ASCII art, hand-written
SVG or images. The overview diagram goes in `overview.diagram`. Anywhere else (a file
note, a line note, a change item), put the source in `<pre class="mermaid">…</pre>`
inside the HTML. The page loads mermaid.js, themes it to match the page, and
renders each diagram when it scrolls into view. Pick the diagram type that fits:
`flowchart` for what uses what, `sequenceDiagram` for call or event order,
`stateDiagram-v2` for state changes, `erDiagram` for schema changes.

### 5. Describe the tests

1. Run `python3 <skill>/scripts/tests_inventory.py <base> inventory.json` from the repo
   root. It lists the added, modified and removed test cases (`it`/`test`, including
   `.each`), and the Storybook stories that have a `play` function.
2. The inventory is a starting point. Its describe prefixes can be wrong for sibling
   `describe` blocks. A "modified" test may only rename a constant. A test renamed in
   place shows as one removal plus one addition.
3. Have parallel subagents read the test bodies and write the rows. Use one agent per
   one to three sections, and give each the inventory path, its files, the base commit,
   the row schema from `references/config.md`, and a paragraph on what the PR changes.
   Ask them to:
   - use the real test names
   - say when a change is a rename only
   - name the test that replaces each removed one
4. Merge the rows into each section's `tests` array. The page shows each row in its
   `file`'s card. You can also point a section at
   them with `tests_file`.
5. Spot-check a few rows against the code.
6. Note any coverage gaps the rows show, such as an untested boundary. Tell the user.

### 6. Build, check, publish

```bash
python3 <skill>/scripts/build.py config.json out.html
```

Each build counts the tokens and estimated cost of making the guide so far and shows
them in the header. It reads this session's transcript and its subagents' transcripts,
from the last launch of this skill onwards, so a rebuild after feedback adds that
work too. The cost is an estimate at API list prices, not what a subscription is
billed. If the hover breakdown says "no price" for a model, add the model to `PRICES`
in `scripts/usage.py`.

The builder fails on any of these:
- a changed file in no section
- an empty diff for a listed file
- a line note outside the diff
- an unknown change type, impact level or test type
- a test row for a file outside its section

Fix the config and rebuild.

Before publishing:

- Check every claim in the notes against the code. Each pass so far has caught a few
  wrong ones: a misremembered string, a misread condition, a guessed behaviour.
- Run a syntax check on the page script: pull out the last inline `<script>` and run
  `node --check` on it.
- Open the page and check that every diagram renders. A Mermaid syntax error shows
  as an error box in place of the diagram.

Publish the HTML with the Artifact tool. Give the page a short `<title>` that names the
change; the config's `title` key sets it. Republish to the same file path on every
update so the URL stays the same.

### 7. Handle feedback

The user often comments on the page. When a comment asks a question, answer it in the
thread. If the answer shows the page was unclear, also fix the content: add the missing
definition, or reword the heading. When a comment asks for a format change, change
`assets/template.html` or `scripts/build.py` in this skill, not just the one page, so
every future guide gets the change.

## Files

- `scripts/build.py`: checks the config and renders the page from the template.
- `scripts/tests_inventory.py`: lists the tests changed per file.
- `scripts/usage.py`: totals the tokens and estimated cost of building the guide. The
  builder calls it; run it alone to inspect the numbers.
- `assets/template.html`: the page layout, styles and behaviour, always in dark mode.
- `assets/example-config.json`: a made-up example that uses every key, with
  `assets/example-usage.json` as its usage file.
- `references/config.md`: the config schema and the rules for writing the content.
