---
name: pr-review-guide
description: >-
  Builds an interactive review guide for a pull request or branch diff and publishes
  it as an artifact. The guide has a high-level overview (summary, before/after,
  an interactive architecture graph, data flow diagrams, interactive state machines,
  code layout, key decisions). Every diagram can be panned, zoomed and opened full screen;
  nodes link to their code, sequence diagrams play their messages step by step, and
  state machines can be clicked through event by event. Sections
  follow review order, each with its own data flow diagram and its changes listed as
  Added / Modified / Deleted with High / Medium / Low impact tags. Each changed test
  file gets a table of the tests it changed. Test and eval data fixtures, such as
  documents and binary files, are listed with a summary but no diff. Diffs are syntax-highlighted, with
  file-level and line-level notes, a reviewed checklist, and collapsing for reviewed
  sections. Use it whenever the user asks for an artifact, page, guide or walkthrough
  to help them (or someone else) review a PR, branch, commit range or diff, even if
  they don't name this skill.
---

# PR review guide

The guide helps one person review a change fast and miss nothing. It tells the change
as a story: each section builds on the one before, so the reader always knows why
they are looking at this code now. It says where the risk is and explains what each
test covers. A human reads it top to bottom, so readability comes first: small
sections, short sentences, one idea at a time. The layout and behaviour are fixed by `assets/template.html`. Your job
is the content: a JSON config that `scripts/build.py` turns into one HTML page.

## What the page contains

From top to bottom:

1. **Header.** Title, PR link, line counts, the tokens and estimated cost of building
   the guide, and legends for impact levels and test types.
2. **Overview.** Summary, before/after cards, an interactive architecture graph, the
   high-level data flow across the whole change, the main state machines it touches, a
   code-layout table, and key decisions.
3. **Sections, in review order.** Each section has:
   - a caret, plus counts per impact level
   - a bridge: one sentence linking it to the section before, so the story carries on
   - a one-line lead saying where to start
   - collapsible Added / Modified / Deleted lists, where every item has an impact tag
   - a Data flow card: how data moves through this section's part of the change
   - a State card, when the section adds or changes state: its finite state machine
   - its files' diffs, with an "About this file" note and inline line notes
   - on each test file, above its diff, a Tests table, collapsed by default: change,
     test name, Unit / Integration / E2E, inputs, expected output, and why the test changed
   - a Fixtures card, when the section's tests or evals use data files: a summary of the
     data, then each file's change, size and what it holds. Fixtures get no diff, no line
     notes and no reviewed box
4. **Diagrams.** Each one sits in a stage you can drag to pan, pinch or Ctrl/⌘ + scroll
   to zoom, and open full screen. Hovering a node dims everything it isn't connected
   to. Nodes with a link jump to their section or file. Sequence diagrams have play
   and step buttons that walk through the messages in order. Graph edges can be
   animated, and nodes tagged added, changed or removed get matching colours. State
   machines start in their initial state; clicking a state or one of its events moves
   there, and the transitions out of the current state animate.
5. **Sidebar and toolbar.** The sidebar lists every file, has collapsible sections, and
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
- Pick out test and eval data fixtures: sample documents (PDF, DOCX), images, recorded
  responses, golden outputs and eval datasets. These go in the `fixtures` of the section
  whose tests or evals use them, not in `files`. Read enough of each to say what it holds.
- If the repo has confidentiality rules for PRs (a CLAUDE.md or AGENTS.md), they apply
  to the page too. The page is shareable.

### 2. Read the change before writing anything

Read the full diff of every source file. Read the old version of anything you will
describe as "before", with `git show "<base>:<path>"`. In zsh, write `"${B}:path"`,
not `"$B:path"`, because zsh reads `$B:h` and the like as modifiers.

For a large diff, delegate reading by area to parallel subagents. Ask each for facts
with function names and line numbers, not prose.

### 3. Plan the story

Plan the guide as a story before writing any of it. The reader should finish each
section knowing why the next one comes next.

1. **Write the story in a few sentences first.** Say what problem the change solves,
   what the new piece is, how the rest of the code adopts it, and what's left over.
   If you can't tell it simply, you don't understand the change yet: go back to step 2.
2. **Turn each step of the story into a section.** One section is one idea a reviewer
   can hold in their head: "the new retry helper", "the client now treats HTTP errors
   as failures". If a section needs "and" in its title, split it.
3. **Order the sections so each builds on the last.** Introduce a thing before any
   section that uses it. The usual order is:
   1. The core new piece first.
   2. Then the shared wrappers and infrastructure that use it.
   3. Then each consumer.
   4. Then supporting changes and copy.

   Break the usual order when the story needs it, for example a bug fix that reads
   best as "the symptom, the cause, the fix, the tests that pin it".
4. **Write a bridge for every section after the first.** One sentence that hands over
   from the section before: what the reader now knows, and what this section adds.
   For example: "With `withRetry` in place, the client can lean on it. The one real
   change is deciding what counts as a failure." The first section's bridge says why
   the story starts there. The builder warns when a bridge is missing.
