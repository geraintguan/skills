"""Total the tokens and estimated cost of building a review guide.

Usage: python3 usage.py out.json [--since ISO-TIMESTAMP] [--transcript PATH]

build.py calls collect() itself, so run this only to inspect the numbers or to save
them for a build outside the session (the config's usage_file).

Reads the Claude Code transcript of the current session ($CLAUDE_CODE_SESSION_ID) and
its subagent transcripts. Counts every model request from --since onwards. Without
--since, it starts at the last time the pr-review-guide skill was launched, or at the
start of the session if it can't find one.

Cost is an estimate at PRICING_SOURCE. It ignores plan or subscription billing, batch
discounts and partner pricing.
"""
import argparse, json, os, pathlib, sys
from typing import Any, Iterator, Optional

Entry = dict[str, Any]
Tokens = dict[str, int]

# $ per million tokens: (input, output, cache read). Cache writes are 1.25x input for
# the 5-minute TTL and 2x input for the 1-hour TTL. Longest prefix match wins.
PRICES = {
    "claude-fable-5-1": (10.00, 50.00, 0.25),
    "claude-mythos-5-1": (10.00, 50.00, 0.25),
    "claude-fable-5": (10.00, 50.00, 1.00),
    "claude-mythos-5": (10.00, 50.00, 1.00),
    "claude-opus-5-5": (4.00, 20.00, 0.20),
    "claude-opus-5": (5.00, 25.00, 0.50),
    "claude-opus-4-8": (5.00, 25.00, 0.50),
    "claude-opus-4-7": (5.00, 25.00, 0.50),
    "claude-opus-4-6": (5.00, 25.00, 0.50),
    "claude-opus-4-5": (5.00, 25.00, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20),
    "claude-sonnet-5": (2.00, 10.00, 0.20),
    "claude-sonnet-4-6": (3.00, 15.00, 0.30),
    "claude-sonnet-4-5": (3.00, 15.00, 0.30),
    "claude-haiku-4-5": (1.00, 5.00, 0.10),
}
PRICING_SOURCE = "Anthropic API list prices, cached 2026-09-25"
WRITE_5M, WRITE_1H = 1.25, 2.0
FAST_MULTIPLIER = 2.0
WEB_SEARCH_USD = 10.00 / 1000
SKILL_NAME = "pr-review-guide"
TOKEN_KINDS = ("input", "cache_write_5m", "cache_write_1h", "cache_read", "output")
# Substrings a line must contain to be worth parsing; most of a transcript is tool output.
LINE_MARKERS = ('"usage"', f"<command-name>/{SKILL_NAME}", '"Skill"')


def current_transcript() -> Optional[pathlib.Path]:
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not session_id:
        return None
    config_dir = pathlib.Path(os.environ.get("CLAUDE_CONFIG_DIR", pathlib.Path.home() / ".claude"))
    return next(config_dir.glob(f"projects/*/{session_id}.jsonl"), None)


def read_entries(path: pathlib.Path) -> Iterator[Entry]:
    with path.open() as f:
        for line in f:
            if not any(marker in line for marker in LINE_MARKERS):
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def is_skill_launch(entry: Entry) -> bool:
    content = (entry.get("message") or {}).get("content")
    if entry.get("type") == "user" and isinstance(content, str):
        return f"<command-name>/{SKILL_NAME}" in content
    if entry.get("type") == "assistant" and isinstance(content, list):
        return any(block.get("type") == "tool_use" and block.get("name") == "Skill"
                   and str(block.get("input", {}).get("skill", "")).split(":")[-1] == SKILL_NAME
                   for block in content)
    return False


def scan(path: pathlib.Path) -> tuple[list[tuple[str, Entry]], list[str]]:
    """(timestamp, message) per API message, and skill launch timestamps, in one pass.

    Streamed content blocks repeat a message's usage on several lines, so the last copy wins.
    """
    by_id: dict[str, tuple[str, Entry]] = {}
    launches = []
    for e in read_entries(path):
        timestamp = e.get("timestamp", "")
        if is_skill_launch(e):
            launches.append(timestamp)
        message = e.get("message") or {}
        if e.get("type") == "assistant" and message.get("usage") and message.get("model") != "<synthetic>":
            by_id[message.get("id") or e.get("uuid")] = (timestamp, message)
    return list(by_id.values()), launches


