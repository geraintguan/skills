---
name: comment-cleaner
description: >-
  Evaluates and removes low-value, redundant code comments — the kind that just
  restate what the code already says — while preserving comments that carry real
  information. Where a comment held useful context, it refactors variable/function
  names so the code documents itself, and only keeps the comment when naming can't
  capture it. Use this whenever the user wants to clean up, prune, strip, trim, or
  reduce comments; says there are "too many comments", the comments are "noise",
  "obvious", or "AI-generated/LLM clutter"; or asks to de-clutter a diff before
  committing or opening a PR. Trigger it even when the user doesn't say the word
  "comment" but clearly wants over-explained code tightened up.
---

# Comment Cleaner

LLM-written code tends to over-comment: a `// loop through users` above the loop,
a `# increment counter` next to `i += 1`, a comment restating the function it sits
above. These comments add nothing — the code already says it — and they rot,
because they don't change when the code does. Your job is to remove that noise
*without* destroying the comments that genuinely help a future reader.

The guiding principle: **a comment earns its place only if it tells the reader
something the code cannot.** When the missing information is just a better name,
the right fix isn't to keep the comment — it's to fix the name and delete the
comment. When the information truly can't live in a name (a reason, a caveat, a
link), the comment stays.

## Workflow

### 1. Determine scope and get the material

**If the request already names the scope** — specific files, or "the changes from
this task" — operate on exactly that and skip auto-detection. (The bundled Stop
hook does this: it hands you the list of files the task changed so cleanup stays
proportional to the work, rather than expanding to the whole codebase.) Otherwise,
auto-detect with the resolver below.

Run the bundled scope resolver (it sits next to this skill at `scripts/scope.sh`).
It encodes the scope contract deterministically (so the diff range and merge-base
are always right) and emits exactly what to review — plain `git` + `sh`, no
language runtime required:

```bash
sh <skill-dir>/scripts/scope.sh
```

It prints a `SCOPE:` line, a `BASE:` line, then the material, matching this
contract:

- **Staged files exist** → `SCOPE: staged`, followed by `---DIFF---`. Only review
  comments **added** in the staged diff.
- **Else, on a non-default branch** → `SCOPE: branch`, followed by `---DIFF---` of
  this branch's commits vs. the merge-base with the default branch. Only review
  comments **added** by the branch.
- **Else (on the default branch, nothing staged)** → `SCOPE: all`, followed by
  `---FILES---`, a list of every tracked file. **Every** comment in those files is
  in scope.

For the diff scopes, work only on comments sitting on **added (`+`) lines** — the
context lines (no prefix) and removed (`-`) lines are there to help you judge and
must stay untouched. For the `all` scope, read the listed files and review every
comment. The diff includes context lines so you can judge each comment in place;
when you refactor or delete, open the actual file with Edit. If the diff is empty
or no comments are in scope, tell the user there's nothing to clean up and stop.

### 2. Judge each comment

Read the file around each candidate (you need the surrounding code to judge it).
Sort each comment into one of four buckets:

**Preserve — never touch these:**
- *Functional directives* that change behavior or tooling: `eslint-disable`,
  `// @ts-expect-error`, `# type: ignore`, `# noqa`, `# pragma`, `// nolint`,
  `prettier-ignore`, shebangs (`#!/...`), encoding lines, build tags.
- *Doc / API comments*: docstrings, JSDoc/TSDoc, Javadoc, XML-doc, rustdoc, and
  any comment documenting a public/exported symbol that tools or consumers read.
- *TODO / FIXME / HACK / XXX / BUG* notes and *legal/license/copyright* headers.
- *Genuine "why" comments*: a non-obvious reason, a workaround and the bug it
  dodges, a performance rationale, a warning about a gotcha, a spec/issue link,
  an explanation of something surprising in the domain or an external API.

**Remove — delete the comment:**
- Restatements of the code: `// constructor`, `# increment i` over `i += 1`,
  `// return the result`, a banner that just names the obvious next block.
- Comments that paraphrase a self-explanatory function signature or variable.
- Redundant section dividers and decorative separators that carry no information.
- Commented-out code added in this diff — it's noise. (Remove it, but list it in
  the report so the user can object if they parked it there on purpose.)

For an inline comment, delete only the comment and keep the code on the line. For
a standalone comment, delete the whole line. Never leave a block syntactically
broken (e.g. don't delete the only statement in a body and leave an empty block).

**Refactor, then remove — this is the valuable case:**
When a comment supplies context that the code *lacks but a name could hold*, move
the information into the name and drop the comment. Examples:

| Before | After |
| --- | --- |
| `d = 7  # retention in days` | `retention_days = 7` |
| `// wait 3 times before giving up`<br>`for (let i = 0; i < 3; i++)` | `const MAX_RETRIES = 3;`<br>`for (let i = 0; i < MAX_RETRIES; i++)` |
| `t = 0.8  # similarity cutoff` | `similarity_cutoff = 0.8` |
| `def proc(x):  # x is a raw user-supplied email` | `def normalize_email(raw_email):` |

Rename **every** reference within the symbol's scope so the code still compiles —
use Edit/Grep to find them. Keep the change tight and local. If the rename would
escape into risky territory — a public/exported API, a serialized field name, a
symbol referenced across many files, or anywhere a collision could occur — **don't
force it.** Fall back to keeping the comment and reporting it (next bucket). A
wrong rename is far worse than one surviving comment.

**Keep + report — useful but unnameable:**
Some context simply can't fit in a name: *"the vendor's API returns HTTP 200 even
on failure, so we check the body"*, *"ordering matters here — auth must run before
the cache warms"*. Leave these in place and list them, so the user knows why they
survived and can confirm your call.

### 3. Apply and report

Edit the files in place. Then give the user a concise summary so they can review
with `git diff` (don't re-print whole files):

```
Scope: <staged | branch vs <default> | entire codebase>

Removed (N): comments that only restated the code
  - path/to/file.py:42  "# increment the counter"
  - ...

Refactored (N): context moved into names, comment dropped
  - path/to/file.ts:13  d → retentionDays  (was "// retention in days")
  - ...

Kept (N): real context a name can't capture
  - path/to/api.go:88  "// vendor returns 200 even on failure; check body"
  - ...
```

If you kept comments only because a safe refactor wasn't possible (not because the
context was inherently unnameable), call that out explicitly — that's the case the
user most wants to know about, and they may choose to restructure the code with you.

## Notes

- The resolver only decides scope and hands you the diff/files — identifying
  comments is on you. That's deliberate: you handle strings, block comments,
  inline vs. standalone, and any language far better than a regex would.
- Stay strictly within scope. On a branch or staged run, don't remove comments
  that were already there before this work — only the ones the diff added.
- When genuinely unsure whether a comment carries weight, keep it. The cost of a
  surviving redundant comment is small; the cost of deleting hard-won context is
  not.