5. **Split a file when its changes belong to different steps.** A file can hold more
   than one idea, such as a new helper and a call site that adopts it. Give each idea
   its own section and list the file in each with the `hunks` that belong there,
   instead of showing the whole file in one section the reader isn't ready for. Only
   split when it makes the story easier to follow; most files stay whole.
6. **Read the section titles and bridges in order, alone.** They should tell the whole
   story without the diffs. If one jumps or repeats, reorder, merge or split.

Keep sections small. A section past about 8 files or 400 changed lines usually holds
more than one idea, and the builder warns about it. Split it along the story, for
example "the new state" and then "the components that read it". A big consumer can
take two sections: "how `Editor` loads drafts" and then "how `Editor` saves them".

Inside a section, list source files first, then tests, then stories. Fixtures go in
the section's `fixtures`, next to the tests that load them. A consumer's
source, test, story and small call-site changes share one section. Deleted files go
with whatever replaced them. Every changed file outside `skip_prefixes` must be in a
section, and every hunk of a split file must be in exactly one. The builder exits
with an error if one is missing.

### 4. Write the config

Use `references/config.md` for every key, the impact-level rules and the writing rules.
Start from `assets/example-config.json`. Write the config in a scratch directory, not
in the user's repo.

The parts, in the order to write them:

- **Overview.** Say what the change does and why, before and after. The architecture
  `graph` shows what uses what, with a one-line caption. Tag each node and edge the PR
  adds, changes or removes, group nodes by area, and link each node to its section or
  file. The data flow shows how data moves across
  the whole change (see below). The layout table has the paths and what each does in
  this PR. Decisions mark the ones the user made.
- **Section `data_flow`.** Every section gets one, focused on that section only. See
  "Data flow diagrams" below.
- **`state`.** Wherever the change adds or changes state, model it as a finite state
  machine. Sections get their own `state`; the overview's `state` holds the main
  machines across the change. See "State machines" below.
- **Section `bridge`.** One sentence handing over from the section before. See step 3.
- **Section `lead` and `changes`.** Sort into Added, Modified and Deleted, and tag each
  High, Medium or Low. Name the real functions. State the concrete behaviour, including
  any threshold or default that moved from old to new.
- **File `note` and line `lines`.** Narrate freely at file and line level. Line notes
  belong on the lines a reviewer must understand: invariants, fallbacks and guards, hook
  or call order, cache and fetch behaviour, analytics meaning, and behaviour that differs
  from the base. Every line note must point at a line in the diff, or the build fails.
- **Section `tests`.** See step 5.
- **Section `fixtures`.** A one- or two-sentence `summary` of what the data is and which
  tests or evals use it, then a short `note` per file on what it holds, such as "a
  3-page contract with a redline". A directory path ending in `/` covers every changed
  file under it. Don't describe a fixture's lines: the reader won't see them.

Define library and framework terms in one clause the first time they appear, for
example "RTK Query cache". Readers ask.

Write for a person reading the page, not for a parser. Follow the readability rules in
`references/config.md`: one idea per paragraph, item or note, short sentences, plain
words, and the point first. Break anything complex into small steps the reader can
check one at a time, with a diagram where a picture is clearer than prose.

Never draw diagrams as ASCII art, hand-written SVG or images. There are four kinds, all drawn with React Flow:

