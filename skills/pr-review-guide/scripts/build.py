"""Build a PR review artifact page from a config JSON.

Usage: python3 build.py config.json out.html

See references/config.md for every key and how to write good content for it.

Config keys:
  repo_root, base (merge-base sha or ref), head (default HEAD)
  title (page <title>, 2-4 words), eyebrow, h1, lede, pr_url, store_key
  meta_extra: list of short HTML strings for the header meta row
  usage_file: path to scripts/usage.py output (relative to the config). Without it, a build inside a
              Claude Code session counts the session's tokens and cost itself. Shown in the meta row.
  groups: [{id, title, files: [path | {path, note?, lines?, hunks?}],
            file note: HTML narrating what the file's change does and why (shown above its diff)
            hunks: [1-based hunk numbers of `git diff -U4`] shows only those hunks; a file split across sections
                   lists it in each, and together the entries must cover every hunk exactly once
            lines: [{line, side: "new"|"old" (default new), text: HTML, impact?}] inline notes after that line;
                   the line must appear in the diff (an added/context line for new, removed/context for old)
            bridge: HTML sentence linking this section to the one before it (the story's next step),
            lead: optional HTML sentence (where to start),
            changes: {added|modified|deleted: [{impact: "High"|"Medium"|"Low", text: HTML}]}}]
          (legacy: note: [HTML strings] renders a plain list when changes is absent)
            tests: [{file, name, summary, change: "Added"|"Modified"|"Removed", type: "Unit"|"Integration"|"E2E",
                     inputs: HTML, expected: HTML, why: HTML}]  one row per test changed; shown in its file's card
            tests_file: path to a JSON file holding that array (relative to the config), merged into tests
            data_flow: [{title?, sequence: Sequence | graph: Graph | machine: Machine | schema: Schema, caption?: HTML}]
                       how data moves through this section's change, usually a sequence; [] opts out, a missing key warns
            state: [same flow shape, usually a machine]  the state this section adds or changes, shown in a State card
            fixtures: {summary: HTML, files: [path | dir/ | {path, note?}]}  test or eval data (documents, binaries)
                      listed with their size and a note, never diffed; a path ending in / covers every changed file under it
  skip_prefixes: changed paths deliberately left out (e.g. generated locales)
  overview (optional, rendered first): {
    summary: [HTML paragraphs: what the change does and why],
    before: [HTML bullets], after: [HTML bullets],
    graph: Graph for the architecture, diagram_caption: HTML,
    data_flow: [{title?, sequence | graph | machine | schema, caption?}]  # high-level data flow across the whole change
    state: [flows]  # the main state machines the change touches
    layout: [{path, role (HTML), group (group id)}]  # where the code lives; +/- is summed per path prefix
    decisions: [HTML bullets: key design decisions and who made them]
  }
  Graph (rendered with React Flow): {direction?: "TB"|"LR"|"BT"|"RL",
    nodes: [{id, label, detail?, group?, status?: "added"|"changed"|"removed", shape?: "decision"|"terminal"|"store", link?, tip?}],
    edges: [{from, to, label?, status?, animated?, tip?}], group_tips?: {group: text}}
  Machine (an interactive finite state machine, drawn with React Flow): {direction?, initial?: state id (default the first),
    states: [{id, label, detail?, group?, status?, link?, final?, tip?}], transitions: [{from, to, event, status?, tip?}], group_tips?}
  link (graph node or state): a section id, a file path in a section, or "overview"; the node jumps there
  tip (any diagram element): plain text, shown as written on hover, saying what the element is and does; a diagram element without one warns
  diagrams: {name: flow}  diagrams for HTML fields; <div data-diagram="name"></div> in any HTML field draws one there
  Sequence (call or event order, drawn with React Flow, with step-through playback): {
    participants: [{id, label, detail?, status?, link?, tip?}],
    steps: [message | note | fragment], where
      message: {from, to, label, reply?: true (dashed return), status?, tip?}
      note: {note: text, over: [one or two participant ids], status?, tip?}
      fragment: {loop: condition, steps} | {opt: condition, steps} | {alt: [{when: condition, steps, tip?}], status?, tip?}}
  Schema (an entity-relationship diagram, drawn with React Flow): {direction? (default "LR"),
    entities: [{id, label, detail?, group?, status?, link?, tip?, fields: [{name, type?, key?: "PK"|"FK"|"UK", status?, tip?}]}],
    relations: [{from, to, label?, cardinality?: "1:1"|"1:N"|"N:1"|"N:N", status?, tip?}], group_tips?}
Every diagram is drawn with React Flow.
The script fails if a changed file is in no group and not skipped.
"""
import functools, html, json, re, subprocess, sys, pathlib
from collections import defaultdict
from typing import Any, Optional

