"""Build a PR review artifact page from a config JSON.

Usage: python3 build.py config.json out.html

See references/config.md for every key and how to write good content for it.

Config keys:
  repo_root, base (merge-base sha or ref), head (default HEAD)
  title (page <title>, 2-4 words), eyebrow, h1, lede, pr_url, store_key
  meta_extra: list of short HTML strings for the header meta row
  usage_file: path to scripts/usage.py output (relative to the config). Without it, a build inside a
              Claude Code session counts the session's tokens and cost itself. Shown in the meta row.
  groups: [{id, title, files: [path | {path, note?, lines?}],
            file note: HTML narrating what the file's change does and why (shown above its diff)
            lines: [{line, side: "new"|"old" (default new), text: HTML, impact?}] inline notes after that line;
                   the line must appear in the diff (an added/context line for new, removed/context for old)
            bridge: HTML sentence linking this section to the one before it (the story's next step),
            lead: optional HTML sentence (where to start),
            changes: {added|modified|deleted: [{impact: "High"|"Medium"|"Low", text: HTML}]}}]
          (legacy: note: [HTML strings] renders a plain list when changes is absent)
            tests: [{file, name, change: "Added"|"Modified"|"Removed", type: "Unit"|"Integration"|"E2E",
                     inputs: HTML, expected: HTML, why: HTML}]  one row per test changed; shown in its file's card
            tests_file: path to a JSON file holding that array (relative to the config), merged into tests
            data_flow: [{title?, diagram: mermaid source | graph: Graph | machine: Machine, caption?: HTML}]
                       how data moves through this section's change, usually a sequenceDiagram; [] opts out, a missing key warns
            state: [same flow shape, usually a machine]  the state this section adds or changes, shown in a State card
  skip_prefixes: changed paths deliberately left out (e.g. generated locales)
  overview (optional, rendered first): {
    summary: [HTML paragraphs: what the change does and why],
    before: [HTML bullets], after: [HTML bullets],
    graph: Graph for the architecture, diagram_caption: HTML,
    data_flow: [{title?, diagram | graph | machine, caption?}]  # high-level data flow across the whole change
    state: [flows]  # the main state machines the change touches
    layout: [{path, role (HTML), group (group id)}]  # where the code lives; +/- is summed per path prefix
    decisions: [HTML bullets: key design decisions and who made them]
  }
  Graph (rendered with React Flow): {direction?: "TB"|"LR"|"BT"|"RL",
    nodes: [{id, label, detail?, group?, status?: "added"|"changed"|"removed", shape?: "decision"|"terminal"|"store", link?}],
    edges: [{from, to, label?, status?, animated?}]}
  Machine (an interactive finite state machine, drawn with React Flow): {direction?, initial?: state id (default the first),
    states: [{id, label, detail?, group?, status?, link?, final?}], transitions: [{from, to, event, status?}]}
  link (graph node or state): a section id, a file path in a section, or "overview"; the node jumps there
  diagrams: {name: flow}  diagrams for HTML fields; <div data-diagram="name"></div> in any HTML field draws one there
Mermaid is only for sequenceDiagram and erDiagram: flowcharts are graphs and state diagrams are machines.
The script fails if a changed file is in no group and not skipped.
"""
import html, json, re, subprocess, sys, pathlib
from collections import defaultdict
from typing import Any, Optional

import usage

cfg_path = pathlib.Path(sys.argv[1])
cfg = json.loads(cfg_path.read_text())
out_path = pathlib.Path(sys.argv[2])
root, base, head = cfg.get("repo_root", "."), cfg["base"], cfg.get("head", "HEAD")

def git(*args):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout

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

DIAGRAM_KINDS = ("diagram", "graph", "machine")
FLOW_KEYS = {"title", "caption", *DIAGRAM_KINDS}
SHAPES = (None, "decision", "terminal", "store")
MERMAID_KINDS = ("sequenceDiagram", "erDiagram")

def check_mermaid(where: str, source: str) -> None:
    if source.split(maxsplit=1)[:1] not in ([k] for k in MERMAID_KINDS):
        sys.exit(f"{where}: Mermaid is only for {' and '.join(MERMAID_KINDS)}; draw anything else as a graph or a machine")

def check_flow(where: str, flow: Flow) -> Flow:
    if not isinstance(flow, dict) or sum(kind in flow for kind in DIAGRAM_KINDS) != 1:
        sys.exit(f"{where}: each flow needs exactly one of a mermaid diagram, a graph or a machine")
    if flow.keys() - FLOW_KEYS:
        sys.exit(f"{where}: unknown flow keys {sorted(flow.keys() - FLOW_KEYS)}; a flow takes {sorted(FLOW_KEYS)}")
    if "diagram" in flow:
        check_mermaid(where, str(flow["diagram"]))
    return flow

def check_flows(where: str, flows: list[Flow]) -> list[Flow]:
    return [check_flow(where, flow) for flow in flows]

# Diagram links name a section id, a file path in a section, or "overview"; the page turns them into anchors.
link_targets = {"overview", *(g["id"] for g in cfg["groups"]),
                *(e if isinstance(e, str) else e["path"] for g in cfg["groups"] for e in g["files"])}