- **`graph`** ([React Flow](https://reactflow.dev/), laid out by
  [dagre](https://github.com/dagrejs/dagre)): nodes and edges as JSON. Use it for the
  overview architecture, every flowchart or pipeline, and any "what uses what" picture.
  Readers get a minimap, click-through to code, and nodes they can drag (graphs start
  locked; the 🔒 button or L unlocks them). Nodes can carry a `detail` line, a `group`,
  a `status`, a `link` and a `shape`: `decision` (a diamond for a branch), `terminal`
  (a pill for a start or end) or `store` (a cache or database). Edges tagged `added` or
  `changed` animate.
- **`machine`** (React Flow too): a finite state machine as states and transitions.
  Readers step through it by clicking states or events. Use it for every state machine.
- **`sequence`** (React Flow too): call or event order as participants and steps.
  Steps are messages (`reply: true` for a dashed return), notes, and `loop`, `opt` and
  `alt` fragments. Readers play it or step through it message by message. Use it for
  every sequence diagram.
- **`schema`** (React Flow too): an entity-relationship diagram for schema changes.
  Entities are cards that list their fields (with `PK`, `FK` or `UK` keys and their own
  `status`), and relations are edges labelled with their cardinality, such as `N:1`.

The overview architecture goes in `overview.graph`. For a diagram anywhere else (a file
note, a line note, a change item), name it in the top-level `diagrams` and put
`<div data-diagram="name"></div>` in the HTML where it goes. The page themes every
diagram to match, and renders each one when it scrolls into view.

#### Data flow diagrams

Architecture says what uses what. Data flow says what moves where, in what order:
inputs, calls, events, cache and store reads and writes, responses and errors.

- **Overview `data_flow`:** the end-to-end path through the change, at the level of
  components and services. One diagram per main journey, such as a read path and a
  write path. Keep each under about 12 participants.
- **Section `data_flow`:** zoom in on that section. Show the real function, hook or
  endpoint names, what each passes and returns, and where this PR changed the flow.
  Use `alt` for branches (success and error, cache hit and miss) and `loop` for retries
  and polling. Tag new or changed messages, notes and fragments with `status`, and add a
  note such as `new: refetch, then retry once` where the change needs words. Keep the
  messages in the order they happen: the play button walks through them in source order.
- Use a `sequence` by default. Use a `graph` with `direction: "LR"` for a
  pipeline with no back-and-forth. When data drives state changes, model the state in
  `state` instead.
- A section where no data moves (copy, renames, config only) sets `data_flow: []`
  and says why in the section `lead`. The builder warns when the key is missing.

#### State machines

Model state as a finite state machine wherever the change has it: a status or phase
enum, a reducer or store slice, a request lifecycle (idle, loading, success, error), a
retry or polling loop, a UI mode (closed, open, editing, saving), a job or workflow
status, a feature-flag rollout stage, or a protocol handshake. Implicit state counts
too: a pair of booleans like `isLoading` and `hasError` is a machine with four states,
some of which may be impossible.

- Draw it as a `machine` in the section's `state` (or `overview.state` for one that
  spans sections). Use the real state names from the code and the real events or
  actions as transition labels, such as `FETCH_SUCCEEDED` or `user clicks Save`.
- Mark `initial` and every `final` state. Tag the states and transitions this PR adds,
  changes or removes. Link each state to the file that handles it.
- Show the whole machine, not only the new part, so a reviewer can check every state
  has a way out and nothing reaches a state it shouldn't. Say in the caption what the
  PR changed, and any transition that is missing or unguarded. Tell the user about
  those gaps too.
- Model the states the code really has, and say so when the machine is implicit,
  for example "derived from `isLoading` and `error`".
- Skip it only when nothing in the section holds state.

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
- a fixture path that matches no changed file, or a file listed both as a fixture and in
  `files`, or as a fixture in two sections
- a single string where a list belongs: the overview's `summary`, `before`, `after` or
  `decisions`, or `meta_extra` or `skip_prefixes`
- an empty diff for a listed file
- a line note outside the diff
- an unknown change type, impact level or test type
- a test row for a file outside its section
- a graph node or edge that names an unknown node, or a bad status, shape or direction
- a diagram link to something that isn't a section id, a file in a section, or `overview`
- a sequence message or note that names an unknown participant, or a fragment with no
  condition or no steps
- a schema relation that names an unknown entity, a field with no name, or a bad key
  or cardinality
- an unknown flow key, or a `data-diagram` name missing from `diagrams`

Fix the config and rebuild.

Before publishing:

- Read the page top to bottom as the reviewer would. Check the story flows from
  section to section, and that no section, note or caption is a wall of text. Split
  or cut anything that is.

- Check every claim in the notes against the code. Each pass so far has caught a few
  wrong ones: a misremembered string, a misread condition, a guessed behaviour.
- Run a syntax check on the page script: pull out the last inline `<script>` and run
  `node --check` on it.

Publish the HTML with the Artifact tool. Give the page a short `<title>` that names the
change; the config's `title` key sets it. Republish to the same file path on every
update so the URL stays the same.

#### Library version drift

The page loads React, React Flow and dagre from jsDelivr, pinned to exact versions in
`assets/template.html`. Over time those builds can stop working together: a URL stops
resolving, or React Flow picks up a second copy of React. The page checks for both. When
one happens it shows a warning banner asking the reader to regenerate the guide, lists
what failed, and logs it to the console under `diagram`. Non-interactive parts keep
working.

When a user reports the banner, fix the template, not the one page:

1. Read the banner's list or the console for which library failed.
2. Bump the pinned URLs in `XYFLOW_URLS` to versions that work
   together. When React's version changes, list the React URLs that jsDelivr's builds
   import, and point each one at the single pinned copy in the import map.
3. Rebuild and republish the guide, and ask the user to confirm the banner is gone.

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
  It loads React Flow, React and dagre from jsDelivr, only when a page has diagrams.
- `assets/xyflow.css`: React Flow's stylesheet. The builder inlines it only into pages
  with a diagram, because artifacts can't load stylesheets from a CDN.
- `assets/example-config.json`: a made-up example that uses every key, with
  `assets/example-usage.json` as its usage file. The demo has no database, so its one
  missing diagram kind, `schema`, is shown in `references/config.md`.
- `references/config.md`: the config schema and the rules for writing the content.
