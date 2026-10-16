"""Build a PR review artifact page from a config JSON.

Usage: python3 build.py config.json out.html

See references/config.md for every key and how to write good content for it.

Config keys:
  repo_root, base (merge-base sha or ref), head (default HEAD)
  title (page <title>, 2-4 words), eyebrow, h1, lede, pr_url, store_key
  meta_extra: list of short HTML strings for the header meta row
  groups: [{id, title, files: [path | {path, note?, lines?}],
            file note: HTML narrating what the file's change does and why (shown above its diff)
            lines: [{line, side: "new"|"old" (default new), text: HTML, impact?}] inline notes after that line;
                   the line must appear in the diff (an added/context line for new, removed/context for old)
            lead: optional HTML sentence (where to start),
            changes: {added|modified|deleted: [{impact: "High"|"Medium"|"Low", text: HTML}]}}]
          (legacy: note: [HTML strings] renders a plain list when changes is absent)
            tests: [{file, name, change: "Added"|"Modified"|"Removed", type: "Unit"|"Integration"|"E2E",
                     inputs: HTML, expected: HTML, why: HTML}]  one row per test changed in the section's files
            tests_file: path to a JSON file holding that array (relative to the config), merged into tests
  skip_prefixes: changed paths deliberately left out (e.g. generated locales)
  overview (optional, rendered first): {
    summary: [HTML paragraphs: what the change does and why],
    before: [HTML bullets], after: [HTML bullets],
    diagram: mermaid source for the architecture, diagram_caption: HTML,
    layout: [{path, role (HTML), group (group id)}]  # where the code lives; +/- is summed per path prefix
    decisions: [HTML bullets: key design decisions and who made them]
  }
Diagrams anywhere else go in HTML fields as <pre class="mermaid">source</pre>.
The script fails if a changed file is in no group and not skipped.
"""
import html, json, subprocess, sys, pathlib

cfg = json.loads(pathlib.Path(sys.argv[1]).read_text())
out_path = pathlib.Path(sys.argv[2])
root, base, head = cfg.get("repo_root", "."), cfg["base"], cfg.get("head", "HEAD")

def git(*args):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout

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

def check_line_notes(path, d, notes):
    shown = diff_lines(d)
    for note in notes:
        side = note.get("side", "new")
        if note["line"] not in shown.get(side, ()):
            sys.exit(f"{path}: line note at {side} line {note['line']} is not in the diff")
        if note.get("impact") not in (None, "High", "Medium", "Low"):
            sys.exit(f"{path}: bad impact {note.get('impact')}")
    return notes

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
        tests += json.loads((pathlib.Path(sys.argv[1]).parent / g["tests_file"]).read_text())
    group_paths = {f["path"] for f in files}
    for row in tests:
        missing_keys = {"file", "name", "change", "type", "inputs", "expected", "why"} - row.keys()
        if missing_keys:
            sys.exit(f"{g['id']}: test row missing {sorted(missing_keys)}: {row.get('name')}")
        if row["change"] not in ("Added", "Modified", "Removed") or row["type"] not in ("Unit", "Integration", "E2E"):
            sys.exit(f"{g['id']}: bad change/type in test row {row['name']}")
        if row["file"] not in group_paths:
            sys.exit(f"{g['id']}: test file {row['file']} is not in this group's files")
    g = {**g, "tests": tests}
    for kind, items in g.get("changes", {}).items():
        if kind not in ("added", "modified", "deleted"):
            sys.exit(f"{g['id']}: unknown change type {kind}")
        for c in items:
            if c.get("impact") not in ("High", "Medium", "Low"):
                sys.exit(f"{g['id']}: impact must be High, Medium or Low: {c}")
    groups.append({**g, "files": files})

skips = tuple(cfg.get("skip_prefixes", []))
missing = [f for f in git("diff", "--name-only", base, head).split() if f not in seen and not f.startswith(skips)]
if missing:
    sys.exit("changed files in no group:\n  " + "\n  ".join(missing))

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
    if ov.get("diagram"):
        cap = f'<p class="ov-caption">{ov["diagram_caption"]}</p>' if ov.get("diagram_caption") else ""
        parts.append(f'<div><h3>Architecture</h3><div class="ov-diagram"><pre class="mermaid">{html.escape(ov["diagram"])}</pre>{cap}</div></div>')
    if ov.get("layout"):
        rows = "".join(
            f'<tr><td class="p"><a href="#{r["group"]}">{html.escape(r["path"])}</a></td><td>{r["role"]}</td><td class="s">{stat(r["path"])}</td></tr>'
            for r in ov["layout"])
        parts.append(f'<div><h3>Code layout</h3><div class="ov-layout"><table><thead><tr><th>Where</th><th>What it does in this PR</th><th>Lines</th></tr></thead><tbody>{rows}</tbody></table></div></div>')
    if ov.get("decisions"):
        parts.append(f'<div><h3>Key decisions</h3><ul class="ov-decisions">{bullets(ov["decisions"])}</ul></div>')
    parts.append("</section>")
    return "".join(parts)

def js(value):
    return json.dumps(value).replace("</", "<\\/")

tpl = (pathlib.Path(__file__).resolve().parent.parent / "assets" / "template.html").read_text()
for key, value in {
    "__TITLE__": html.escape(cfg["title"]), "__EYEBROW__": cfg["eyebrow"], "__H1__": cfg["h1"],
    "__LEDE__": cfg["lede"], "__OVERVIEW__": render_overview(cfg.get("overview")), "__PR_URL__": cfg["pr_url"], "__STORE_KEY__": cfg["store_key"],
}.items():
    tpl = tpl.replace(key, value)
tpl = tpl.replace("/*__DATA__*/null", js(groups)).replace("/*__META__*/[]", js(cfg.get("meta_extra", [])))
out_path.write_text(tpl)
print(f"wrote {out_path} ({len(tpl)} bytes, {sum(len(g['files']) for g in groups)} files)")