def check_link(where: str, target: str) -> str:
    if target not in link_targets:
        sys.exit(f"{where}: link target {target!r} is not a section id, a file in a section, or 'overview'")
    return target

def check_graph_nodes(where: str, nodes: list[dict[str, Any]]) -> set[str]:
    ids = {n.get("id") for n in nodes}
    if not nodes or len(ids) != len(nodes) or None in ids or not all(n.get("label") for n in nodes):
        sys.exit(f"{where}: a graph needs nodes, each with a unique id and a label")
    return ids

def check_graph_edges(where: str, edges: list[dict[str, Any]], ids: set[str]) -> None:
    for e in edges:
        if e.get("from") not in ids or e.get("to") not in ids:
            sys.exit(f"{where}: graph edge {e.get('from')} -> {e.get('to')} names an unknown node")

def check_choice(where: str, items: list[dict[str, Any]], key: str, allowed: tuple[Optional[str], ...]) -> None:
    for item in items:
        if item.get(key) not in allowed:
            sys.exit(f"{where}: graph {key} must be {' or '.join(filter(None, allowed))}: {item}")

def check_graph(where: str, graph: dict[str, Any]) -> dict[str, Any]:
    """Validates a React Flow graph, including each node's link."""
    nodes, edges = graph.get("nodes") or [], graph.get("edges") or []
    if graph.get("direction", "TB") not in ("TB", "LR", "BT", "RL"):
        sys.exit(f"{where}: graph direction must be TB, LR, BT or RL")
    check_graph_edges(where, edges, check_graph_nodes(where, nodes))
    check_choice(where, nodes + edges, "status", STATUSES)
    check_choice(where, nodes, "shape", SHAPES)
    for n in nodes:
        if n.get("link"):
            check_link(f"{where} node {n['id']}", n["link"])
    return graph

def transition_edge(where: str, t: dict[str, Any]) -> dict[str, Any]:
    if not t.get("event"):
        sys.exit(f"{where}: every machine transition needs an event")
    edge = {"from": t.get("from"), "to": t.get("to"), "label": t["event"]}
    return {**edge, "status": t["status"]} if "status" in t else edge

def machine_graph(where: str, machine: dict[str, Any]) -> dict[str, Any]:
    """A state machine as a graph: states are nodes, transitions are edges labelled with their event."""
    states = machine.get("states") or [{}]
    initial = machine.get("initial") or states[0].get("id")
    if initial not in {st.get("id") for st in states}:
        sys.exit(f"{where}: machine initial state {initial!r} is not one of its states")
    return {"direction": machine.get("direction", "LR"), "machine": {"initial": initial},
            "nodes": [{**st, "initial": st.get("id") == initial} for st in states],
            "edges": [transition_edge(where, t) for t in machine.get("transitions") or []]}

has_graph = False

def render_diagram(where: str, spec: Flow) -> str:
    """A React Flow placeholder for a graph or machine, else a mermaid block."""
    global has_graph
    if "graph" in spec or "machine" in spec:
        has_graph = True
        graph = spec["graph"] if "graph" in spec else machine_graph(where, spec["machine"])
        data = check_graph(where, graph)
        return f'<div class="rf-graph" data-graph="{html.escape(json.dumps(data))}"></div>'
    return f'<pre class="mermaid">{html.escape(spec["diagram"])}</pre>'

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
    if 'class="mermaid"' in value:
        sys.exit(f"{where}: put inline diagrams in diagrams and embed them with <div data-diagram=\"name\"></div>")
    return DIAGRAM_REF.sub(lambda m: embed_diagram(where, m), value)

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

groups, seen = [], set()
for g in cfg["groups"]:
    files = []
    for entry in g["files"]:
        spec = {"path": entry} if isinstance(entry, str) else entry
        f = spec["path"]
        d = git("diff", "-U4", base, head, "--", f)
        if not d:
            sys.exit(f"no diff for {f}")
        seen.add(f)
        header = d[:400]
        status = "A" if "\nnew file mode" in header else "D" if "\ndeleted file mode" in header else "M"
        lines = d.splitlines()
        files.append(dict(
            path=f, status=status,
            add=sum(l.startswith("+") and not l.startswith("+++") for l in lines),
            rem=sum(l.startswith("-") and not l.startswith("---") for l in lines),
            diff=d[d.index("\n@@") + 1:] if "\n@@" in d else "",
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
        missing_keys = {"file", "name", "change", "type", "inputs", "expected", "why"} - row.keys()
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
    groups.append({**g, "files": files, "data_flow": "".join(f"<div>{render_flow(g['id'], f)}</div>" for f in flows),
                   "state": "".join(f"<div>{render_flow(g['id'], f)}</div>" for f in machines)})

skips = tuple(cfg.get("skip_prefixes", []))
missing = [f for f in git("diff", "--name-only", base, head).split() if f not in seen and not f.startswith(skips)]
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
tpl = tpl.replace("/*__XYFLOW_CSS__*/", (assets / "xyflow.css").read_text() if has_graph else "")
tpl = tpl.replace("/*__DATA__*/null", js(groups)).replace("/*__META__*/[]", js(meta))
out_path.write_text(tpl)
print(f"wrote {out_path} ({len(tpl)} bytes, {sum(len(g['files']) for g in groups)} files)")
