# `lean` — Implementation Spec: Stages 3–5 (trimmed)

Kept as "3–5" to stay consistent with the original roadmap numbering
(1 = skeleton, 2 = project state). This covers the graph read path, the two
side-effecting tools plus truncation, and the fake-LLM dispatch loop — the
last stage before anything talks to a real model.

This is the third pass at the same stages. It keeps your `graph/loader.py`
**exactly as you wrote it**, drops the custom exception layer, and keeps
everything the stage descriptions actually require. The source and test files
below were assembled from a working project: with them in place,
**27 tests pass** against the fixture in this document.

---

## Why this version is the simplest

The two earlier drafts, side by side with this one:

| | Draft 1 (`lean-spec-stages-3-5.md`) | Draft 2 (`…-3-5_1_.md`) | **This version** |
|---|---|---|---|
| Your loader | replaced by a pydantic `Graph` | kept, with 5 edits | **kept, 0 edits** |
| Fixture | hand-written `keywords` list on every node | graphify-shaped | graphify-shaped |
| Custom exception classes | 6 | 6 | **0** |
| `raise` sites for them | 7 | 10 | **0** |
| `except` sites | 1 | 3 | **1** (one catch-all, in dispatch) |
| Source lines in the snippets¹ | 179 | 235 | 200 |
| Tests | 11 | 26 | 27 |

¹ Non-blank, non-comment lines in the Python source snippets, counted the same
way for all three. The number for this version includes the 36 lines of loader
you already wrote, so about 164 lines are new.

Raw line count isn't where this version wins against draft 1. It's slightly
larger, because it carries the real graphify loader and the `(nodes, adj)` query
layer. The wins are in the rows above it (no rewrite, no
hand-written keywords, no exception classes) and, against draft 2, roughly 35
fewer source lines.

**Why each choice makes this the easiest:**

1. **Nothing you've already written gets rewritten.** The loader is the only
   piece of stages 3–5 that touches graphify's format, and it's already done.
   Draft 1 asked you to throw it away for a placeholder schema; draft 2 listed
   five edits to it (restored comments, `TypedDict`, a new exception type,
   `GraphError` wrapping for bad files, an encoding argument). Here it's pasted
   in unchanged.
2. **No hand-maintained data.** Draft 1's schema needed a `keywords` list on
   every fixture node, plus a validator to catch id typos in that hand-written
   JSON. graphify doesn't emit keywords, so that schema would have needed an
   adapter later anyway. This version matches keywords against text your
   loader already produces (`id`, `name`, `source_location`), so there is
   nothing extra to author or keep in sync.
