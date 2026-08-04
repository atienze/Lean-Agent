# lean — Agentic Framework Design

**Date:** 2026-04-18
**Status:** Approved

---

## Overview

`lean` is a local coding assistant CLI built on top of Ollama. It is designed to work on consumer hardware (24GB VRAM) by keeping the model's context window as small as possible at all times. It uses a graph-first context strategy, lazy tool injection, and compressed session history to stay lean across arbitrarily long sessions.

---

## Architecture

Pipeline architecture. The orchestrator is a thin loop that passes state through discrete, single-purpose stages. Each stage has one input and one output. Stages are independently testable and swappable.

```
lean/
├── cli.py              # Entry point: typer CLI, rich REPL
├── orchestrator.py     # Thin pipeline runner
├── pipeline/
│   ├── context.py      # Assembles system prompt + summary + task
│   ├── llm.py          # Ollama client, streaming
│   ├── dispatch.py     # Parses tool calls, enforces autonomy mode
│   └── truncate.py     # Caps file reads and bash output
│   # Note: graph_query is a tool (tools/), not a pipeline stage
├── tools/
│   ├── graph_query.py
│   ├── read_file.py
│   ├── write_file.py
│   └── bash.py
├── graph/
│   ├── loader.py       # Loads .lean/graph.json at startup
│   ├── query.py        # Keyword → BFS subgraph → compact text block
│   └── rebuild.py      # tree-sitter re-extraction after write_file
└── .lean/              # Project-scoped state (gitignored)
    ├── graph.json
    ├── graph_meta.json
    ├── summary.md
    └── config.json
```

---

## Pipeline Stages

Each turn of the agent loop runs these stages in order:

```
Task (user input)
    ↓
[context] — assembles: system prompt + tool schemas + summary.md + task
    ↓
[llm] — streams response from Ollama
        model outputs: {"tool": "...", "args": {...}}
        or:            {"done": true, "message": "..."}
    ↓
[dispatch] — routes tool call to handler
             applies autonomy mode (confirm / auto / silent / dry-run)
    ↓
[truncate] — caps tool result before re-entering context
             (50 lines for file reads, 500 chars for bash output)
    ↓
[rebuild] — if tool was write_file, re-extracts changed files
            via tree-sitter, patches graph.json in place
    ↓
back to [llm] with updated context, or exit if done
```

The model never accesses the filesystem directly. All actions are routed through `dispatch.py`, which validates the tool call schema and rejects malformed calls with an error fed back into context.

---

## Tool Set

The model has exactly four tools, defined as JSON schemas injected into the system prompt:

| Tool | Args | Behavior |
|------|------|----------|
| `graph_query` | `keywords: list[str]` | BFS query against graph.json, returns compact subgraph |
| `read_file` | `path: str, offset?: int` | Reads file, hard-capped at 50 lines from offset |
| `write_file` | `path: str, content: str` | Writes file, triggers graph rebuild |
| `bash` | `command: str` | Runs shell command, output capped at 500 chars |

**Tool call format:**
```json
{"tool": "read_file", "args": {"path": "src/auth.py"}}
```

**Done signal:**
```json
{"done": true, "message": "Fixed session expiry bug in auth/session.py line 34"}
```

`dispatch.py` validates schema on every response. Malformed output returns an error into context without executing anything.

**Why only four tools:** `graph_query` is the navigation primitive. The model cannot grep or glob blindly — if it needs to find files it asks the graph, and only reads a specific file if the graph summary isn't sufficient. This is the primary mechanism that keeps context lean.

---

## Context Strategy

**Lazy graph injection.** The graph subgraph is not pre-loaded before the first LLM call. The model calls `graph_query` when it needs orientation. This removes ~1,500 tokens from the baseline context. The model only pays the graph cost when it actually needs it.

**Compressed history.** Raw message turns are discarded after each completed task. The orchestrator writes a one-sentence summary to `.lean/summary.md`. Each new session injects only `summary.md` (~200 tokens) rather than accumulated raw history.

**Baseline context per turn (before any tool calls):**
- System prompt + tool schemas: ~800 tokens
- `summary.md`: ~200 tokens
- Current task: ~100 tokens
- **Total: ~1,100 tokens**

**Context growth across a session:**

| Turn | lean (lazy + compressed) | Naive (eager + raw history) |
|------|--------------------------|------------------------------|
| 1    | ~1,100                   | ~2,400                       |
| 5    | ~1,100                   | ~3,900                       |
| 10   | ~1,100                   | ~5,400                       |
| 20   | ~1,100                   | ~8,400                       |

