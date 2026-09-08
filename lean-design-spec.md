# lean — Agentic Framework Design

**Date:** 2026-09-03
**Status:** Proposed
**Summary:** lean is a local, read-only assistant for a codebase — it answers questions, reads files, writes Markdown notes, and runs brainstorm sessions that end in a design doc. It does not write or execute code; the only tool with a side effect (`write_md`) is hard-restricted to `.md` files.

---

## Positioning

- Read-only thinking partner for a codebase — not a coding agent.
- Never touches the source tree.
- Output (a design doc) goes to a human or a separate coding agent (Claude Code, Cursor, etc.) for implementation.

---

## Architecture

```
lean/
├── cli.py              # Entry point: typer CLI, rich REPL
├── orchestrator.py     # Thin pipeline runner
├── pipeline/
│   ├── context.py      # Assembles system prompt + summary + last turn + task
│   ├── llm.py          # Ollama client, streaming
│   ├── dispatch.py     # Parses tool calls, enforces autonomy mode + write_md guard
│   └── truncate.py     # Caps file reads and tool output
├── agents/
│   ├── chat.py          # ChatAgent — free-form Q&A about the codebase
│   └── brainstorm.py    # BrainstormAgent — investigate → synthesize → draft/review/refine → design doc
├── tools/
│   ├── graph_query.py
│   ├── read_file.py
│   ├── top_nodes.py
│   └── write_md.py      # only tool with a side effect; extension-restricted
├── graph/
│   ├── loader.py        # Loads .lean/graph.json at startup
│   ├── query.py         # Keyword → BFS subgraph → compact text block
│   └── rebuild.py        # tree-sitter re-extraction, run only via `lean graph rebuild` / `lean init`
└── .lean/                # Project-scoped state (gitignored)
    ├── graph.json
    ├── graph_meta.json
    ├── summary.md
    ├── last_turn.md
    └── config.json
```

---

## Pipeline Stages

```
Task (user input)
    ↓
[context] — assembles: system prompt + tool schemas + summary.md + last_turn.md + task
    ↓
[llm] — streams response from Ollama, outputs one of:
        {"tool": "...", "args": {...}}
        {"done": true, "message": "..."}
    ↓
[dispatch] — routes the model's output
    │
    ├─ tool call: graph_query / read_file / top_nodes
    │      → runs immediately, no confirmation
    │      ↓
    │  [truncate] — caps the tool result before it re-enters context
    │               (50 lines for file reads, ~800–1,500 tokens for graph_query)
    │      ↓
    │  back to [llm] with the updated context
    │
    ├─ tool call: write_md
    │      → autonomy mode gates the write (confirm / auto / silent / dry-run)
    │      → path checked against .md / .markdown, rejected if it doesn't match
    │      → file written to disk, confirmation reported to chat
    │      ↓
    │  back to [llm] with the updated context
    │
    └─ {"done": true, "message": "..."}
           → message printed straight to chat, turn ends
```

- `write_md` is the only branch that touches disk; `done` is the only branch that ends the loop — every other tool call loops back through `[truncate]` into another `[llm]` call.
- The graph is never re-indexed automatically — rebuilds only happen via an explicit `lean graph rebuild` (e.g. after editing code yourself, or a `git pull`).
- The model never touches the filesystem directly — every action routes through `dispatch.py`, which validates the tool call and, for `write_md`, the target path.

---

## Tool Set

| Tool | Args | Behavior |
|------|------|----------|
| `graph_query` | `keywords: list[str]` | BFS query against `graph.json`, returns compact subgraph |
| `read_file` | `path: str, offset?: int` | Reads file, hard-capped at 50 lines from offset |
| `top_nodes` | `n?: int` | Returns the graph's highest-connectivity nodes — orientation without a keyword |
| `write_md` | `path: str, content: str` | Writes/overwrites a **Markdown file only** |

**Tool call format:**
```json
{"tool": "read_file", "args": {"path": "src/auth.py"}}
```

**Done signal:**
```json
{"done": true, "message": "Session expiry is enforced in auth/session.py:112 via expires_at"}
```

- `graph_query`, `read_file`, `top_nodes` — pure reads, run without confirmation regardless of autonomy mode.
- `write_md` — the only tool with a side effect; path must resolve to `.md`/`.markdown` or the call is rejected outright, error fed back into context.
- No tool can create, modify, or delete a source file, run a shell command, or execute code — that surface doesn't exist in this build.
- `write_md` is optional: for anything that doesn't warrant a saved file, the model just answers via `{"done": true, "message": "..."}` instead. Reserved for a finished design doc or an explicit save request, never a default reflex.