3. **One error policy instead of an error hierarchy.** The custom exceptions
   were the "error specific functions" that made drafts 1 and 2 more work:
   define six classes, raise them in ten places, validate arguments in every
   tool, and catch the right one in the right place. Here tools just run, and
   one `except Exception` in `dispatch.py` hands whatever went wrong back to
   the model. The details are in [Error handling](#error-handling-the-whole-policy).
4. **Tools are thin adapters.** `graph_query` and `top_nodes` are five lines
   each. All the logic lives in `query.py`, which is pure functions over
   `(nodes, adj)` and tests without mocks.
5. **Stage 11 gets smaller.** Because the loader targets graphify's real
   field names now, stage 11 only has to *produce* `graph.json`. There's no
   "the placeholder schema might not match" adapter step left.

**What you give up compared with draft 2** (and why it's acceptable for now):

- A truncated or hand-mangled `graph.json` fails with Python's own
  `JSONDecodeError` or `KeyError` instead of a friendly `GraphError` message.
  Nothing writes `graph.json` until stage 11, so this can't happen yet.
- A real bug in a tool shows up as a `tool_error` in the history instead of
  crashing the loop. The fix while debugging is one line: `print(exc)` inside
  the `except`.
- Bad tool arguments aren't type-checked up front; Python's own errors say
  what went wrong (`KeyError: 'keywords'`) and the model retries.

---

## Error handling: the whole policy

Four rules, and nothing else:

1. **Tools don't validate their arguments.** They read `args["path"]`,
   `args["keywords"]` and so on. If something is missing or the wrong type,
   Python raises `KeyError`, `TypeError`, `ValueError` or `FileNotFoundError`
   on its own.
2. **`dispatch.py` is the only place that catches.** It wraps every tool call
   in `except Exception` and appends the result as a `tool_error` entry:

   ```text
   tool_error: KeyError: 'keywords'
   tool_error: FileNotFoundError: [Errno 2] No such file or directory: '/proj/missing.py'
   tool_error: unknown tool: 'delete_repo'
   ```

   The exception's *type name* is included on purpose. `str(KeyError("keywords"))`
   is just `'keywords'`, which tells the model very little on its own.
3. **Guards and refusals are return values, not exceptions.** `write_md`
   returns `error: write_md can only write .md/.markdown files…` for a wrong
   suffix and `write_md cancelled by user: …` when the user says no. Neither is
   a crash; they're normal outcomes the model should read like any other tool
   result. It also means the `.md` guard doesn't depend on an exception class
   that some other code has to remember to catch.
4. **One hard failure.** If the loop runs `max_iterations` without a `done`,
   `run_turn` raises a plain `RuntimeError`. That's a genuine "something is
   wrong with this model or prompt" condition and it should reach the CLI.

A missing `graph.json` raises the built-in `FileNotFoundError` from your loader,
with your message. When the CLI is built (stage 9), the friendly version is a
two-line `try/except FileNotFoundError` around `load_graph`; no new exception
class is needed.

One ordering detail lives in `write_md`: it reads `args["path"]` and
`args["content"]` **before** the confirm prompt. Otherwise a call with no
`content` would ask the user to approve a write and *then* fail. There's a test
for it.

---

## Project layout (additions)

```
src/lean/
├── paths.py              # stage 3 — adds graph_path()
├── config.py             # stage 4 — adds file_read_lines
├── graph/
│   ├── loader.py          # stage 3 — yours, unchanged
│   └── query.py           # stage 3
├── tools/
│   ├── graph_query.py      # stage 3
│   ├── top_nodes.py        # stage 3
│   ├── read_file.py        # stage 4
│   └── write_md.py         # stage 4
└── pipeline/
    ├── truncate.py          # stage 4
    ├── llm.py                # stage 5 — interface only, no Ollama yet
    └── dispatch.py           # stage 5

tests/
├── fixtures/graph.json    # stage 3
├── support/fake_llm.py     # stage 5, reused by later stages
├── test_graph.py           # stage 3
├── test_tools.py           # stage 4
└── test_dispatch.py         # stage 5
```

There is no `errors.py`. Each new folder (`graph/`, `tools/`, `pipeline/`,
`tests/`, `tests/support/`) needs an empty `__init__.py`; the tests import
`tests.support.fake_llm`, so run `pytest` from the project root.

### Two edits to files you already have

```python
# paths.py — add next to config_path()
def graph_path(root: Path | None = None) -> Path:
    return lean_dir(root) / "graph.json"
```

```python
# config.py — LeanConfig gains one field (stage 4 reads it)
class LeanConfig(BaseModel):
    provider: str = "ollama"
    model: str = "qwen-3.5:27b"
    autonomy: AutonomyMode = "confirm"
    file_read_lines: int = 50
```

`file_read_lines` is the `max_lines` that `read_file` receives. The model never
chooses it (its arguments are only `path` and `offset`), so a misbehaving
prompt can't ask for a 5,000-line read. `context_limit` and `design_doc_dir`
from the full `config.json` schema aren't needed until stages 6 and 10, so add
them then.

---

## Stage 3 — Graph read path

Stage 3 is read-only. It never runs graphify and never writes `graph.json`. It
turns a graph file that already exists into two things the model can ask for:
*what's near these keywords?* (`graph_query`) and *what are the most connected
nodes?* (`top_nodes`).

```text
.lean/graph.json
     │  loader.py     file → data. The only place graphify's field names appear.
     ▼
(nodes, adj)           what the nodes are / how they connect
     │  query.py       pure functions over that data (BFS, ranking, formatting), no I/O
     ▼
tools/graph_query.py, tools/top_nodes.py
     │                 five-line adapters: pull args out, call query.py, return a string
     ▼
dispatch.py (stage 5)
```

### `graph/loader.py` — yours, unchanged

```python
"""Graph info adapter"""

from pathlib import Path
import json

# Node defined by graphify schema
Node = {
    "id": str,      
    "type": str,        
    "name": str | None,
    "source_location": str | None,
}

# adjacency map to node id's to neighbor id's 
AdjacencyMap = dict[str, set[str]]

# node lookup id to node
NodeLookup = dict[str, Node]

# convert graphify node to internal representation
def _translate_node(raw_node: dict) -> Node:

    return {
        "id": raw_node["id"],
        "type": raw_node.get("file_type"),
        "name": raw_node.get("label"),
        "source_location": raw_node.get("source_location"),
    }

# extract source/target pair from graphify edge
def _translate_edge(raw_edge: dict) -> tuple[str, str]:

    return (raw_edge["source"], raw_edge["target"])

# load graph.json and return (node_lookup, adjacency_map)
def load_graph(graph_path: Path) -> tuple[NodeLookup, AdjacencyMap]:

    # check for graph_path existance
    if not graph_path.exists():
        raise FileNotFoundError(f"Graph missing... Try running 'lean init' first.")

    # read raw JSON
    with open(graph_path) as d:
        data = json.load(d)

    # grab nodes from json and put into map
    nodes: NodeLookup = {}
    for raw_node in data.get("nodes", []):
        node = _translate_node(raw_node)
        nodes[node["id"]] = node

    # build undirected adjacency map
    adj: AdjacencyMap = {node_id: set() for node_id in nodes}

    # grab edges from json and put into adj matrix
    for raw_edge in data.get("edges", []):
        source, target = _translate_edge(raw_edge)

        if source in adj and target in adj:
            adj[source].add(target)
            adj[target].add(source)

    return nodes, adj
```

Nothing to change. Why it's already the right shape:

- **`_translate_node` / `_translate_edge` are the seam.** They're the only
  functions that know graphify's names (`file_type`, `label`, `source`,
  `target`). If graphify renames a field, you edit one of them.
- **A dict keyed by id.** BFS looks nodes up by id constantly; `nodes[node_id]`
  is O(1) on a dict and an O(n) scan on a list.
- **`adj` is built once, undirected.** graphify emits edges as a flat list;
  turning that into `adj` once means every later "what's next to X?" is a dict
  access. Each edge is added in both directions, so a query around
  `invalidate()` surfaces both what it calls *and* what calls it.
- **Sets collapse duplicates.** Two edges between the same pair become one
  neighbor, so "degree" here means *number of distinct neighbors*.
- **The `if source in adj and target in adj` guard** skips edges that point at
  unknown nodes. That's why `query.py` never has to check that a neighbor
  exists.

Optional, not needed for anything in this spec: `Node = {...}` is a plain dict
whose values happen to be classes. It runs fine, but pyright/mypy can't use it
as a type. If a type checker complains, declaring `Node` as a `TypedDict` with
the same four fields is the fix, and nothing else changes.

### `graph/query.py` — BFS and ranking

```python
from .loader import AdjacencyMap, Node, NodeLookup

MAX_NEIGHBORS_SHOWN = 10


def _matches(node: Node, wanted: list[str]) -> bool:
    parts = (node["id"], node["name"], node["source_location"])
    text = " ".join(part for part in parts if part).lower()
    return any(keyword in text for keyword in wanted)


def bfs_query(
    nodes: NodeLookup,
    adj: AdjacencyMap,
    keywords: list[str],
    depth: int = 1,
) -> list[Node]:
    if isinstance(keywords, str):          # model sent "session" instead of ["session"]
        keywords = [keywords]
    wanted = [str(k).lower() for k in keywords if str(k).strip()]   # a blank would match everything

    start_ids = [node_id for node_id, node in nodes.items() if _matches(node, wanted)]

    visited = set(start_ids)
    frontier = list(start_ids)

    for _ in range(depth):
        next_frontier = []
        for node_id in frontier:
            for neighbor_id in adj[node_id]:
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    next_frontier.append(neighbor_id)
        frontier = next_frontier

    return [nodes[node_id] for node_id in sorted(visited)]


def top_nodes(nodes: NodeLookup, adj: AdjacencyMap, n: int = 5) -> list[Node]:
    ranked = sorted(nodes.values(), key=lambda node: (-len(adj[node["id"]]), node["id"]))
    return ranked[:n]


def _describe(node: Node) -> str:
    head = f"{node['id']} [{node['type'] or 'unknown'}]"
    if node["name"]:
        head += f" {node['name']}"
    if node["source_location"]:
        head += f" @ {node['source_location']}"
    return head


def format_nodes(nodes: list[Node], adj: AdjacencyMap) -> str:
    if not nodes:
        return "(no matching nodes)"
    lines = []
    for node in nodes:
        neighbors = sorted(adj[node["id"]])
        if neighbors:
            shown = neighbors[:MAX_NEIGHBORS_SHOWN]
            hidden = len(neighbors) - len(shown)
            tail = ", ".join(shown) + (f" (+{hidden} more)" if hidden else "")
        else:
            tail = "(none)"
        lines.append(f"{_describe(node)} — neighbors: {tail}")
    return "\n".join(lines)
```

- **Keyword matching is a substring test** over `id`, `name` and
  `source_location` joined into one lowercase string. So `"session"` hits
  `create_session()`, `session.py` and anything under `auth/session.py`. False
  positives are possible (`"auth"` also matches `author`). That's fine: the
  output is context for the model, which can narrow with a follow-up query.
- **The two lines at the top of `bfs_query` replace a validation function.**
  A bare string is wrapped into a list (a `"session"` would otherwise be
  iterated letter by letter), and blank keywords are dropped because the empty
  string is a substring of everything and would match the whole graph.
- **The BFS.** Each pass through `for _ in range(depth)` is one hop outward.
  `visited` stops a node being walked twice, and `frontier` / `next_frontier`
  separate "nodes I'm expanding now" from "nodes I found this hop". `depth=0`
  returns only the matches; `depth=1` (what the tool uses) adds their direct
  neighbors.
- **`sorted(visited)`** because sets have no guaranteed order. Sorting is what
  makes "assert the output is exactly this string" a valid test.
- **Ranking is `(-degree, id)`.** Negating just the degree gives degree
  descending with id ascending as the tiebreak in one `sorted()` call
  (`reverse=True` would flip both).
- **`format_nodes` caps neighbors at 10** with a `(+N more)` marker. Real
  graphs have hub nodes with hundreds of neighbors, and it's better for the
  model to see every matched node with a short neighbor list than to lose whole
  nodes when stage 5's `truncate_tokens` cuts the string.

### `tools/graph_query.py` and `tools/top_nodes.py`

```python
# tools/graph_query.py
from ..graph import query
from ..graph.loader import AdjacencyMap, NodeLookup


def run(args: dict, nodes: NodeLookup, adj: AdjacencyMap) -> str:
    found = query.bfs_query(nodes, adj, args["keywords"])
    return query.format_nodes(found, adj)
```

```python
# tools/top_nodes.py
from ..graph import query
from ..graph.loader import AdjacencyMap, NodeLookup


def run(args: dict, nodes: NodeLookup, adj: AdjacencyMap) -> str:
    n = int(args.get("n", 5))
    return query.format_nodes(query.top_nodes(nodes, adj, n), adj)
```

No validation here, on purpose (see the error policy). A missing `keywords`
raises `KeyError`, a non-numeric `n` raises `ValueError`, and dispatch turns
either into a message the model can act on. `int(...)` also quietly accepts
`"5"`, which small models send often.

### Fixture — `tests/fixtures/graph.json`

A tiny fake auth module: 10 nodes and 9 edges, enough to make BFS and ranking
non-trivial. Field names are graphify's, so your `load_graph` runs on it
unchanged.

```json
{
  "nodes": [
    {"id": "auth/session.py", "label": "session.py", "file_type": "code", "source_location": "auth/session.py:1"},
    {"id": "auth/session.py:create_session", "label": "create_session()", "file_type": "code", "source_location": "auth/session.py:12"},
    {"id": "auth/session.py:invalidate", "label": "invalidate()", "file_type": "code", "source_location": "auth/session.py:30"},
    {"id": "auth/token.py", "label": "token.py", "file_type": "code", "source_location": "auth/token.py:1"},
    {"id": "auth/token.py:mint_token", "label": "mint_token()", "file_type": "code", "source_location": "auth/token.py:8"},
    {"id": "api/routes.py", "label": "routes.py", "file_type": "code", "source_location": "api/routes.py:1"},
    {"id": "api/routes.py:login", "label": "login()", "file_type": "code", "source_location": "api/routes.py:14"},
    {"id": "api/routes.py:logout", "label": "logout()", "file_type": "code", "source_location": "api/routes.py:27"},
    {"id": "db/models.py", "label": "models.py", "file_type": "code", "source_location": "db/models.py:1"},
    {"id": "db/models.py:User", "label": "User", "file_type": "code", "source_location": "db/models.py:5"}
  ],
  "edges": [
    {"source": "auth/session.py", "target": "auth/session.py:create_session"},
    {"source": "auth/session.py", "target": "auth/session.py:invalidate"},
    {"source": "auth/session.py:create_session", "target": "auth/token.py:mint_token"},
    {"source": "auth/token.py", "target": "auth/token.py:mint_token"},
    {"source": "api/routes.py", "target": "api/routes.py:login"},
    {"source": "api/routes.py", "target": "api/routes.py:logout"},
    {"source": "api/routes.py:login", "target": "auth/session.py:create_session"},
    {"source": "api/routes.py:logout", "target": "auth/session.py:invalidate"},
    {"source": "db/models.py", "target": "db/models.py:User"}
  ]
}
```

The field *names* are real; the *values* are hand-made stand-ins.
`file_type: "code"` and the `path:line` shape of `source_location` are
reasonable guesses, not copied from a real graph. When you have a real
`graph.json`, compare and adjust the fixture and the expected strings in the
tests. Edges are written in one direction; `load_graph` makes them undirected
in memory.

**What the fixture looks like after loading** (ids shortened):

| Node | Neighbors in `adj` | Degree |
|---|---|---|
| `create_session` | `session.py`, `mint_token`, `login` | 3 |
| `session.py` | `create_session`, `invalidate` | 2 |
| `invalidate` | `session.py`, `logout` | 2 |
| `mint_token` | `create_session`, `token.py` | 2 |
| `routes.py` | `login`, `logout` | 2 |
| `login` | `routes.py`, `create_session` | 2 |
| `logout` | `routes.py`, `invalidate` | 2 |
| `token.py` | `mint_token` | 1 |
| `models.py` | `User` | 1 |
| `User` | `models.py` | 1 |

The degrees sum to 18, which is 9 edges counted from both ends — a quick check
that the undirected build worked. Ranking puts `create_session` first (the
only degree-3 node), then breaks the six-way degree-2 tie alphabetically by
full id: `api/routes.py`, `api/routes.py:login`, `api/routes.py:logout`,
`auth/session.py`, and so on.

**`bfs_query(["session"], depth=1)`, step by step:**

1. **Seeds.** Three nodes contain `"session"` in their search text:
   `auth/session.py`, `auth/session.py:create_session` and
   `auth/session.py:invalidate`.
2. **Hop 1.** `create_session` adds `mint_token` and `login`; `invalidate`
   adds `logout`; `session.py` only leads to the other two seeds. Six nodes.
3. **Sort and return.**

`login` and `logout` show up only because `adj` is undirected. For a question
like "how does session expiry work?", knowing that `logout` is what calls
`invalidate` is exactly the piece you want.

### Tests — `tests/test_graph.py`

```python
import json
from pathlib import Path

import pytest

from lean.graph.loader import load_graph
from lean.graph.query import bfs_query, format_nodes, top_nodes

FIXTURE = Path(__file__).parent / "fixtures" / "graph.json"


def write_graph(tmp_path, data) -> Path:
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ---- loader (your code) ----

def test_load_graph_translates_graphify_fields():
    nodes, _ = load_graph(FIXTURE)
    assert len(nodes) == 10
    assert nodes["auth/session.py:create_session"] == {
        "id": "auth/session.py:create_session",
        "type": "code",                       # graphify's file_type
        "name": "create_session()",           # graphify's label
        "source_location": "auth/session.py:12",
    }


def test_load_graph_builds_undirected_adjacency():
    nodes, adj = load_graph(FIXTURE)
    assert set(adj) == set(nodes)
    # mint_token is never a `source` in the fixture, yet it knows both nodes that point at it
    assert adj["auth/token.py:mint_token"] == {"auth/session.py:create_session", "auth/token.py"}


def test_load_graph_drops_edges_to_unknown_nodes(tmp_path):
    path = write_graph(tmp_path, {
        "nodes": [{"id": "a"}, {"id": "b"}],
        "edges": [{"source": "a", "target": "b"}, {"source": "a", "target": "ghost"}],
    })
    _, adj = load_graph(path)
    assert adj == {"a": {"b"}, "b": {"a"}}


def test_load_graph_missing_optional_fields_become_none(tmp_path):
    nodes, _ = load_graph(write_graph(tmp_path, {"nodes": [{"id": "a"}]}))
    assert nodes["a"] == {"id": "a", "type": None, "name": None, "source_location": None}


def test_load_graph_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_graph(tmp_path / "nope.json")


# ---- query ----

def test_bfs_query_session_depth_1():
    nodes, adj = load_graph(FIXTURE)
    result = bfs_query(nodes, adj, ["session"], depth=1)
    assert [n["id"] for n in result] == [
        "api/routes.py:login",
        "api/routes.py:logout",
        "auth/session.py",
        "auth/session.py:create_session",
        "auth/session.py:invalidate",
        "auth/token.py:mint_token",
    ]


def test_bfs_query_depth_0_returns_only_keyword_matches():
    nodes, adj = load_graph(FIXTURE)
    result = bfs_query(nodes, adj, ["session"], depth=0)
    assert [n["id"] for n in result] == [
        "auth/session.py",
        "auth/session.py:create_session",
        "auth/session.py:invalidate",
    ]


def test_bfs_query_is_case_insensitive():
    nodes, adj = load_graph(FIXTURE)
    assert bfs_query(nodes, adj, ["SESSION"]) == bfs_query(nodes, adj, ["session"])


def test_bfs_query_no_match():
    nodes, adj = load_graph(FIXTURE)
    assert bfs_query(nodes, adj, ["nonexistent"]) == []
    assert format_nodes([], adj) == "(no matching nodes)"


def test_bfs_query_ignores_blank_keywords_and_accepts_a_bare_string():
    nodes, adj = load_graph(FIXTURE)
    assert bfs_query(nodes, adj, [""]) == []                # blank must not match the whole graph
    assert bfs_query(nodes, adj, ["  ", "user"]) == bfs_query(nodes, adj, ["user"])
    assert bfs_query(nodes, adj, "session") == bfs_query(nodes, adj, ["session"])


def test_format_nodes_exact_output():
    nodes, adj = load_graph(FIXTURE)
    result = bfs_query(nodes, adj, ["user"], depth=1)
    assert format_nodes(result, adj) == (
        "db/models.py [code] models.py @ db/models.py:1 — neighbors: db/models.py:User\n"
        "db/models.py:User [code] User @ db/models.py:5 — neighbors: db/models.py"
    )


def test_format_nodes_caps_neighbor_list():
    hub = {"id": "hub", "type": "code", "name": None, "source_location": None}
    adj = {"hub": {f"leaf{i:02d}" for i in range(12)}}
    out = format_nodes([hub], adj)
    assert out.startswith("hub [code] — neighbors: leaf00")
    assert out.endswith("leaf09 (+2 more)")


def test_top_nodes_ranks_by_degree():
    nodes, adj = load_graph(FIXTURE)
    result = top_nodes(nodes, adj, n=5)
    assert [n["id"] for n in result] == [
        "auth/session.py:create_session",   # degree 3, the only hub
        "api/routes.py",                    # degree 2 from here down, id-ordered
        "api/routes.py:login",
        "api/routes.py:logout",
        "auth/session.py",
    ]
```

Two are worth a second look. `test_load_graph_builds_undirected_adjacency`
proves the loader's most important design choice, and every exact-output query
test depends on it. `test_bfs_query_ignores_blank_keywords_and_accepts_a_bare_string`
covers the two guard lines in `bfs_query`.

---

## Stage 4 — `read_file` / `write_md` / `truncate`

### `pipeline/truncate.py`

```python
def truncate_lines(lines: list[str], max_lines: int) -> tuple[list[str], int]:
    kept = lines[:max_lines]
    remaining = max(0, len(lines) - max_lines)
    return kept, remaining


def truncate_tokens(text: str, max_tokens: int) -> str:
    max_chars = max_tokens * 4  # rough heuristic, ~4 chars/token, no real tokenizer needed
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n...[truncated]"
```

Two functions, two jobs. `read_file` uses `truncate_lines` to bound what it
shows in the first place, and returns *how many lines were cut* so the caller
can say how much is missing. `truncate_tokens` is the generic safety net that
dispatch (stage 5) applies to every tool's result. It's a hard cut at a
character count, not a line or sentence boundary, which is fine for a safety
net; no real tokenizer needed yet.

### `tools/read_file.py`

```python
from pathlib import Path

from ..pipeline.truncate import truncate_lines


def run(args: dict, root: Path | None, max_lines: int) -> str:
    target = (root or Path.cwd()) / args["path"]
    offset = int(args.get("offset", 0))

    all_lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    shown, remaining = truncate_lines(all_lines[offset:], max_lines)

    body = "\n".join(shown) if shown else "(no lines at this offset)"
    if remaining:
        body += f"\n...[{remaining} more lines, use offset={offset + max_lines} to continue]"
    return body
```

- **Slicing never raises.** `all_lines[offset:]` with an offset past the end
  returns `[]`, not an `IndexError`, so "offset past EOF" needs no bounds check
  and shows `(no lines at this offset)`.
- **The trailer tells the model exactly what to pass next**
  (`use offset=50 to continue`), so it never has to do the arithmetic.
- **A missing file just raises `FileNotFoundError`.** Dispatch reports it to
  the model; there's no "no such file" check to write.

Paging through a 120-line file with `max_lines=50`:

| Call | Shows | Trailer |
|---|---|---|
| `{"path": "a.py"}` | lines 1–50 | `...[70 more lines, use offset=50 to continue]` |
| `{"path": "a.py", "offset": 50}` | lines 51–100 | `...[20 more lines, use offset=100 to continue]` |
| `{"path": "a.py", "offset": 100}` | lines 101–120 | none |
| `{"path": "a.py", "offset": 500}` | `(no lines at this offset)` | none |

### `tools/write_md.py`

```python
from pathlib import Path
from typing import Callable

from ..config import AutonomyMode

ALLOWED_SUFFIXES = {".md", ".markdown"}


def _default_confirm(path: Path) -> bool:
    answer = input(f"Write to {path}? [y/N] ")
    return answer.strip().lower() == "y"


def run(
    args: dict,
    root: Path | None,
    autonomy: AutonomyMode,
    confirm_fn: Callable[[Path], bool] | None = None,
) -> str:
    path_str = args["path"]          # read both up front, so a missing
    content = args["content"]        # argument fails before the confirm prompt

    target = (root or Path.cwd()) / path_str
    if target.suffix not in ALLOWED_SUFFIXES:
        return f"error: write_md can only write .md/.markdown files, got {target.suffix!r}"

    if autonomy == "confirm":
        confirm = confirm_fn or _default_confirm
        if not confirm(target):
            return f"write_md cancelled by user: {target}"

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"wrote {len(content)} chars to {target}"
```

- **Order of checks:** read the arguments, then the `.md` suffix, then the
  autonomy confirmation, then the write. The suffix check comes *before* the
  prompt so the user is never asked to approve a write that would be rejected.
- **Refusals return strings.** A wrong suffix and a "no" at the prompt both
  come back as normal results, so the model reads the outcome in its history.
- **`confirm_fn` is an injectable parameter** rather than a bare `input()` call
  buried in the function. Tests pass their own function; one test monkeypatches
  `input` to prove the default really reads from stdin.
- **`mkdir(parents=True, exist_ok=True)`** lets the model write
  `docs/design/notes.md` without the folder existing first.

### Tests — `tests/test_tools.py`

```python
import pytest

from lean.pipeline.truncate import truncate_lines, truncate_tokens
from lean.tools import read_file, write_md


# ---- truncate ----

def test_truncate_lines_reports_how_many_were_cut():
    assert truncate_lines(["a", "b", "c"], 2) == (["a", "b"], 1)
    assert truncate_lines(["a"], 5) == (["a"], 0)


def test_truncate_tokens_cuts_at_about_four_chars_per_token():
    assert truncate_tokens("short", 10) == "short"
    out = truncate_tokens("x" * 100, 10)
    assert out == "x" * 40 + "\n...[truncated]"


# ---- read_file ----

def test_read_file_pages_through_a_long_file(tmp_path):
    (tmp_path / "a.py").write_text("\n".join(f"line{i}" for i in range(1, 121)))
    first = read_file.run({"path": "a.py"}, root=tmp_path, max_lines=50)
    assert first.startswith("line1\n") and "line50\n" in first
    assert first.endswith("...[70 more lines, use offset=50 to continue]")

    last = read_file.run({"path": "a.py", "offset": 100}, root=tmp_path, max_lines=50)
    assert last.splitlines()[0] == "line101" and last.splitlines()[-1] == "line120"
    assert "more lines" not in last


def test_read_file_offset_past_eof(tmp_path):
    (tmp_path / "a.py").write_text("line1\nline2\n")
    result = read_file.run({"path": "a.py", "offset": 50}, root=tmp_path, max_lines=50)
    assert result == "(no lines at this offset)"


# ---- write_md ----

def test_write_md_rejects_non_markdown_with_a_message(tmp_path):
    result = write_md.run({"path": "notes.py", "content": "x"}, root=tmp_path, autonomy="auto")
    assert result.startswith("error:")
    assert not (tmp_path / "notes.py").exists()


def test_write_md_accepts_markdown_in_auto_mode_and_creates_folders(tmp_path):
    result = write_md.run({"path": "docs/design/notes.md", "content": "hello"}, root=tmp_path, autonomy="auto")
    assert (tmp_path / "docs" / "design" / "notes.md").read_text() == "hello"
    assert "wrote" in result


def test_write_md_confirm_mode_blocks_without_approval(tmp_path):
    result = write_md.run(
        {"path": "notes.md", "content": "hello"},
        root=tmp_path, autonomy="confirm", confirm_fn=lambda _path: False,
    )
    assert not (tmp_path / "notes.md").exists()
    assert "cancelled" in result


def test_write_md_default_confirm_reads_stdin(tmp_path, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    result = write_md.run({"path": "notes.md", "content": "hello"}, root=tmp_path, autonomy="confirm")
    assert not (tmp_path / "notes.md").exists()
    assert "cancelled" in result


def test_write_md_missing_argument_fails_before_the_confirm_prompt(tmp_path):
    def never_asked(_path):
        raise AssertionError("the user should not be asked to approve a call that can't succeed")

    with pytest.raises(KeyError):
        write_md.run({"path": "notes.md"}, root=tmp_path, autonomy="confirm", confirm_fn=never_asked)
```

---

## Stage 5 — Fake LLM + `dispatch.py`

The highest-leverage stage: once this is in place, every later stage (context
assembly, the real Ollama client, both agents) gets tested by scripting
responses instead of running a model.

### `pipeline/llm.py` — an interface, not an implementation

```python
from typing import Protocol


class LLMClient(Protocol):
    def complete(self, messages: list[dict]) -> dict:
        """Return one parsed action: {"tool": ..., "args": ...} or {"done": True, "message": ...}."""
        ...
```

`Protocol` is structural: nothing has to subclass `LLMClient`. Anything with a
matching `complete(self, messages)` method satisfies it, so the fake below and
the real Ollama client (stage 7) both just need the right method shape.

### `tests/support/fake_llm.py` — scriptable, not a mock

```python
class ScriptedLLM:
    def __init__(self, responses: list[dict]):
        self._responses = list(responses)
        self.calls: list[list[dict]] = []  # a snapshot of every `messages` list it was called with

    def complete(self, messages: list[dict]) -> dict:
        self.calls.append(list(messages))  # copy: run_turn keeps appending to the same list
        if not self._responses:
            raise AssertionError("ScriptedLLM ran out of scripted responses")
        return self._responses.pop(0)
```

Recording `self.calls` costs nothing now and pays off from stage 6 onward, when
you'll want to assert *what got sent* on each loop iteration. It stores a
**copy** of each `messages` list (`list(messages)`): `run_turn` keeps appending
to one list, so storing the reference would make every recorded call show the
final history.

### `pipeline/dispatch.py`

```python
from pathlib import Path
from typing import Callable

from ..config import LeanConfig
from ..graph.loader import AdjacencyMap, NodeLookup
from ..tools import graph_query, read_file, top_nodes, write_md
from .llm import LLMClient
from .truncate import truncate_tokens


def build_registry(
    config: LeanConfig,
    nodes: NodeLookup,
    adj: AdjacencyMap,
    root: Path | None = None,
) -> dict[str, Callable]:
    return {
        "graph_query": lambda args: graph_query.run(args, nodes, adj),
        "top_nodes": lambda args: top_nodes.run(args, nodes, adj),
        "read_file": lambda args: read_file.run(args, root=root, max_lines=config.file_read_lines),
        "write_md": lambda args: write_md.run(args, root=root, autonomy=config.autonomy),
    }


def run_turn(llm: LLMClient, tools: dict[str, Callable], task: str, max_iterations: int = 25) -> str:
    history = [{"role": "user", "content": task}]

    for _ in range(max_iterations):
        action = llm.complete(history)

        if action.get("done"):
            return action.get("message", "")

        tool_name = action.get("tool")
        if tool_name not in tools:
            history.append({"role": "tool_error", "content": f"unknown tool: {tool_name!r}"})
            continue

        try:
            result = tools[tool_name](action.get("args", {}))
        except Exception as exc:
            history.append({"role": "tool_error", "content": f"{type(exc).__name__}: {exc}"})
            continue

        capped = truncate_tokens(result, max_tokens=1500)
        history.append({"role": "tool_result", "tool": tool_name, "content": capped})

    raise RuntimeError(f"no 'done' signal after {max_iterations} iterations")
```

**Wiring: loader → registry → loop**

```text
nodes, adj = load_graph(paths.graph_path(root))      # yours; FileNotFoundError if not indexed
tools = build_registry(config, nodes, adj, root)     # binds graph + config into four callables
answer = run_turn(llm, tools, task)
```

`build_registry` closes over `nodes` and `adj`, so dispatch only ever sees
one-argument callables (`tools[name](args)`) and doesn't know a graph exists.
The graph loads once per process, not once per tool call.

**How `run_turn` works, one iteration at a time:**

1. **Ask the model.** `llm.complete(history)` returns one action dict.
2. **`{"done": True, ...}`** ends the loop and returns the message.
3. **An unknown tool name** appends a `tool_error` entry and loops. The model
   sees its own mistake next turn and can correct it.
4. **A known tool is called** with `action["args"]`. Anything it raises is
   caught, prefixed with the exception's type name, and appended as a
   `tool_error`.
5. **On success** the result goes through `truncate_tokens` and is appended as
   a `tool_result`.
6. **The only exit is `done`.** After `max_iterations` without one, the loop
   raises `RuntimeError`.

`history` is a stand-in, not real context assembly. It's just enough structure
to prove the loop terminates and appends the right things in the right order;
stage 6's `context.py` replaces *how it gets built*, not the loop shape. The
separate `tool_error` and `tool_result` roles let stage 6 render failures
differently from successes.

The `write_md` guard lives in `write_md.py`, not in dispatch. Dispatch always
calls through `tools["write_md"]`, so there's exactly one place where the
autonomy check is enforced, and no way for a future agent to route around it.
`test_write_md_guard_survives_dispatch` checks that the guard holds when
dispatch is the one driving the call.

### Tests — `tests/test_dispatch.py`

```python
import shutil
from pathlib import Path

import pytest

from lean import paths
from lean.config import LeanConfig
from lean.graph.loader import load_graph
from lean.pipeline.dispatch import build_registry, run_turn
from lean.tools import write_md
from tests.support.fake_llm import ScriptedLLM

FIXTURE = Path(__file__).parent / "fixtures" / "graph.json"


def test_run_turn_loops_through_tools_then_done():
    llm = ScriptedLLM([
        {"tool": "read_file", "args": {"path": "auth/session.py"}},
        {"tool": "graph_query", "args": {"keywords": ["session"]}},
        {"done": True, "message": "sessions expire via invalidate()"},
    ])
    tools = {
        "read_file": lambda args: "line1\nline2",
        "graph_query": lambda args: "auth/session.py [code] — neighbors: (none)",
    }
    result = run_turn(llm, tools, task="how does session expiry work?")
    assert result == "sessions expire via invalidate()"
    assert len(llm.calls) == 3


def test_run_turn_feeds_tool_failures_back_to_the_model(tmp_path):
    nodes, adj = load_graph(FIXTURE)
    tools = build_registry(LeanConfig(), nodes, adj, root=tmp_path)
    llm = ScriptedLLM([
        {"tool": "delete_repo", "args": {}},                                # unknown tool
        {"tool": "graph_query", "args": {}},                                # missing 'keywords'
        {"tool": "read_file", "args": {"path": "missing.py"}},              # file doesn't exist
        {"tool": "graph_query", "args": {"keywords": ["user"]}},            # finally fine
        {"done": True, "message": "ok"},
    ])
    assert run_turn(llm, tools, task="test") == "ok"

    final_history = llm.calls[-1]
    assert [m["role"] for m in final_history] == [
        "user", "tool_error", "tool_error", "tool_error", "tool_result",
    ]
    assert "delete_repo" in final_history[1]["content"]
    assert final_history[2]["content"].startswith("KeyError")
    assert final_history[3]["content"].startswith("FileNotFoundError")


def test_run_turn_raises_after_max_iterations():
    llm = ScriptedLLM([{"tool": "noop", "args": {}}] * 3)
    with pytest.raises(RuntimeError):
        run_turn(llm, tools={"noop": lambda args: "ok"}, task="test", max_iterations=3)


def test_write_md_guard_survives_dispatch(tmp_path):
    denied_paths = []

    def deny(path):
        denied_paths.append(path)
        return False

    registry = {
        "write_md": lambda args: write_md.run(args, root=tmp_path, autonomy="confirm", confirm_fn=deny),
    }
    llm = ScriptedLLM([
        {"tool": "write_md", "args": {"path": "notes.md", "content": "hello"}},
        {"done": True, "message": "not saved"},
    ])
    assert run_turn(llm, registry, task="save notes") == "not saved"
    assert not (tmp_path / "notes.md").exists()
    assert len(denied_paths) == 1


def test_registry_wires_loaded_graph_into_tools(tmp_path):
    (tmp_path / ".lean").mkdir()
    shutil.copy(FIXTURE, paths.graph_path(tmp_path))

    nodes, adj = load_graph(paths.graph_path(tmp_path))
    tools = build_registry(LeanConfig(), nodes, adj, root=tmp_path)

    assert "db/models.py:User" in tools["graph_query"]({"keywords": ["user"]})
    assert tools["top_nodes"]({"n": 1}).startswith("auth/session.py:create_session")
```

`test_run_turn_feeds_tool_failures_back_to_the_model` is the test that stands in
for all the error classes the earlier drafts had: it drives an unknown tool, a
missing argument and a missing file through the real registry and checks that
each becomes a `tool_error` while the loop carries on. The last test proves
the pieces connect: your loader's `(nodes, adj)` flows through
`build_registry` into the graph tools, end to end, using the real fixture.

---

## Checklist against the stage descriptions

- [x] Graph read path: keyword→subgraph BFS and degree ranking, exact-output
      tests, built on your `load_graph` (unchanged)
- [x] `read_file`: 50-line cap with offset; offset past EOF handled by slicing
- [x] `write_md`: `.md`/`.markdown` guard, confirm/auto autonomy modes
- [x] `truncate`: line-based (per tool) and token-based (pipeline level)
- [x] Fake LLM (`ScriptedLLM`) + `dispatch.py` tool-call loop
- [x] Unknown tool, bad arguments and missing file fail gracefully and don't
      crash the loop
- [x] `write_md` guard enforced through dispatch, not just in isolation

## Deliberately not here yet

- **Custom exception types and argument validation.** Add them when a real
  failure earns them. The likeliest first candidate is a friendly message for a
  truncated `graph.json` once stage 11 starts writing it, and a
  `FileNotFoundError` handler in the CLI at stage 9.
- **Path-traversal guarding** on `read_file` / `write_md` (rejecting `../..`
  escapes). Worth adding before this runs against untrusted input.
- **Odd numeric inputs.** A negative `n` or `offset` follows Python's slicing
  rules (`offset=-5` returns the last five lines). Harmless for now.
- **Edge direction.** `adj` is undirected, so "A calls B" and "B calls A" look
  identical to `query.py`. If the model later needs direction, store a second
  directed map *alongside* `adj`.
- **Relevance scoring** for keyword matches: no ranking by number of hits, no
  whole-word matching, no stemming.
- **Real graphify output.** Your loader already targets graphify's field
  names. Still open: *producing* `graph.json` (stage 11), and checking the
  fixture's values against a real one.
- **Loader polish.** `encoding="utf-8"` on the `open(...)` call (the platform
  default isn't UTF-8 on some Windows setups) and the `TypedDict` note above.
- `silent`/`dry-run` autonomy modes; `context_limit` and `design_doc_dir` in
  `LeanConfig` (stages 6 and 10); `summary.md` / `last_turn.md` population
  (stage 6's `context.py` is the first thing that writes them).