def split_usage(usage: dict[str, Any]) -> Tokens:
    cache_write = usage.get("cache_creation") or {}
    write_1h = cache_write.get("ephemeral_1h_input_tokens", 0)
    write_5m = cache_write.get("ephemeral_5m_input_tokens",
                               usage.get("cache_creation_input_tokens", 0) - write_1h)
    return {
        "input": usage.get("input_tokens", 0),
        "cache_write_5m": write_5m,
        "cache_write_1h": write_1h,
        "cache_read": usage.get("cache_read_input_tokens", 0),
        "output": usage.get("output_tokens", 0),
    }


def sum_tokens(rows: list[Tokens]) -> Tokens:
    totals = {kind: sum(r[kind] for r in rows) for kind in TOKEN_KINDS}
    return {**totals, "total": sum(totals.values())}


def price_for(model: str) -> Optional[tuple[float, float, float]]:
    keys = [k for k in PRICES if model.startswith(k)]
    return PRICES[max(keys, key=len)] if keys else None


def request_cost(input_price: float, output_price: float, read_price: float, usage: dict[str, Any]) -> float:
    tokens = split_usage(usage)
    cost = (tokens["input"] * input_price
            + tokens["cache_write_5m"] * input_price * WRITE_5M
            + tokens["cache_write_1h"] * input_price * WRITE_1H
            + tokens["cache_read"] * read_price
            + tokens["output"] * output_price) / 1_000_000
    if usage.get("speed") == "fast":
        cost *= FAST_MULTIPLIER
    searches = (usage.get("server_tool_use") or {}).get("web_search_requests", 0)
    return cost + searches * WEB_SEARCH_USD


def model_row(model: str, messages: list[Entry]) -> dict[str, Any]:
    """cost_usd is None when the model has no entry in PRICES."""
    price = price_for(model)
    cost = None if price is None else round(sum(request_cost(*price, m["usage"]) for m in messages), 4)
    return {"model": model, "requests": len(messages), "cost_usd": cost,
            "tokens": sum_tokens([split_usage(m["usage"]) for m in messages])}


def summarise(messages: list[Entry]) -> dict[str, Any]:
    by_model: dict[str, list[Entry]] = {}
    for message in messages:
        by_model.setdefault(message["model"], []).append(message)
    rows = sorted((model_row(m, ms) for m, ms in by_model.items()), key=lambda r: r["cost_usd"] or 0, reverse=True)
    return {
        "requests": len(messages),
        "tokens": sum_tokens([r["tokens"] for r in rows]),
        "cost_usd": round(sum(r["cost_usd"] or 0 for r in rows), 4),
        "unpriced_models": [r["model"] for r in rows if r["cost_usd"] is None],
        "by_model": rows,
    }


def collect(transcript: pathlib.Path, since: Optional[str] = None) -> dict[str, Any]:
    main_messages, launches = scan(transcript)
    since = since or max(launches, default=None)

    def after_start(records: list[tuple[str, Entry]]) -> list[Entry]:
        return [message for timestamp, message in records if not since or timestamp >= since]

    messages = after_start(main_messages)
    subagents = 0
    for path in sorted(transcript.with_suffix("").glob("subagents/*.jsonl")):
        subagent_messages = after_start(scan(path)[0])
        subagents += bool(subagent_messages)
        messages += subagent_messages
    return {"since": since, "transcript": str(transcript), "subagents": subagents,
            "pricing": PRICING_SOURCE, **summarise(messages)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out")
    parser.add_argument("--since", help="ISO 8601 UTC timestamp, e.g. 2026-10-16T13:41:59Z")
    parser.add_argument("--transcript", type=pathlib.Path)
    args = parser.parse_args()

    transcript = args.transcript or current_transcript()
    if transcript is None:
        sys.exit("no transcript for this session: pass --transcript")
    report = collect(transcript, args.since)
    pathlib.Path(args.out).write_text(json.dumps(report, indent=2) + "\n")
    print(f"wrote {args.out}: {report['requests']} requests, {report['tokens']['total']:,} tokens, "
          f"~${report['cost_usd']:.2f} since {report['since'] or 'session start'}")
    if report["unpriced_models"]:
        print("no price for: " + ", ".join(report["unpriced_models"]), file=sys.stderr)


if __name__ == "__main__":
    main()