import usage

cfg_path = pathlib.Path(sys.argv[1])
cfg = json.loads(cfg_path.read_text())
for g in cfg["groups"]:
    g["files"] = [{"path": e} if isinstance(e, str) else e for e in g["files"]]
out_path = pathlib.Path(sys.argv[2])
root, base, head = cfg.get("repo_root", "."), cfg["base"], cfg.get("head", "HEAD")

def git(*args):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout

@functools.cache
def file_diff(path: str) -> str:
    return git("diff", "-U4", base, head, "--", path)

def load_relative_json(path: str) -> Any:
    return json.loads((cfg_path.parent / path).read_text())

def diff_lines(d):
    """Line numbers shown in the diff, per side."""
    shown = {"new": set(), "old": set()}
    o = n = 0
    for line in d.splitlines():
        if line.startswith("@@"):
            parts = line.split()
            o, n = int(parts[1][1:].split(",")[0]), int(parts[2][1:].split(",")[0])
        elif line.startswith(("+++", "---", "diff ", "index ", "new file", "deleted file", "\\")):
            continue
        elif line.startswith("+"):
            shown["new"].add(n); n += 1
        elif line.startswith("-"):
            shown["old"].add(o); o += 1
        elif o or n:
            shown["old"].add(o); shown["new"].add(n); o += 1; n += 1
    return shown

Flow = dict[str, Any]
STATUSES = (None, "added", "changed", "removed")

DIAGRAM_KINDS = ("sequence", "graph", "machine", "schema")
FLOW_KEYS = {"title", "caption", *DIAGRAM_KINDS}
SHAPES = (None, "decision", "terminal", "store")
FIELD_KEYS = (None, "PK", "FK", "UK")
CARDINALITIES = (None, "1:1", "1:N", "N:1", "N:N")

def check_flow(where: str, flow: Flow) -> Flow:
    if not isinstance(flow, dict) or sum(kind in flow for kind in DIAGRAM_KINDS) != 1:
        sys.exit(f"{where}: each flow needs exactly one of {', '.join(DIAGRAM_KINDS)}")
    if flow.keys() - FLOW_KEYS:
        sys.exit(f"{where}: unknown flow keys {sorted(flow.keys() - FLOW_KEYS)}; a flow takes {sorted(FLOW_KEYS)}")
    return flow

def check_flows(where: str, flows: list[Flow]) -> list[Flow]:
    return [check_flow(where, flow) for flow in flows]

# Diagram links name a section id, a file path in a section, or "overview"; the page turns them into anchors.
link_targets = {"overview", *(g["id"] for g in cfg["groups"]),
                *(e["path"] for g in cfg["groups"] for e in g["files"])}

def check_link(where: str, target: str) -> str:
    if target not in link_targets:
        sys.exit(f"{where}: link target {target!r} is not a section id, a file in a section, or 'overview'")
    return target

def check_choice(where: str, items: list[dict[str, Any]], key: str, allowed: tuple[Optional[str], ...]) -> None:
    for item in items:
        if item.get(key) not in allowed:
            sys.exit(f"{where}: {key} must be {' or '.join(filter(None, allowed))}: {item}")

def check_nodes(where: str, nodes: list[dict[str, Any]], noun: str) -> set[str]:
    """Checks the boxes of a graph, machine or sequence: unique ids, labels, statuses and links. Returns the ids."""
    ids = {n.get("id") for n in nodes}
    if not nodes or len(ids) != len(nodes) or None in ids or not all(n.get("label") for n in nodes):
        sys.exit(f"{where}: needs {noun}s, each with a unique id and a label")
    check_choice(where, nodes, "status", STATUSES)
    for n in nodes:
        if n.get("link"):
            check_link(f"{where} {noun} {n['id']}", n["link"])
    return ids

def check_ends(where: str, items: list[dict[str, Any]], ids: set[str], noun: str) -> None:
    for item in items:
        if item.get("from") not in ids or item.get("to") not in ids:
            sys.exit(f"{where}: {noun} {item.get('from')} -> {item.get('to')} names an unknown id")

