"""List the tests a diff adds, modifies or removes, per test file.

Usage: python3 tests_inventory.py <base-ref> [out.json]   (run from the repo root)

Covers JS/TS test files (it/test, including it.each) and Storybook stories that have a
`play` function. Treat the output as a starting point:
- describe prefixes can be wrong for sibling describe blocks; use the real names from source;
- "modified" compares whitespace-normalised bodies, so a rename of a constant counts;
- a test renamed in place shows as one removed plus one added.
"""
import json, re, subprocess, sys

base = sys.argv[1]
out_path = sys.argv[2] if len(sys.argv) > 2 else None
TEST_FILE = re.compile(r"(\.(test|spec)\.[cm]?[jt]sx?$)|(\.stories\.[jt]sx?$)")
TEST = re.compile(r'^(\s*)(it|test)(\.each\([^\n]*?\))?\(\s*([`"\'])(.+?)\4', re.M)
DESC = re.compile(r'^(\s*)describe\(\s*([`"\'])(.+?)\2', re.M)
STORY = re.compile(r"^export const (\w+)\s*(?::[^=]+)?=", re.M)


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True)


def show(rev, path):
    result = git("show", f"{rev}:{path}")
    return result.stdout if result.returncode == 0 else ""


def stories_with_play(src):
    found = [(m.start(), m.group(1)) for m in STORY.finditer(src)]
    out = {}
    for i, (pos, name) in enumerate(found):
        body = src[pos : found[i + 1][0] if i + 1 < len(found) else len(src)]
        if "play:" in body or "play(" in body:
            out[name] = body
    return out


def test_cases(src):
    descs = [(m.start(), len(m.group(1)), m.group(3)) for m in DESC.finditer(src)]
    cases = list(TEST.finditer(src))
    out = {}
    for i, m in enumerate(cases):
        body = src[m.start() : cases[i + 1].start() if i + 1 < len(cases) else len(src)]
        prefix = [d for (p, indent, d) in descs if p < m.start() and indent < len(m.group(1))]
        out[" › ".join(prefix[-2:] + [m.group(5)])] = body
    return out


def normalise(text):
    return re.sub(r"\s+", " ", text)


inventory = {}
for path in git("diff", "--name-only", base, "HEAD").stdout.split():
    if not TEST_FILE.search(path):
        continue
    extract = stories_with_play if ".stories." in path else test_cases
    old, new = extract(show(base, path)), extract(show("HEAD", path))
    inventory[path] = {
        "added": [n for n in new if n not in old],
        "removed": [n for n in old if n not in new],
        "modified": [n for n in new if n in old and normalise(new[n]) != normalise(old[n])],
    }

if out_path:
    with open(out_path, "w") as f:
        json.dump(inventory, f, indent=1)
for path, change in inventory.items():
    print(f"\n## {path}  +{len(change['added'])} ~{len(change['modified'])} -{len(change['removed'])}")
    for kind in ("added", "modified", "removed"):
        for name in change[kind]:
            print(f"  {kind[0].upper()} {name}")
