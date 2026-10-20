# Config reference

`scripts/build.py config.json out.html` reads one JSON object. All HTML fields are
inserted as-is, so escape `<` in prose as `&lt;` and wrap identifiers in `<code>`.

A diagram is a `sequence` (participants and messages), a `graph` (nodes and edges), a
`machine` (an interactive finite state machine) or a `schema` (an entity-relationship
diagram). All four are JSON, drawn with [React Flow](https://reactflow.dev/). See
"Diagrams". To put a diagram in an HTML field, name it in `diagrams` and write
`<div data-diagram="name"></div>`.

## Top level

| Key | Required | What it is |
|---|---|---|
| `repo_root` | no (default `.`) | Path to the git checkout. |
| `base` | yes | Base commit, usually the merge-base with the target branch. |
| `head` | no (default `HEAD`) | Head ref. |
| `title` | yes | The page `<title>`: a two-to-four-word name for the change, such as "Retry Backoff Review". It's HTML text: entities such as `&lt;` work, and tags are dropped. |
| `eyebrow` | yes | Small line above the heading, such as "Pull request #123 · feature-branch → main". |
| `h1` | yes | The PR title. |
| `lede` | yes | One or two sentences on how to read the page. |
| `pr_url` | yes | Link to the PR. Use the compare URL for a plain branch. |
| `store_key` | yes | localStorage key for review ticks, unique per PR, such as `pr123-reviewed`. |
| `meta_extra` | no | Short HTML strings for the header meta row, such as "28 machine-translated locales left out" or "Reviews: LGTM". |
| `usage_file` | no | Path to saved `scripts/usage.py` output, relative to the config. Leave it out: a build in a Claude Code session counts its own tokens and cost. Use it for builds outside a session, such as the example. The header shows the total tokens and estimated cost, with a per-model breakdown on hover. |
| `skip_prefixes` | no | Changed paths left out on purpose. Name them in `meta_extra`. |
| `diagrams` | no | `{name: flow}`, each flow `{diagram or graph or machine, title, caption}`. `<div data-diagram="name"></div>` in any HTML field draws that diagram there, such as in a file note. The builder fails on a name that isn't here and warns about one that's never used. |
| `overview` | yes in practice | See below. |
| `groups` | yes | The sections, in review order. See below. |

## `overview`

| Key | What it is |
|---|---|
| `summary` | A list of HTML paragraphs, even for one paragraph. The first says what the change does and why. The second says how it's built. |
| `before`, `after` | HTML bullets. Parallel lists: each "after" bullet answers a "before" bullet. |
| `graph` | The architecture as a graph (see "Diagrams"). Edges go from a component to what it uses. Group nodes by area, tag what the PR adds, changes or removes, and link each node to its code. Keep it under about 20 nodes. |
| `diagram_caption` | One HTML line on how to read the diagram, and which parts are generic. |
| `state` | A list of flows `{title, machine, caption}`: the main state machines the change touches. Shown under "State". See "State machines". |
| `data_flow` | A list of flows, each `{title, sequence or graph or machine, caption}`. The high-level data flow across the whole change, one flow per main journey, usually a `sequence`. `title` and `caption` are optional HTML. See "Data flow". |
| `layout` | `[{path, role, group}]`. `path` is a file or directory prefix. The builder sums the +/− lines under it. `role` says what that path does in this PR. `group` is a section `id`, used for the link. |
| `decisions` | Design decisions as `{area, impact, text}`, grouped by area and then by impact, highest first. `area` is the part of the system or concern the decision touches, as HTML, such as `Error handling` or `The <code>users</code> table`; reuse the exact same string for every decision in that area. Areas with a High decision come first. `impact` is `High`, `Medium` or `Low` (see "Decision impact"). `text` is HTML. Mark the ones the user made with `<em>🙋 (your call)</em>`. |
| `api` | Every API endpoint the PR adds, modifies or removes. See "API endpoints". `[]` shows "No API changes". The builder warns when the key is missing. |
| `metrics` | Every metric the PR adds, modifies or removes: logs, OpenTelemetry (oTel) metrics and spans, analytics events. See "Metrics and flags". `[]` shows "No metric changes". The builder warns when the key is missing. |
| `flags` | Every feature flag the PR adds, modifies or removes. See "Metrics and flags". `[]` shows "No feature flags". The builder warns when the key is missing. |

Each overview part (summary, before and after, architecture, data flow, state, code
layout, key decisions, API, metrics, feature flags) that has content gets its own entry under
Overview in the sidebar.

### Decision impact

- **High:** shapes behaviour users see, or is hard to reverse: a public API or data
  contract, a schema, what counts as an error.
- **Medium:** a real trade-off with limited reach, such as a default, a threshold or a
  library choice.
- **Low:** local choices that are easy to change later, such as naming or file layout.

### API endpoints

```json
"api": [
  {"name": "/api/drafts/:id", "method": "PUT", "protocol": "REST", "change": "Added", "file": "src/server/drafts.ts",
   "does": "Saves a draft's body and returns its new <code>version</code>.",
   "why": "Autosave needs an idempotent save; <code>POST /api/drafts</code> made a new draft each time."},
  {"name": "drafts.list", "method": "GET (query)", "protocol": "tRPC", "change": "Modified", "file": "src/server/routers/drafts.ts",
   "does": "Lists the user's drafts, newest first.",
   "why": "Takes an optional <code>cursor</code> so long lists page instead of loading at once."}
]
```

- `name` is the route path, or the procedure or operation name for RPC-style APIs.
- `method` is the HTTP method: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`. For tRPC or
  GraphQL, add the kind, such as `GET (query)` or `POST (mutation)`.
- `protocol` is the API style: `REST`, `RESTful`, `tRPC`, `GraphQL`, `gRPC`, `JSON-RPC`,
  `Webhook`, `WebSocket`.
- `does` is a short description of what the endpoint does. `why` says why it's added,
  modified or removed. Both are HTML.
- `change` is `Added`, `Modified` or `Removed`. A change to inputs, outputs, auth or
  status codes is Modified. `file` is optional: a link target, usually the file that
  defines the endpoint. The name then links there.

### Metrics and flags

```json
"metrics": [
  {"name": "Draft_Saved", "change": "Added", "where": "Amplitude event", "file": "src/drafts/useSaveDraft.ts",
   "tracks": "Each successful save, with <code>draftId</code> and <code>attempt</code>.",
   "why": "Shows how often the new retry path saves a draft that would have failed."}
],
"flags": [
  {"name": "drafts_autosave", "code": "FLAGS.draftsAutosave", "change": "Added", "file": "src/drafts/useAutosave.ts",
   "gates": "Saving the draft every 5 seconds while the editor is open.",
   "why": "Rolls autosave out to 10% of users first.",
   "default": "Off. Saves only on click."}
]
```

- Metric: `name` is the exact event, log message, span or metric name. `where` says
  where it's tracked, such as "Log", "OpenTelemetry metric", "OpenTelemetry span" or
  "Amplitude event". `tracks` is what it measures, with its properties. `why` says why
  it's added, modified or removed.
- Flag: `name` is the exact name in the flag system, such as a Statsig gate. `code` is
  the identifier in the code, when it differs. `gates` is what turns on with the flag,
  and `why` says why it's added, modified or removed. `default` is optional: the default
  state and the behaviour when off.
- Both: `change` is `Added`, `Modified` or `Removed`. `file` is optional: a link target,
  usually the file that emits the metric or checks the flag. The name then links there.

## `groups[]`

| Key | What it is |
|---|---|
| `id` | A short slug, used for anchors. |
| `title` | The section name, as HTML, so it can hold `<code>`. Gloss jargon in it, for example "DataGrid (the design system)". |
| `bridge` | One HTML sentence linking this section to the one before it: what the reader now knows, and what this section adds. The first section's bridge says why the story starts here. Shown under the title, even when the section is collapsed. The builder warns when it's missing after the first section. |
| `lead` | One sentence saying where to start reading. |
| `changes` | `{added, modified, deleted}`. Each holds a list of `{impact, text}`. Leave out a type with no entries. |
| `files` | Paths, or `{path, note, lines, hunks}` objects, ordered source → tests → stories. `hunks` splits a file across sections (see "Splitting a file"). |
| `tests` | Test rows, each shown on its file's card. See below. |
| `tests_file` | Path to a JSON array of test rows, relative to the config. It's merged into `tests`. |
| `state` | A list of flows `{title, machine, caption}` for the state this section adds or changes, shown in a State card under the data flow. See "State machines". |
| `data_flow` | A list of flows `{title, sequence or graph or machine, caption}` for this section only, shown under the changes. Usually one. The builder warns when the key is missing; set `[]` for a section where no data moves. See "Data flow". |
| `fixtures` | `{summary, files}`: test or eval data this section's tests use, listed without diffs. See "Fixtures". |
| `note` | Legacy: a plain list used when `changes` is missing. Don't use it in new configs. |

### Data flow

```json
"data_flow": [{
  "title": "Saving a draft",
  "sequence": {
    "participants": [
      {"id": "ui", "label": "DraftEditor", "link": "src/DraftEditor.tsx"},
      {"id": "hook", "label": "useSaveDraft", "status": "changed"},
      {"id": "api", "label": "POST /drafts"}
    ],
    "steps": [
      {"from": "ui", "to": "hook", "label": "save(text)"},
      {"from": "hook", "to": "api", "label": "{id, text}"},
      {"alt": [
        {"when": "200", "steps": [
          {"from": "api", "to": "hook", "label": "draft", "reply": true},
          {"from": "hook", "to": "ui", "label": "saved", "reply": true}
        ]},
        {"when": "409", "steps": [
          {"from": "api", "to": "hook", "label": "conflict", "reply": true},
          {"note": "new: refetch, then retry once", "over": ["hook"], "status": "added"}
        ]}
      ]}
    ]
  },
  "caption": "The 409 branch is new."
}]
```

- Show what moves, in order: arguments, requests, events, cache or store reads and
  writes, return values and errors. The architecture diagram already covers what uses what.
- Use a `sequence` unless a `graph` with `direction: "LR"` reads better for a
  one-way pipeline.
  Put state driven by data in `state` as a `machine`.
- Use real names for participants and messages. Tag what this PR adds or changes with
  `status`, and explain it in a note or the caption.
- The overview flow stays at the component level. A section flow zooms in on its own files.

### Diagrams

Every diagram renders in a stage with zoom, fit and full-screen buttons. Readers drag to
pan and pinch or Ctrl/⌘ + scroll to zoom; plain scrolling still scrolls the page.
Hovering a node dims everything it isn't connected to.

**Tooltips.** Every element takes a `tip`: plain text, shown as written in a tooltip
when the reader hovers it. The tooltip's heading names the kind of element and its
label, such as "Participant · useSaveDraft" or "Edge · getJson → withRetry". Then it
shows the tip, then what a click does.

- Write one or two sentences on what the element is and what it does in this change.
  Don't repeat the label. For an actor (a participant, node or entity), say who or what
  it is and its job in the flow. For an arrow (a message, edge, transition or relation),
  say what moves along it, or what triggers it.
- Say what's new or different when the element has a `status`.
- Nodes, states, participants, entities, edges, transitions, relations, messages, loops,
  opts and alt branches need one: the builder warns about each that has none. Notes,
  whole alts and schema fields can take one but don't need it. A graph, machine or
  schema puts its groups' tips in `group_tips`, keyed by group name.

**Graph** (React Flow, laid out by dagre):

```json
"graph": {
  "direction": "LR",
  "nodes": [
    {"id": "getJson", "label": "getJson", "detail": "src/client.ts", "group": "Client", "status": "changed", "link": "src/client.ts",
     "tip": "Fetches a URL and parses the body. It now treats non-2xx responses as failures."},
    {"id": "withRetry", "label": "withRetry", "detail": "src/retry.ts", "group": "Retry helper", "status": "added", "link": "retry",
     "tip": "New: runs a function up to N times, waiting longer between attempts."}
  ],
  "edges": [{"from": "getJson", "to": "withRetry", "label": "3 attempts", "status": "added",
             "tip": "getJson now wraps each request in withRetry."}],
  "group_tips": {"Client": "The app's HTTP layer.", "Retry helper": "The new retry code."}
}
```

- `direction`: `TB` (default), `LR`, `BT` or `RL`.
- Node: `id` and `label` are required, and labels are plain text. `detail` is a second,
  smaller line, such as the file. Nodes with the same `group` are boxed together.
  `status` is `added`, `changed` or `removed`. `link` is a link target. `shape` is
  `decision` (a diamond, for a branch such as `response.ok?`), `terminal` (a pill, for
  where a flow starts or ends) or `store` (a cache, queue or database). Leave it out for
  a plain box. Label a decision's edges with the outcomes, such as `yes` and `no`.
- Edge: `from` and `to` are node ids. `label` is plain text. `status` colours the edge.
  `tip` shows when the reader hovers the edge or its label.
  `added` and `changed` edges animate unless `animated` is `false`.
- Graphs and machines start locked: readers can pan and zoom but not move nodes until
  they press 🔒 (or L). Graphs with more than eight nodes get a minimap.

**Sequence** (React Flow, laid out in columns): see the example under "Data flow".

- Participant: `id` and `label` are required. `detail`, `status` and `link` work as on
  graph nodes. Each participant is a column, with its header repeated at the bottom.
- `steps` run top to bottom. Each one is one of:
  - a message: `{from, to, label}`, plus `reply: true` for a dashed return and an
    optional `status`. `from` and `to` can be the same participant, for a self-call.
  - a note: `{note, over}`, where `over` lists one or two participant ids.
  - a fragment: `{loop: condition, steps}`, `{opt: condition, steps}`, or
    `{alt: [{when, steps}, …]}` for branches. Fragments nest.
- Fragments and notes take a `status` too.
- Participants and messages take a `tip`, as do a `loop` or `opt` and each `alt` branch
  (`{when, steps, tip}`). A fragment's tip shows on its header, and each later branch's
  on its divider.
- The stage has play, step and "show all" buttons (and P, N and A keys) that walk
  through the messages in order. Clicking a message jumps to it. Hovering a participant
  fades the messages that don't touch it.

**Schema** (React Flow, laid out by dagre like a graph), for schema and data model changes:

```json
"schema": {
  "entities": [
    {"id": "drafts", "label": "drafts", "detail": "migrations/0042_drafts.sql", "status": "added", "link": "migrations/0042_drafts.sql",
     "fields": [
       {"name": "id", "type": "uuid", "key": "PK"},
       {"name": "author_id", "type": "uuid", "key": "FK"},
       {"name": "body", "type": "text"},
       {"name": "saved_at", "type": "timestamptz", "status": "added"}
     ]},
    {"id": "users", "label": "users", "fields": [{"name": "id", "type": "uuid", "key": "PK"}]}
  ],
  "relations": [{"from": "drafts", "to": "users", "label": "author_id", "cardinality": "N:1", "status": "added"}]
}
```

- Entity: `id` and `label` are required. `detail`, `group`, `status` and `link` work as
  on graph nodes. `fields` lists its columns in order.
- Field: `name` is required. `type` is the column type, `key` is `PK`, `FK` or `UK`, and
  `status` marks a column the PR adds, changes or removes.
- Relation: `from` and `to` are entity ids, pointing from the table that holds the
  foreign key. `label` is usually that column. `cardinality` is `1:1`, `1:N`, `N:1` or
  `N:N`, read from `from` to `to`.
- `direction` defaults to `LR`. Show the tables the change touches and the ones they
  reference, not the whole database.

The builder fails on a flow key it doesn't know, such as a stray `diagram` or `links`.

### State machines

```json
"state": [{
  "title": "One <code>withRetry</code> call",
  "machine": {
    "initial": "attempting",
    "states": [
      {"id": "attempting", "label": "Attempting", "detail": "await fn()", "link": "src/retry.ts"},
      {"id": "waiting", "label": "Waiting", "detail": "sleep backoffDelay(n)", "status": "added"},
      {"id": "resolved", "label": "Resolved", "final": true},
      {"id": "failed", "label": "Failed", "final": true}
    ],
    "transitions": [
      {"from": "attempting", "to": "resolved", "event": "fn resolves"},
      {"from": "attempting", "to": "waiting", "event": "rejects, attempts left", "status": "added"},
      {"from": "waiting", "to": "attempting", "event": "delay elapsed", "status": "added"},
      {"from": "attempting", "to": "failed", "event": "rejects on last attempt"}
    ]
  },
  "caption": "Waiting is new."
}]
```

- `initial` is a state id. It defaults to the first state.
- State: `id` and `label` are required. `detail`, `group`, `status` and `link` work as
  on graph nodes. `final: true` draws a double border.
- Transition: `from`, `to` and `event` are required, and `status` is optional. A
  transition from a state to itself shows on the state's card as "↻ event".
- `direction` defaults to `LR`.
- The page starts in `initial`. A panel under the diagram shows the current state and a
  button for each event out of it. Clicking a state or an event moves there, and the
  transitions out of the current state animate. A state's code link is its "code ↗"
  button, because clicking the state moves to it.

### Links

A link target is a section `id`, a changed file's path, or `overview`. Clicking the node
opens that section or file and scrolls to it. Graph nodes and machine states take
`link`. The builder fails on an unknown target. Link the nodes a reader would want to
read next.

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

### Splitting a file

When one file holds changes that belong to different steps of the story, list it in
each of those sections with the `hunks` that belong there. For example, `client.ts`
adds a helper in hunk 1 and adopts it in hunks 2 and 3:

```json
{"id": "helper", "files": [{"path": "src/client.ts", "hunks": [1], "note": "The new helper."}]},
{"id": "adopt", "files": [{"path": "src/client.ts", "hunks": [2, 3], "note": "Each call now uses it."}]}
```

- Hunks are numbered from 1 in the order of `git diff -U4 <base> <head> -- <path>`.
  Count its `@@` lines. A wrong number makes the builder exit and list the file's hunks.
- Between them, a file's entries must cover every hunk exactly once, and a section lists
  a file only once.
- Each part has its own card, reviewed checkbox, `note` and `lines`, and shows "Part 1 of
  2". A link to the path goes to the first part.
- Split only when it helps the story. A file whose changes are one idea stays whole.

### Fixtures

Test and eval data files hold no logic to review line by line, and many are binary. List
them in the section whose tests or evals use them:

```json
"fixtures": {
  "summary": "Sample contracts the clause-extraction eval runs on, one per edge case.",
  "files": [
    {"path": "evals/data/nda-redlined.docx", "note": "An NDA with tracked changes in clause 4."},
    {"path": "tests/fixtures/scans/", "note": "Scanned PDFs with no text layer."}
  ]
}
```

- Use it for sample documents, images, audio, recorded responses, golden outputs,
  eval datasets and other data the tests load. Test code and helpers stay in `files`.
- `summary` is one or two HTML sentences: what the data is and which tests or evals use it.
- `files` holds paths, or `{path, note}` objects. A path ending in `/` covers every
  changed file under it, and they share its `note`. `note` says what the file holds and
  why the tests need it.
- The page shows a collapsed Fixtures card in the section head: each file's change,
  its line counts or "binary", its size, and its note. There's no diff, line note or
  reviewed box, and fixtures don't count toward the section's lines.
- A fixture must be a changed file, in one section only, and not also in `files`. The
  builder fails otherwise.

### Test rows

```json
{"file": "src/feed/GroupedCard.test.tsx",
 "name": "GroupedCard › opens a clicked row and tracks its position",
 "summary": "Clicking a row opens it and tracks its position.",
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
- `name` takes the form "describe › test", using the real names from the source. The
  page shows it on hover over the summary.
- `summary` is what the Test column shows: a short HTML phrase, under ten words, on
  what the test checks, in plain words rather than the test's own name.
- `inputs` covers fixture sizes, props, mocked providers, cache contents and user
  actions. List the cases of an `.each`.
- `expected` covers the concrete assertions: calls and their arguments, ARIA roles
  and states, event names and properties, counts.
- `why` ties the change to the PR. Say "rename only" when that's all it is. A removed
  row names the test that replaces it.
- `file` must be one of the section's files. The row shows in a Tests table on that
  file's card, above its diff.

## Writing rules

### Story

- The guide is one story. The overview summary sets it up: the problem, the fix, and
  the path through the sections. Each section is the next step, and its `bridge` says
  how it follows from the last one.
- Introduce a function, type or term before any section relies on it. If a later
  section needs it first, move that section.
- Keep each section to one idea. Split a section that needs "and" in its title, or that
  goes past about 8 files or 400 changed lines.
- Split a file across sections when its changes belong to different steps of the story.
  See "Splitting a file".
- Say what's surprising or risky at the point the reader meets it, not in a list at the
  end.

### Readability

A person reads this, often between other work. Make every part easy to take in.

- One idea per paragraph, bullet, change item, file note and line note. Split an item
  that covers two.
- Keep sentences under about 25 words. Keep a file note to one or two sentences, a
  line note to one to three, and a caption to one.
- Break a complex change into steps the reader can check one at a time. A numbered
  list of steps beats a long paragraph. A diagram beats either when things move or
  branch.
- Lead with the point. Use short sentences, active voice and real names.
- Keep technical terms, and define a library or domain term in one clause the first
  time it appears. Wrap the term in `<abbr title="…">` with a one-sentence definition,
  such as `<abbr title="RTK Query's store of fetched data, keyed by endpoint and arguments">RTK Query cache</abbr>`.
  The page shows it as a dotted term with a tooltip, on hover and keyboard focus. Use
  it in any HTML field, and again wherever a later reader might have skipped the first
  definition.
- Use emojis as signposts, at most one per item, at the start: ⚠️ a risk or gap, 🐛 a
  bug fix, 🔒 auth or permissions, ⚡ performance, 💥 a breaking change, 🧪 test-only,
  🧹 cleanup, 🗄️ data or schema, 🎨 UI. Don't use them as decoration, and don't repeat
  the ones the page adds itself (impact, change type and test type pills, and headings).
- Prefer plain words to jargon. When jargon is the right word, define it once.
- Use the same name for the same thing everywhere: in titles, notes, diagrams and tests.
- Never claim something you haven't checked in the code. When unsure, read the file.
- Keep customer and personal data out of the page. It's shareable.