The lean approach stays flat. The naive approach grows linearly and on an 8k context budget hits the wall around turn 10-12.

---

## Project State (`.lean/`)

Created on `lean init` or first run in a directory. Gitignored by default.

```
.lean/
├── graph.json       # Graphify output — queried on demand, never injected raw
├── graph_meta.json  # {filepath: sha256} for incremental tree-sitter rebuilds
├── summary.md       # Plain-text running log of completed tasks (~200 tokens)
└── config.json      # Project-level overrides
```

**`config.json` schema:**
```json
{
  "model": "qwen2.5-coder:32b",
  "context_limit": 16000,
  "autonomy": "confirm",
  "file_read_lines": 50,
  "bash_output_chars": 500
}
```

All config values are overridable via CLI flags per invocation.

**Graph lifecycle:**
- `lean init` — runs Graphify's tree-sitter pass over the project (free, no LLM). Builds `graph.json` cold. If `.lean/graph.json` is missing at runtime, lean detects this and prompts the user to run `lean init` before proceeding.
- Each `write_file` — `rebuild.py` checks SHA256 of changed files, re-extracts only what changed, patches `graph.json` in place. Near-instant.
- `lean graph rebuild` — manual full rebuild (e.g., after a large `git pull`).

**Summary lifecycle:**
- After each completed task, orchestrator appends one sentence to `summary.md`.
- `summary.md` is the only history that persists between sessions.
- Raw turns from the current session are held in memory only; discarded on exit.

---

## CLI Interface

**One-shot task:**
```bash
lean "fix the session expiry bug in auth"
lean --auto "add rate limiting to the API routes"
lean --silent "fix the auth bug"
lean --dry-run "refactor the database layer"
```

**Interactive REPL (no args):**
```bash
lean
> fix the session expiry bug in auth
> now add tests for it
> done
```

**Project setup:**
```bash
lean init           # Graphify tree-sitter pass, creates .lean/
lean graph rebuild  # Manual full graph rebuild
lean config         # View/edit .lean/config.json
```

---

## Autonomy Modes

Controlled by `dispatch.py`. Applied to `write_file` and `bash` tool calls.

| Mode | Display tool calls | Pause for confirm | Execute |
|------|--------------------|-------------------|---------|
| default | ✓ | ✓ | ✓ |
| `--auto` | ✓ | ✗ | ✓ |
| `--silent` | ✗ | ✗ | ✓ |
| `--dry-run` | ✓ | ✗ | ✗ |

`--silent` prints only the final done message. Exit code reflects success/failure, making it composable in shell pipelines:

```bash
lean --silent "fix the auth bug" && git commit -m "auth fix"
```

Tool call streaming (in non-silent modes) is purely stdout via `rich` — zero context cost.

**REPL output example (`--auto`):**
```
[lean] add rate limiting to the API routes
  → graph_query ["rate", "limiting", "routes"] ... 4 nodes
  → read_file routes/api.py (lines 1-50)
  → write_file routes/api.py ✓
  → bash pytest tests/test_api.py ... passed
  → Done: added RateLimiter middleware to all /api/* routes
```

---

## Graphify Integration

lean uses Graphify's output (`graph.json`) as a read-only lookup table. It does not reimplement Graphify — it queries the JSON structure.

**`graph/query.py`:** Given keywords extracted from the task (via simple tokenization + stopword removal — no LLM call), finds matching nodes in `graph.json`, does a 1-2 hop BFS to get neighbors, returns the subgraph as a compact text block (~800-1,500 tokens). This is what the model sees when it calls `graph_query`.

**`graph/rebuild.py`:** After `write_file`, checks SHA256 of the written file against `graph_meta.json`. If changed, shells out to tree-sitter to re-extract that file's nodes and patches them into `graph.json`. The rest of the graph is untouched.

**What goes into context from the graph:** Only the BFS result — a compact text block listing node names, types, docstrings, and edges. Never the full `graph.json`.

---

## Language and Runtime

- **Language:** Python
- **CLI:** `typer`
- **Terminal rendering:** `rich`
- **LLM backend:** Ollama (`ollama` Python SDK)
- **Graph parsing:** tree-sitter (via Graphify)
- **Target hardware:** 24GB VRAM, quantized models (e.g., `qwen2.5-coder:32b`)