---

## Context Strategy

- **Lazy graph injection** — the model calls `graph_query` or `top_nodes` when it needs orientation; nothing graph-related is pre-loaded before the first LLM call.
- **Compressed history** — raw turns are discarded after each task; a one-sentence summary is appended to `.lean/summary.md`, and the immediately-preceding turn is kept in full in `.lean/last_turn.md` until the next task starts.
- **Fresh-session baseline** — ~650–750 tokens (system prompt + tool schemas ~350–450, `summary.md` ~200, current task ~100).

---

## Project State (`.lean/`)

```
.lean/
├── graph.json       # Graphify output — queried on demand, never injected raw
├── graph_meta.json  # {filepath: sha256} for incremental tree-sitter rebuilds
├── summary.md       # Plain-text running log of completed tasks
├── last_turn.md      # Full text of the most recent turn, cleared on /clear
└── config.json       # Project-level overrides
```

**`config.json` schema:**
```json
{
  "model": "qwen2.5-coder:32b",
  "context_limit": 16000,
  "autonomy": "confirm",
  "file_read_lines": 50,
  "design_doc_dir": "docs/design"
}
```

- `design_doc_dir` — default folder `write_md` targets when `BrainstormAgent` saves a design doc without an explicit path.
- Model choice — coder-tuned or general reasoning models both work; lean never asks the model to emit code.
- `lean init` — runs the initial tree-sitter pass (no LLM).
- `lean graph rebuild` — the only way the graph updates afterward; no automatic rebuild path exists.

---

## Agents

### `ChatAgent`
- Tools: `graph_query`, `read_file`, `top_nodes`, `write_md`.
- Default: answers in chat. Calls `write_md` only on request (e.g. "save this to `notes/auth-flow.md`").

### `BrainstormAgent`
- Flow: investigate → synthesize → draft → review → approve/refine (refinement cap: 1) → `write_md`.
- `--quick` — skips draft/review, prints a 2-question feasibility verdict to stdout; nothing saved.

---

## Skills and Tool Access

| Skill | Tools |
|---|---|
| `chat` | `graph_query`, `read_file`, `top_nodes`, `write_md` |
| `brainstorm` | `graph_query`, `read_file`, `top_nodes`, `write_md`, `transition_phase`, `approve_draft`, `propose_refinement` |

- **Custom skills** — create `.lean/skills/chat.md` or `.lean/skills/brainstorm.md` to override the bundled skill of the same name.

---

## CLI Interface

**REPL slash commands:**
- `/chat` — free conversation about the codebase (default: plain text at the base prompt)
- `/brainstorm <topic>` — session ending in a design doc; `--quick` for the 2-question verdict; bare `/brainstorm` resumes the most recent session
- `/exit` — abort the active verb, return to base prompt
- `/quit` — exit the REPL (also Ctrl-D)
- `/clear` — reset session memory (`summary.md`, `last_turn.md`) and token counter
- `/help [<verb>]`
- `/status`

**One-shot subcommands:**
```bash
lean "how does session expiry work in this codebase?"    # defaults to chat
lean brainstorm "should we add streaming responses?"       # deep mode
lean brainstorm --quick "should we add streaming?"
lean status
```

- **@-mentions** — `@lean/cli.py` attaches file contents as a tool result inline.

**Example — chat:**
```
[lean] how does session expiry work in this codebase?
  → graph_query ["session", "expiry", "auth"] ... 6 nodes
  → read_file auth/session.py (lines 1-50)
  → Done: Sessions are minted in create_session() with a 30-minute TTL in Redis;
    session.py:112 checks expires_at on every request and calls invalidate() if past due.
```

- **Provider/model overrides** — `--model`, `--provider`
- **Configuration** — `lean config`, `lean config set`
- **Graph operations** — `lean graph rebuild`

---

## Token Flow

**Sent to Ollama:**
- Core system prompt (~350–450 tokens): role, JSON-only rule, tool-call examples, navigation rules
- Skill content (~300–900 tokens, when active): `chat.md` or `brainstorm.md` inlined
- Last turn recap (~1,000–1,500 tokens, or 0 if cleared)
- Session summary (~2,000–3,500 tokens, or 0 if cleared)
- **Fresh-session baseline:** ~350–450 tokens

---

## Testing

- `pytest tests/ -v` — run all tests
- `pytest tests/test_cli.py` — a specific test file

---

## Credits & License

- Inspired by [obra/superpowers](https://github.com/obra/superpowers) (agentic workflow structure) and [safishamsi/graphify](https://github.com/safishamsi/graphify) (codebase graph engine, used read-only)
- MIT License
