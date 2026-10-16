# Config reference

`scripts/build.py config.json out.html` reads one JSON object. All HTML fields are
inserted as-is, so escape `<` in prose as `&lt;` and wrap identifiers in `<code>`.

Every diagram is [Mermaid](https://mermaid.js.org/). Outside `overview.diagram`, embed
one in any HTML field as `<pre class="mermaid">flowchart LR\n  A --> B</pre>`. Escape
`<` in its labels as `&lt;`.

## Top level

| Key | Required | What it is |
|---|---|---|
| `repo_root` | no (default `.`) | Path to the git checkout. |
| `base` | yes | Base commit, usually the merge-base with the target branch. |
| `head` | no (default `HEAD`) | Head ref. |
| `title` | yes | The page `<title>`: a two-to-four-word name for the change, such as "Retry Backoff Review". |
| `eyebrow` | yes | Small line above the heading, such as "Pull request #123 · feature-branch → main". |
| `h1` | yes | The PR title. |
| `lede` | yes | One or two sentences on how to read the page. |
| `pr_url` | yes | Link to the PR. Use the compare URL for a plain branch. |
| `store_key` | yes | localStorage key for review ticks, unique per PR, such as `pr123-reviewed`. |
| `meta_extra` | no | Short HTML strings for the header meta row, such as "28 machine-translated locales left out" or "Reviews: LGTM". |
| `usage_file` | no | Path to saved `scripts/usage.py` output, relative to the config. Leave it out: a build in a Claude Code session counts its own tokens and cost. Use it for builds outside a session, such as the example. The header shows the total tokens and estimated cost, with a per-model breakdown on hover. |
| `skip_prefixes` | no | Changed paths left out on purpose. Name them in `meta_extra`. |
| `overview` | yes in practice | See below. |
| `groups` | yes | The sections, in review order. See below. |

## `overview`

| Key | What it is |
|---|---|
| `summary` | HTML paragraphs. The first says what the change does and why. The second says how it's built. |
| `before`, `after` | HTML bullets. Parallel lists: each "after" bullet answers a "before" bullet. |
| `diagram` | Mermaid source, usually `flowchart TD`. Arrows go from a component to what it uses. Group with `subgraph`. Keep it under about 20 nodes. |
| `diagram_caption` | One HTML line on how to read the diagram, and which parts are generic. |
| `layout` | `[{path, role, group}]`. `path` is a file or directory prefix. The builder sums the +/− lines under it. `role` says what that path does in this PR. `group` is a section `id`, used for the link. |
| `decisions` | HTML bullets for design decisions. Mark the ones the user made with `<em>(your call)</em>`. |

## `groups[]`

| Key | What it is |
|---|---|
| `id` | A short slug, used for anchors. |
| `title` | The section name. Gloss jargon in it, for example "DataGrid (the design system)". |
| `lead` | One sentence saying where to start reading. |
| `changes` | `{added, modified, deleted}`. Each holds a list of `{impact, text}`. Leave out a type with no entries. |
| `files` | Paths, or `{path, note, lines}` objects, ordered source → tests → stories. |
| `tests` | Test rows, each shown on its file's card. See below. |
| `tests_file` | Path to a JSON array of test rows, relative to the config. It's merged into `tests`. |
| `note` | Legacy: a plain list used when `changes` is missing. Don't use it in new configs. |

### Impact levels

- **High:** behaviour users see, or logic that's easy to get wrong. Examples: a new
  shared component, cache or fetch behaviour, what a click opens.
- **Medium:** a real logic change with limited reach. Examples: a threshold moving,
  a guard, a fallback, hook order, analytics meaning.
- **Low:** mechanical changes. Examples: renames, import swaps, exports, tests,
  stories, copy, style-only tweaks.

Write each item as one or two sentences. Name the function. State the behaviour.
Flag every behaviour change against the base, for example "now at 5 or more, was
more than 5". Mention small visible changes too, such as a formatting change in a
table.

### File entries

```json
{"path": "src/feed/GroupedCard.tsx",
 "note": "The only chat-aware layer: adds the drawer tab, the menu item and analytics.",
 "lines": [
   {"line": 43, "text": "Same id format as before, so existing tabs still match.", "impact": "Medium"},
   {"line": 12, "side": "old", "text": "The removed guard moved into <code>useShouldGroup</code>."}
 ]}
```

- `note` goes above the file's diff. One or two sentences on what the file's change
  does and why.
- `lines[].line` is a line number in the new file, or in the old file when `side` is
  `"old"`. It must appear in the diff. Context lines count. `impact` is optional.
- Don't narrate every file. Every source file gets a `note`. Tests and stories get one
  when the note says what the tests cover.

### Test rows

```json
{"file": "src/feed/GroupedCard.test.tsx",
 "name": "GroupedCard › opens a clicked row and tracks its position",
 "change": "Added",
 "type": "Integration",
 "inputs": "3 items with an <code>onOpenItem</code> spy; clicks the second row.",
 "expected": "<code>onOpenItem</code> called with item 2; <code>Group_ItemOpened</code> tracked with <code>position: 1</code>.",
 "why": "Covers the wrapper's click analytics, which replace the old “View all” event."}
```

- `change` is one of `Added`, `Modified` or `Removed`.
- `type` is one of these:
  - `Unit`: calls a pure function and renders nothing.
  - `Integration`: renders components, with Testing Library in jsdom or in a Storybook
    play function.
  - `E2E`: Playwright or similar against the running app.
- `name` takes the form "describe › test", using the real names from the source.
- `inputs` covers fixture sizes, props, mocked providers, cache contents and user
  actions. List the cases of an `.each`.
- `expected` covers the concrete assertions: calls and their arguments, ARIA roles
  and states, event names and properties, counts.
- `why` ties the change to the PR. Say "rename only" when that's all it is. A removed
  row names the test that replaces it.
- `file` must be one of the section's files. The row shows in a Tests table on that
  file's card, above its diff.

## Writing rules

- Lead with the point. Use short sentences, active voice and real names.
- Keep technical terms, and define a library or domain term in one clause the first
  time it appears.
- Never claim something you haven't checked in the code. When unsure, read the file.
- Keep customer and personal data out of the page. It's shareable.