def check_graph(where: str, graph: dict[str, Any]) -> dict[str, Any]:
    """Validates a React Flow graph, including each node's link."""
    nodes, edges = graph.get("nodes") or [], graph.get("edges") or []
    if graph.get("direction", "TB") not in ("TB", "LR", "BT", "RL"):
        sys.exit(f"{where}: graph direction must be TB, LR, BT or RL")
    check_ends(where, edges, check_nodes(where, nodes, "node"), "edge")
    check_choice(where, edges, "status", STATUSES)
    check_choice(where, nodes, "shape", SHAPES)
    unknown = (graph.get("group_tips") or {}).keys() - {n.get("group") for n in nodes}
    if unknown:
        sys.exit(f"{where}: group_tips names groups no node is in: {sorted(unknown)}")
    return graph

def with_display(edge: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    return {**edge, **{k: source[k] for k in ("status", "tip") if k in source}}

def transition_edge(where: str, t: dict[str, Any]) -> dict[str, Any]:
    if not t.get("event"):
        sys.exit(f"{where}: every machine transition needs an event")
    return with_display({"from": t.get("from"), "to": t.get("to"), "label": t["event"]}, t)

def machine_graph(where: str, machine: dict[str, Any]) -> dict[str, Any]:
    """A state machine as a graph: states are nodes, transitions are edges labelled with their event."""
    states = machine.get("states") or [{}]
    initial = machine.get("initial") or states[0].get("id")
    if initial not in {st.get("id") for st in states}:
        sys.exit(f"{where}: machine initial state {initial!r} is not one of its states")
    return {"direction": machine.get("direction", "LR"), "machine": {"initial": initial}, **group_tips(machine),
            "nodes": [{**st, "initial": st.get("id") == initial} for st in states],
            "edges": [transition_edge(where, t) for t in machine.get("transitions") or []]}

def group_tips(spec: dict[str, Any]) -> dict[str, Any]:
    return {"group_tips": spec["group_tips"]} if "group_tips" in spec else {}

def check_fields(where: str, entity: dict[str, Any]) -> None:
    fields = entity.get("fields") or []
    if not all(isinstance(f, dict) and f.get("name") for f in fields):
        sys.exit(f"{where}: every field of entity {entity['id']} needs a name")
    check_choice(where, fields, "key", FIELD_KEYS)
    check_choice(where, fields, "status", STATUSES)

def relation_edge(r: dict[str, Any]) -> dict[str, Any]:
    label = " ".join(filter(None, (r.get("label"), r.get("cardinality"))))
    return with_display({"from": r.get("from"), "to": r.get("to"), **({"label": label} if label else {})}, r)

def schema_graph(where: str, schema: dict[str, Any]) -> dict[str, Any]:
    """An ER diagram as a graph: entities are nodes listing their fields, relations are edges labelled with their cardinality."""
    entities, relations = schema.get("entities") or [], schema.get("relations") or []
    check_ends(where, relations, check_nodes(where, entities, "entity"), "relation")
    check_choice(where, relations, "cardinality", CARDINALITIES)
    for entity in entities:
        check_fields(where, entity)
    return {"direction": schema.get("direction", "LR"), "schema": True, **group_tips(schema),
            "nodes": entities, "edges": [relation_edge(r) for r in relations]}

GRAPH_BUILDERS = {"graph": lambda where, graph: graph, "machine": machine_graph, "schema": schema_graph}

has_diagram = False

FRAGMENTS = ("loop", "opt")

def check_message(where: str, step: dict[str, Any], ids: set[str]) -> None:
    check_ends(where, [step], ids, "message")
    if not step.get("label"):
        sys.exit(f"{where}: every sequence message needs a label")

def check_note(where: str, step: dict[str, Any], ids: set[str]) -> None:
    over = step.get("over")
    if not isinstance(over, list) or not 1 <= len(over) <= 2 or not set(over) <= ids:
        sys.exit(f"{where}: a note goes over one or two known participants: {step}")

def check_fragment(where: str, step: dict[str, Any], ids: set[str]) -> None:
    kinds = [k for k in ("alt", *FRAGMENTS) if k in step]
    if len(kinds) != 1:
        sys.exit(f"{where}: a sequence step is a message, a note, or one of alt, loop or opt: {step}")
    arms = step["alt"] if kinds == ["alt"] else [{"when": step[kinds[0]], "steps": step.get("steps")}]
    if not isinstance(arms, list) or not arms:
        sys.exit(f"{where}: an alt needs a list of {{when, steps}} branches: {step}")
    for branch in arms:
        if not branch.get("when"):
            sys.exit(f"{where}: every {kinds[0]} needs a condition: {step}")
        check_steps(where, branch.get("steps"), ids)

def check_steps(where: str, steps: Any, ids: set[str]) -> None:
    if not isinstance(steps, list) or not steps:
        sys.exit(f"{where}: a sequence, and every fragment in one, needs a list of steps")
    check_choice(where, steps, "status", STATUSES)
    for step in steps:
        if "from" in step:
            check_message(where, step, ids)
        elif "note" in step:
            check_note(where, step, ids)
        else:
            check_fragment(where, step, ids)

def check_sequence(where: str, seq: dict[str, Any]) -> dict[str, Any]:
    """Validates a sequence: its participants like graph nodes, and every step against them."""
    ids = check_nodes(where, seq.get("participants") or [], "participant")
    check_steps(where, seq.get("steps"), ids)
    return seq

def branches(step: dict[str, Any]) -> list[dict[str, Any]]:
    """A fragment's branches: an alt's list, or the one body of a loop or opt."""
    return step["alt"] if "alt" in step else [step]

def all_sequence_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every message, note and fragment, depth first."""
    found = []
    for step in steps:
        found.append(step)
        if "from" not in step and "note" not in step:
            found += [s for b in branches(step) for s in all_sequence_steps(b["steps"])]
    return found

def element_name(item: dict[str, Any]) -> str:
    if "from" in item:
        return f"{item['from']} -> {item['to']}" + (f" ({item['label']})" if item.get("label") else "")
    if "when" in item:
        return f"alt [{item['when']}]"
    return str(item["id"]) if "id" in item else next(f"{k} [{item[k]}]" for k in FRAGMENTS if k in item)

def sequence_parts(step: dict[str, Any]) -> list[dict[str, Any]]:
    """What a reader hovers for one step: a message, a loop or opt, or each branch of an alt. Notes are already text."""
    return [] if "note" in step else branches(step)

def diagram_elements(kind: str, data: dict[str, Any]) -> list[dict[str, Any]]:
    """The elements that need a tip: boxes, arrows and fragments. Groups take theirs from group_tips."""
    if kind == "sequence":
        return data["participants"] + [part for s in all_sequence_steps(data["steps"]) for part in sequence_parts(s)]
    return data["nodes"] + data["edges"]

def optional_tips(kind: str, data: dict[str, Any]) -> list[dict[str, Any]]:
    """Notes, whole alts and schema fields may take a tip but don't need one."""
    if kind == "sequence":
        return [s for s in all_sequence_steps(data["steps"]) if "note" in s or "alt" in s]
    return [f for n in data["nodes"] for f in n.get("fields") or []]

def check_tips(where: str, kind: str, data: dict[str, Any]) -> bool:
    """Fails on an empty or non-string tip, and warns about elements a reader can't hover for an explanation.
    Returns whether the diagram has any tips, so the page can say to hover."""
    elements, group_tips = diagram_elements(kind, data), data.get("group_tips") or {}
    tips = [item["tip"] for item in elements + optional_tips(kind, data) if "tip" in item] + list(group_tips.values())
    if not all(isinstance(tip, str) and tip.strip() for tip in tips):
        sys.exit(f"{where}: every tip must be non-empty plain text")
    groups = sorted({n["group"] for n in data.get("nodes", []) if n.get("group")} - group_tips.keys())
    missing = [element_name(e) for e in elements if not e.get("tip")] + [f"group {g}" for g in groups]
    if missing:
        shown = ", ".join(missing[:5]) + (f" and {len(missing) - 5} more" if len(missing) > 5 else "")
        print(f"warning: {where}: {len(missing)} diagram element(s) have no tip: {shown}", file=sys.stderr)
    return bool(tips)

def render_diagram(where: str, spec: Flow) -> str:
    """A React Flow placeholder: a sequence, or a graph built from a graph, machine or schema."""
    global has_diagram
    has_diagram = True
    if "sequence" in spec:
        kind, data = "sequence", check_sequence(where, spec["sequence"])
    else:
        source = next(k for k in GRAPH_BUILDERS if k in spec)
        kind, data = "graph", check_graph(where, GRAPH_BUILDERS[source](where, spec[source]))
    data = {**data, "has_tips": check_tips(where, kind, data)}
    return f'<div class="rf-diagram" data-kind="{kind}" data-spec="{html.escape(json.dumps(data))}"></div>'

def render_flow(where: str, flow: Flow) -> str:
    """Title, diagram and caption of one flow, shared by the overview and the sections."""
    title = f'<h4 class="flow-title">{flow["title"]}</h4>' if flow.get("title") else ""
    cap = f'<p class="ov-caption">{flow["caption"]}</p>' if flow.get("caption") else ""
    return f'{title}{render_diagram(where, flow)}{cap}'

DIAGRAM_REF = re.compile(r'<div data-diagram="([^"]+)"></div>')
named_diagrams = {name: render_flow(f"diagram {name}", check_flow(f"diagram {name}", flow))
                  for name, flow in cfg.get("diagrams", {}).items()}
used_diagrams: set[str] = set()

def embed_diagram(where: str, match: re.Match) -> str:
    name = match.group(1)
    if name not in named_diagrams:
        sys.exit(f"{where}: no diagram named {name!r} in diagrams")
    used_diagrams.add(name)
    return named_diagrams[name]

def embed_diagrams(where: str, value: Any) -> Any:
    """Draws each <div data-diagram="name"></div> in the config's HTML strings."""
    if isinstance(value, dict):
        return {k: embed_diagrams(where, v) for k, v in value.items()}
    if isinstance(value, list):
        return [embed_diagrams(where, v) for v in value]
    if not isinstance(value, str) or "<" not in value:
        return value
    return DIAGRAM_REF.sub(lambda m: embed_diagram(where, m), value)

OVERVIEW_LISTS = ("summary", "before", "after", "decisions")

def check_lists(where: str, section: dict[str, Any], keys: tuple[str, ...]) -> None:
    """A string where a list belongs renders one character per item, such as a paragraph per letter."""
    for key in keys:
        if key in section and not (isinstance(section[key], list) and all(isinstance(item, str) for item in section[key])):
            sys.exit(f"{where}: {key} must be a list of strings, one per item, not {type(section[key]).__name__}")

check_lists("overview", cfg.get("overview") or {}, OVERVIEW_LISTS)
check_lists("config", cfg, ("meta_extra", "skip_prefixes"))
cfg["groups"] = [embed_diagrams(g["id"], g) for g in cfg["groups"]]
if cfg.get("overview"):
    cfg["overview"] = embed_diagrams("overview", cfg["overview"])
for name in named_diagrams.keys() - used_diagrams:
    print(f"warning: diagram {name!r} is never used; put <div data-diagram=\"{name}\"></div> in an HTML field", file=sys.stderr)

def check_line_notes(path, d, notes):
    shown = diff_lines(d)
    for note in notes:
        side = note.get("side", "new")
        if note["line"] not in shown.get(side, ()):
            sys.exit(f"{path}: line note at {side} line {note['line']} is not in the diff")
        if note.get("impact") not in (None, "High", "Medium", "Low"):
            sys.exit(f"{path}: bad impact {note.get('impact')}")
    return notes

# Past either size a section usually covers more than one idea, which is hard to review in one sitting.
SECTION_MAX_FILES, SECTION_MAX_LINES = 8, 400

def split_hunks(d: str) -> tuple[str, list[str]]:
    """The file header and each hunk of a one-file diff."""
    header, *hunks = re.split(r"^(?=@@)", d, flags=re.M)
    return header, hunks

def check_hunk_numbers(path: str, hunks: list[str], picked: list[int]) -> None:
    bad = [n for n in picked if not isinstance(n, int) or not 1 <= n <= len(hunks)]
    if bad or not picked:
        listing = "\n  ".join(f"{i}: {h.splitlines()[0]}" for i, h in enumerate(hunks, 1))
        sys.exit(f"{path}: hunks must be numbers from 1 to {len(hunks)}, got {bad or picked}. Its hunks:\n  {listing}")

Entries = list[tuple[str, dict[str, Any]]]

def check_hunk_coverage(path: str, entries: Entries) -> None:
    hunks = split_hunks(file_diff(path))[1]
    for _, spec in entries:
        check_hunk_numbers(path, hunks, spec["hunks"])
    picked = sorted(n for _, spec in entries for n in spec["hunks"])
    if picked != list(range(1, len(hunks) + 1)):
        sys.exit(f"{path}: its entries must cover hunks 1 to {len(hunks)} once each, got {picked}")

def check_split_files(entries_by_path: dict[str, Entries]) -> None:
    """A file listed in more than one section must share out its hunks, each to exactly one section."""
    for path, entries in entries_by_path.items():
        group_ids = [group_id for group_id, _ in entries]
        if len(set(group_ids)) != len(group_ids):
            sys.exit(f"{path}: listed twice in one section; give that entry all the hunks it needs")
        if len(entries) == 1 and "hunks" not in entries[0][1]:
            continue
        if any("hunks" not in spec for _, spec in entries):
            sys.exit(f"{path}: is split across sections {group_ids}, so every entry for it needs hunks")
        check_hunk_coverage(path, entries)

entries_by_path: dict[str, Entries] = defaultdict(list)
for g in cfg["groups"]:
    for spec in g["files"]:
        entries_by_path[spec["path"]].append((g["id"], spec))
        spec["part"] = len(entries_by_path[spec["path"]])
check_split_files(entries_by_path)

@functools.cache
def changed_files() -> dict[str, dict[str, Any]]:
    """Each changed path's status (A, D or M) and line counts, from one diff; git counts binary files as "-"."""
    status, counts = {}, {}
    for line in git("diff", "--raw", "--numstat", "--no-renames", base, head).splitlines():
        if line.startswith(":"):
            meta, path = line.split("\t", 1)
            status[path] = meta.split()[-1][0]
        else:
            add, rem, path = line.split("\t", 2)
            counts[path] = (add, rem)
    return {path: dict(status=st if st in "ADM" else "M", binary=counts[path][0] == "-",
                       add=int(counts[path][0]) if counts[path][0] != "-" else 0,
                       rem=int(counts[path][1]) if counts[path][1] != "-" else 0)
            for path, st in status.items()}

def blob_sizes(specs: list[str]) -> list[Optional[int]]:
    """Sizes of `ref:path` blobs in one git call; None for a blob that doesn't exist."""
    out = subprocess.run(["git", "cat-file", "--batch-check=%(objectsize)"], cwd=root, input="\n".join(specs) + "\n",
                         capture_output=True, text=True, check=True).stdout.splitlines()
    return [int(line) if line.isdigit() else None for line in out]

def fixture_paths(where: str, path: str) -> list[str]:
    if path.endswith("/"):
        matches = sorted(f for f in changed_files() if f.startswith(path))
    else:
        matches = [path] if path in changed_files() else []
    if not matches:
        sys.exit(f"{where}: fixture {path!r} matches no changed file")
    return matches

def fixture_rows(notes: dict[str, Optional[str]]) -> list[dict[str, Any]]:
    """One row per fixture path, with its size at head, or at base for a deleted file."""
    rows = [dict(path=path, note=note, **changed_files()[path]) for path, note in notes.items()]
    sizes = blob_sizes([f"{base if r['status'] == 'D' else head}:{r['path']}" for r in rows])
    return [{**row, "size": size} for row, size in zip(rows, sizes)]

def check_fixtures(where: str, fixtures: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Expands fixture entries to the changed files they cover. Fixtures get a row each, but no diff."""
    if not fixtures:
        return None
    entries = [{"path": e} if isinstance(e, str) else e for e in fixtures.get("files") or []]
    if not entries or fixtures.keys() - {"summary", "files"}:
        sys.exit(f"{where}: fixtures takes {{summary, files}} with at least one file")
    if not fixtures.get("summary"):
        print(f"warning: section {where} fixtures have no summary saying what the data is for", file=sys.stderr)
    notes = {p: e.get("note") for e in entries for p in fixture_paths(where, e["path"])}
    return {"summary": fixtures.get("summary"), "files": fixture_rows(notes)}

fixture_owner: dict[str, str] = {}

def claim_fixtures(group_id: str, fixtures: Optional[dict[str, Any]]) -> None:
    for row in fixtures["files"] if fixtures else []:
        path = row["path"]
        if path in entries_by_path or path in fixture_owner:
            other = fixture_owner.get(path) or "a section's files"
            sys.exit(f"{path}: listed as a fixture in {group_id} and also in {other}")
        fixture_owner[path] = group_id

groups = []
for g in cfg["groups"]:
    fixtures = check_fixtures(g["id"], g.get("fixtures"))
    claim_fixtures(g["id"], fixtures)
    files = []
    for spec in g["files"]:
        f, part = spec["path"], spec["part"]
        d = file_diff(f)
        if not d:
            sys.exit(f"no diff for {f}")
        header, hunks = split_hunks(d)
        if "hunks" in spec:
            hunks = [hunks[n - 1] for n in sorted(spec["hunks"])]
        d = header + "".join(hunks)
        status = "A" if "\nnew file mode" in header else "D" if "\ndeleted file mode" in header else "M"
        lines = d.splitlines()
        files.append(dict(
            path=f, key=f if part == 1 else f"{f}#{part}", part=part, parts=len(entries_by_path[f]),
            status=status,
            add=sum(l.startswith("+") and not l.startswith("+++") for l in lines),
            rem=sum(l.startswith("-") and not l.startswith("---") for l in lines),
            diff="".join(hunks),
            test=".test." in f or "/tests/" in f or "/test_" in f,
            story=".stories." in f,
            note=spec.get("note"),
            lines=check_line_notes(f, d, spec.get("lines", [])),
        ))
    tests = list(g.get("tests", []))
    if g.get("tests_file"):
        tests += load_relative_json(g["tests_file"])
    group_paths = {f["path"] for f in files}
    rows_by_file = defaultdict(list)
    for row in tests:
        missing_keys = {"file", "name", "summary", "change", "type", "inputs", "expected", "why"} - row.keys()
        if missing_keys:
            sys.exit(f"{g['id']}: test row missing {sorted(missing_keys)}: {row.get('name')}")
        if row["change"] not in ("Added", "Modified", "Removed") or row["type"] not in ("Unit", "Integration", "E2E"):
            sys.exit(f"{g['id']}: bad change/type in test row {row['name']}")
        if row["file"] not in group_paths:
            sys.exit(f"{g['id']}: test file {row['file']} is not in this group's files")
        rows_by_file[row["file"]].append(row)
    for f in files:
        f["test_rows"] = rows_by_file[f["path"]]
    g = {k: v for k, v in g.items() if k not in ("tests", "tests_file")}
    for kind, items in g.get("changes", {}).items():
        if kind not in ("added", "modified", "deleted"):
            sys.exit(f"{g['id']}: unknown change type {kind}")
        for c in items:
            if c.get("impact") not in ("High", "Medium", "Low"):
                sys.exit(f"{g['id']}: impact must be High, Medium or Low: {c}")
    if groups and not g.get("bridge"):
        print(f"warning: section {g['id']} has no bridge from the section before it", file=sys.stderr)
    if len(files) > SECTION_MAX_FILES or sum(f["add"] + f["rem"] for f in files) > SECTION_MAX_LINES:
        print(f"warning: section {g['id']} is large ({len(files)} files); split it if it holds more than one idea", file=sys.stderr)
    if "data_flow" not in g:
        print(f"warning: section {g['id']} has no data_flow; set it to [] if no data moves", file=sys.stderr)
    flows = check_flows(g["id"], g.get("data_flow", []))
    machines = check_flows(g["id"], g.get("state", []))
    groups.append({**g, "files": files, "fixtures": fixtures, "data_flow": "".join(f"<div>{render_flow(g['id'], f)}</div>" for f in flows),
                   "state": "".join(f"<div>{render_flow(g['id'], f)}</div>" for f in machines)})

skips = tuple(cfg.get("skip_prefixes", []))
missing = [f for f in git("diff", "--name-only", base, head).split() if f not in entries_by_path and f not in fixture_owner and not f.startswith(skips)]
if missing:
    sys.exit("changed files in no group:\n  " + "\n  ".join(missing))

def overview_flows(heading: str, flows: list[Flow]) -> str:
    if not check_flows("overview", flows):
        return ""
    return (f'<div><h3>{heading}</h3><div class="ov-flows">'
            + "".join(f'<div class="ov-diagram">{render_flow("overview", f)}</div>' for f in flows) + "</div></div>")

def render_overview(ov):
    if not ov:
        return ""
    def bullets(items):
        return "".join(f"<li>{i}</li>" for i in items)
    def stat(prefix):
        fs = [f for g in groups for f in g["files"] if f["path"].startswith(prefix)]
        return f'<span class="plus">+{sum(f["add"] for f in fs)}</span> <span class="minus">−{sum(f["rem"] for f in fs)}</span>'
    for key in ("summary", "before", "after", "decisions"):
        if isinstance(ov.get(key), str):
            sys.exit(f"overview.{key} must be a list of HTML strings, not one string")
    parts = ['<section class="overview" id="overview"><h2>Overview</h2>']
    if ov.get("summary"):
        parts.append('<div class="ov-summary">' + "".join(f"<p>{p}</p>" for p in ov["summary"]) + "</div>")
    if ov.get("before") or ov.get("after"):
        parts.append('<div class="ov-ba">'
                     f'<div class="ov-card before"><h3>Before</h3><ul>{bullets(ov.get("before", []))}</ul></div>'
                     f'<div class="ov-card after"><h3>After</h3><ul>{bullets(ov.get("after", []))}</ul></div></div>')
    if ov.get("graph"):
        arch = {"graph": ov["graph"], "caption": ov.get("diagram_caption")}
        parts.append(f'<div><h3>Architecture</h3><div class="ov-diagram">{render_flow("overview", arch)}</div></div>')
    parts += [overview_flows(heading, ov.get(key, [])) for heading, key in (("Data flow", "data_flow"), ("State", "state"))]
    if ov.get("layout"):
        rows = "".join(
            f'<tr><td class="p"><a href="#{r["group"]}">{html.escape(r["path"])}</a></td><td>{r["role"]}</td><td class="s">{stat(r["path"])}</td></tr>'
            for r in ov["layout"])
        parts.append(f'<div><h3>Code layout</h3><div class="ov-layout"><table><thead><tr><th>Where</th><th>What it does in this PR</th><th>Lines</th></tr></thead><tbody>{rows}</tbody></table></div></div>')
    if ov.get("decisions"):
        parts.append(f'<div><h3>Key decisions</h3><ul class="ov-decisions">{bullets(ov["decisions"])}</ul></div>')
    parts.append("</section>")
    return "".join(parts)

def compact(n: int) -> str:
    for size, suffix in ((1_000_000, "M"), (1_000, "k")):
        if n >= size:
            return f"{n / size:.1f}{suffix}"
    return str(n)

def build_usage() -> Optional[dict[str, Any]]:
    """The config's usage_file if set, else this session's usage so far, else None."""
    if cfg.get("usage_file"):
        return load_relative_json(cfg["usage_file"])
    transcript = usage.current_transcript()
    return usage.collect(transcript) if transcript else None

def render_usage(u: dict[str, Any]) -> str:
    """Header meta item for the tokens and estimated cost of building this guide."""
    t = u["tokens"]
    breakdown = "\n".join([
        f"{u['requests']} model requests across the main session and {u['subagents']} subagents",
        f"Input {t['input']:,} · cache write {t['cache_write_5m'] + t['cache_write_1h']:,} · cache read {t['cache_read']:,} · output {t['output']:,}",
        *(f"{m['model']}: {m['tokens']['total']:,} tokens, "
          + ("no price" if m["cost_usd"] is None else f"${m['cost_usd']:.2f}") for m in u["by_model"]),
        f"Estimate at {u['pricing']}.",
    ])
    cost = f"~${u['cost_usd']:.2f}" + ("+" if u["unpriced_models"] else "")
    return (f'<span class="usage" title="{html.escape(breakdown)}">Guide built with '
            f'<b>{compact(t["total"])}</b> tokens · <b>{cost}</b></span>')

def js(value):
    return json.dumps(value).replace("</", "<\\/")

build_cost = build_usage()
meta = cfg.get("meta_extra", []) + ([render_usage(build_cost)] if build_cost else [])
assets = pathlib.Path(__file__).resolve().parent.parent / "assets"
tpl = (assets / "template.html").read_text()
overview = render_overview(cfg.get("overview"))
for key, value in {
    "__TITLE__": html.escape(cfg["title"]), "__EYEBROW__": cfg["eyebrow"], "__H1__": cfg["h1"],
    "__LEDE__": cfg["lede"], "__OVERVIEW__": overview, "__PR_URL__": cfg["pr_url"], "__STORE_KEY__": cfg["store_key"],
}.items():
    tpl = tpl.replace(key, value)
tpl = tpl.replace("/*__XYFLOW_CSS__*/", (assets / "xyflow.css").read_text() if has_diagram else "")
tpl = tpl.replace("/*__DATA__*/null", js(groups)).replace("/*__META__*/[]", js(meta))
out_path.write_text(tpl)
print(f"wrote {out_path} ({len(tpl)} bytes, {sum(len(g['files']) for g in groups)} files)")
