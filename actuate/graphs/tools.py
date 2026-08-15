"""Tools a graph specialist may call: local helpers plus constrained HTTP/search.

Network tools are GET-only, HTTPS-preferred, private-IP blocked, size-capped.
They are not a general HTTP client for attacking systems.
"""

from __future__ import annotations

import ast
import ipaddress
import json
import operator
import socket
import time
from typing import Any, Awaitable, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urlparse
from urllib.request import Request, urlopen

from actuate.graphs.catalog import agent_by_id

ToolFn = Callable[[dict[str, Any], dict[str, Any]], Awaitable[str]]

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.Mod: operator.mod,
}


def _eval_math(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_math(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return float(_OPS[type(node.op)](_eval_math(node.operand)))
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return float(_OPS[type(node.op)](_eval_math(node.left), _eval_math(node.right)))
    raise ValueError("unsupported expression")


async def tool_calculator(args: dict[str, Any], ctx: dict[str, Any]) -> str:
    expr = str(args.get("expression") or "").strip()
    if not expr or len(expr) > 120:
        return "NEED DATA: empty or too-long expression"
    try:
        tree = ast.parse(expr, mode="eval")
        return str(_eval_math(tree))
    except (ValueError, SyntaxError, TypeError, ZeroDivisionError) as exc:
        return f"NEED DATA: {exc}"


async def tool_utc_now(args: dict[str, Any], ctx: dict[str, Any]) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


async def tool_recall_memory(args: dict[str, Any], ctx: dict[str, Any]) -> str:
    memory = ctx.get("memory")
    query = str(args.get("query") or ctx.get("user_goal") or "")
    if memory is None or not query:
        return "NEED DATA: no memory store or empty query"
    rows = await memory.recall(query, top_k=int(args.get("top_k") or 3))
    if not rows:
        return "No similar trajectories stored yet."
    return "\n\n".join(r.text for r in rows)


async def tool_list_connections(args: dict[str, Any], ctx: dict[str, Any]) -> str:
    nid = str(ctx.get("node_id") or "")
    graph = ctx.get("graph") or {}
    edges = list(graph.get("edges") or [])
    nodes = {n["id"]: n for n in graph.get("nodes") or []}
    parents = [e["source"] for e in edges if e["target"] == nid]
    children = [e["target"] for e in edges if e["source"] == nid]

    def label(i: str) -> str:
        node = nodes.get(i) or {}
        agent = str(node.get("agent") or i)
        try:
            title = agent_by_id(agent)["title"]
        except KeyError:
            title = agent
        return f"{i} · {title} ({agent})"

    return json.dumps(
        {
            "this_node": label(nid),
            "receives_from": [label(p) for p in parents],
            "sends_to": [label(c) for c in children],
            "fan_out": len(children),
            "note": "When this node finishes, every child listed under sends_to receives this output in parallel unless a child still waits on another unfinished parent.",
        }
    )


async def tool_handoff(args: dict[str, Any], ctx: dict[str, Any]) -> str:
    summary = str(args.get("summary") or "").strip()
    open_questions = args.get("open_questions") or []
    if isinstance(open_questions, str):
        open_questions = [open_questions]
    return json.dumps(
        {
            "handoff": True,
            "from": ctx.get("agent_title") or ctx.get("agent"),
            "summary": summary[:4000],
            "open_questions": list(open_questions)[:12],
        }
    )


_MAX_BODY = 80_000
_TIMEOUT = 12


def _blocked_host(host: str) -> bool:
    host = (host or "").strip().lower().rstrip(".")
    if not host or host in {"localhost", "metadata.google.internal"}:
        return True
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return True
    for info in infos:
        ip = info[4][0]
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return True
        if (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_reserved
            or addr.is_multicast
            or str(addr) == "169.254.169.254"
        ):
            return True
    return False


def _http_get(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return "NEED DATA: only https URLs are allowed"
    if _blocked_host(parsed.hostname or ""):
        return "NEED DATA: that host is not allowed (private/loopback/metadata)"
    req = Request(
        url,
        method="GET",
        headers={"User-Agent": "Actuate/0.1 (agent tool; +https://github.com/actuate-ai/actuate)"},
    )
    try:
        with urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310 — scheme checked above
            raw = resp.read(_MAX_BODY + 1)
    except HTTPError as exc:
        return f"NEED DATA: HTTP {exc.code}"
    except (URLError, TimeoutError, ValueError, OSError) as exc:
        return f"NEED DATA: {exc}"
    if len(raw) > _MAX_BODY:
        raw = raw[:_MAX_BODY]
    text = raw.decode("utf-8", errors="replace")
    return text


def _strip_html(html: str) -> str:
    out: list[str] = []
    skip = 0
    i = 0
    lower = html.lower()
    while i < len(html):
        if lower.startswith("<script", i) or lower.startswith("<style", i):
            endtag = "</script>" if lower.startswith("<script", i) else "</style>"
            j = lower.find(endtag, i)
            i = len(html) if j < 0 else j + len(endtag)
            continue
        ch = html[i]
        if ch == "<":
            skip = 1
        elif ch == ">":
            skip = 0
            out.append(" ")
        elif not skip:
            out.append(ch)
        i += 1
    return " ".join("".join(out).split())[:_MAX_BODY]


async def tool_http_get(args: dict[str, Any], ctx: dict[str, Any]) -> str:
    url = str(args.get("url") or "").strip()
    if not url:
        return "NEED DATA: url required"
    body = _http_get(url)
    if body.startswith("NEED DATA:"):
        return body
    if "<" in body[:200].lower():
        body = _strip_html(body)
    return body[:_MAX_BODY]


async def tool_web_search(args: dict[str, Any], ctx: dict[str, Any]) -> str:
    query = str(args.get("query") or "").strip()
    if not query:
        return "NEED DATA: query required"
    url = f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&no_html=1&no_redirect=1"
    raw = _http_get(url)
    if raw.startswith("NEED DATA:"):
        return raw
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw[:4000]
    heading = data.get("Heading") or query
    abstract = data.get("AbstractText") or data.get("Abstract") or ""
    related = []
    for item in (data.get("RelatedTopics") or [])[:8]:
        if isinstance(item, dict) and item.get("Text"):
            related.append(item["Text"])
        elif isinstance(item, dict) and isinstance(item.get("Topics"), list):
            for sub in item["Topics"][:3]:
                if isinstance(sub, dict) and sub.get("Text"):
                    related.append(sub["Text"])
    source = data.get("AbstractURL") or ""
    if not abstract and not related:
        return (
            f"Search returned no instant answer for {heading!r}. "
            "Use http_get on a specific https URL, or mark NEED SOURCE."
        )
    lines = [f"Query: {heading}", abstract, f"Source: {source}" if source else "", "Related:"]
    lines.extend(f"- {r}" for r in related[:8])
    return "\n".join(t for t in lines if t)[:_MAX_BODY]


SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "calculator",
        "description": "Evaluate a basic arithmetic expression. No variables.",
        "args": {"expression": "e.g. (18+41)/2"},
    },
    {
        "name": "utc_now",
        "description": "Current UTC timestamp.",
        "args": {},
    },
    {
        "name": "recall_memory",
        "description": "Retrieve similar past successful trajectories from Actuate memory.",
        "args": {"query": "search text", "top_k": "optional int"},
    },
    {
        "name": "list_connections",
        "description": "See which graph nodes send data here and which children will receive this output in parallel.",
        "args": {},
    },
    {
        "name": "handoff",
        "description": "Package a structured packet for downstream specialists (does not skip the graph; it is extra structure in your working notes).",
        "args": {"summary": "str", "open_questions": "list[str]"},
    },
    {
        "name": "web_search",
        "description": "Search the public web (DuckDuckGo instant answers). Use for facts you do not have. Cite NEED SOURCE if empty.",
        "args": {"query": "search string"},
    },
    {
        "name": "http_get",
        "description": "GET a public https URL and return text. Blocked: localhost, private IPs, metadata. Max ~80KB.",
        "args": {"url": "https://..."},
    },
]

DISPATCH: dict[str, ToolFn] = {
    "calculator": tool_calculator,
    "utc_now": tool_utc_now,
    "recall_memory": tool_recall_memory,
    "list_connections": tool_list_connections,
    "handoff": tool_handoff,
    "web_search": tool_web_search,
    "http_get": tool_http_get,
}


def tool_instructions() -> str:
    lines = [
        "You are a real Actuate agent, not a single-shot autocomplete.",
        "You may call tools before writing the specialist deliverable.",
        "To call a tool, emit ONE JSON object and nothing else on that turn:",
        '{"tool": "name", "args": {}}',
        "Available tools:",
    ]
    for spec in SCHEMAS:
        lines.append(f"- {spec['name']}: {spec['description']} args={spec['args']}")
    lines.append("After tool results, write the final specialist output. Do not invent tool results.")
    lines.append("Max a few tool calls. If a tool returns NEED DATA, continue without fabricating.")
    return "\n".join(lines)


async def run_tool(name: str, args: dict[str, Any], ctx: dict[str, Any]) -> str:
    fn = DISPATCH.get(name)
    if fn is None:
        return f"Unknown tool '{name}'. Allowed: {', '.join(DISPATCH)}"
    return await fn(args or {}, ctx)
