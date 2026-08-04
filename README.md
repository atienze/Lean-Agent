# lean

A local-first agentic coding framework built on Ollama, featuring codebase graph awareness, TDD-enforced execution, and zero API costs.

> **Inspired by**: [obra/superpowers](https://github.com/obra/superpowers) for agentic AI workflows, and [safishamsi/graphify](https://github.com/safishamsi/graphify) for codebase graph analysis.


## How lean differs from Claude Code

### TDD as a state machine, not a prompt

lean's execute mode runs pytest itself in a red→green loop; the LLM only writes the test and the implementation, while the orchestrator decides when to run tests and whether to iterate. Claude Code leaves TDD discipline to the model.

### Specialized agent pipeline

The default workflow dispatches `WritePlanAgent → ExecutePlanAgent → CodeReviewAgent` with typed artifact hand-off between steps and per-agent tool allowlists. 
For example, `ExecutePlanAgent` has no `bash`, and `BrainstormAgent` has no `write_file`-like override beyond the base set. Claude Code uses one general-purpose agent that spawns ad-hoc subagents.

### Deterministic supervisor around the LLM

`ActionSupervisor` enforces Python-side circuit breakers:

- 3 consecutive parse errors trigger a stricter retry
- 3 tool rejections abort the task
- `write_file` calls that exceed +30 lines or 1.7× growth get rejected with graph context re-injected

Claude Code has no equivalent bloat or parse-error cutoffs.

### Structured review loops

`WritePlanAgent` runs a two-phase state machine (draft → review → approve or refine) with a hard refinement cap of 1. `CodeReviewAgent` runs behind a configurable `fail_on` severity gate. Planning and review are controllers, not prompt conventions.

### Minimal tool dispatch

No JSONSchema for tools; four `{"tool": "...", "args": {...}}` examples plus a Python dispatcher that validates and routes. Claude Code ships full schemas (~2,800–4,500 tokens) and defers less-common ones via `ToolSearch`.

**Bottom line:** Claude Code is a system-prompt and skill-heavy harness around a powerful model — the model drives everything via tool calls. lean pushes as much work as possible into deterministic Python (TDD loop, review gates, bloat checks, agent pipelines) so a local 10–30B model only has to do the parts that actually need reasoning.


## Key Features

- **Code graph awareness** — auto-generated knowledge graph of your codebase; agents query files/functions via `graph_query`
- **TDD execute mode** — enforced test-driven development with orchestrated pytest runs
- **Zero token cost** — runs on local Ollama (default: `deepseek-r1:14b`)
- **Token tracking** — REPL prompt shows usage vs context limit: `lean (verb) 1.2k/64k:`
- **Specialized agents** — `brainstorm`, `write-plan`, `execute`, `code-review`, each with its own tool allowlist
- **Autonomy modes** — `--auto`, `--silent`, `--dry-run` flags
- **Session memory** — persists `summary.md` and `last_turn.md` across REPL restarts
- **@-mentions** — reference files/dirs inline (e.g. `@lean/cli.py`); contents are attached as tool results
- **Hardware-tier defaults** — on `< 12 GB` RAM, `lean init` applies a `small` preset (lower context, capped output) so a 7B Q4 setup gets sensible defaults


## Installation

lean is installed from source — clone the repo and install into a Python virtual environment.

### Prerequisites

- **Python 3.11+** — check with `python --version`. Newer is fine.
- **git** — to clone the repo.
- **A local LLM server** — one of:
  - [Ollama](https://ollama.com) (recommended; default port `:11434`)
  - [llama-server](https://github.com/ggerganov/llama.cpp) (port `:8080`)
  - [LM Studio](https://lmstudio.ai) (port `:1234`)

`lean init` will probe these for you and prompt to pull a model if Ollama has none installed.

### Install

1. **Clone the repo:**

       git clone https://github.com/atienze/lean.git
       cd lean

2. **Create a virtual environment** (keeps lean's dependencies isolated from your system Python):

   On macOS / Linux:

       python3 -m venv ~/lean-env
       source ~/lean-env/bin/activate

   On Windows (PowerShell):

       python -m venv $HOME\lean-env
       $HOME\lean-env\Scripts\Activate.ps1

   You'll know it worked when your prompt is prefixed with `(lean-env)`.

3. **Install lean** in editable mode so future `git pull`s pick up new changes without reinstalling:

       pip install -e .

   This puts a `lean` command on your PATH inside the venv. Confirm with `which lean` (macOS/Linux) or `where lean` (Windows).

4. **Initialize lean in a project:**

       cd /path/to/your/project
       lean init        # probes backend, picks a model, builds the graph
       lean             # start the REPL

Whenever you want to use lean, reactivate the venv first (`source ~/lean-env/bin/activate`).

### What `lean init` does

1. Scaffolds `.lean/` (`config.json`, `summary.md`, `last_turn.md`).
2. **Probes for a local server** on the standard ports — Ollama (`:11434`), llama-server (`:8080`), LM Studio (`:1234`) — and writes the matching `provider` + `host` to `.lean/config.json`. If nothing answers, it prints a discovery catalog with install URLs and a `lean config set ...` recovery path.
3. **Resolves a model.** On Ollama with no models installed, it recommends one sized to your RAM (`qwen2.5-coder:7b` under 12 GB, `deepseek-r1:14b` at and above 12 GB) and offers to `ollama pull` it. On llama-server / LM Studio, it adopts the first model the server reports.
4. **Applies a hardware-tier preset** on `< 12 GB` RAM (`context_limit=8000`, `num_predict=1024`). `>= 12 GB` keeps today's defaults bit-identically.
5. Builds the code graph and prints a pass/fail checklist with a verdict.

Re-run `lean init` any time setup changes; existing user-set config keys are preserved.

### Updating

From inside the cloned `lean/` directory:

    git pull
    pip install -e .     # only needed if dependencies changed

Because lean is installed editable, source changes from `git pull` take effect on the next `lean` invocation.

## Usage

### REPL Mode

Start interactive mode with token tracking by running `lean` with no arguments.

REPL slash commands:

- `/chat` — free conversation with the local model. Plain text at the base prompt also activates `/chat`. (activated on default queries)
- `/brainstorm <topic>` — start brainstorming. Add `--quick` for a 2-question feasibility verdict. Bare `/brainstorm` resumes the most recent session.
- `/plan <task>` or `/plan --from-spec <path>` — write an implementation plan.
- `/execute test: <path> impl: <path>` — run the TDD execute loop.
- `/review [<path>]` — code-review the current diff or a target.
- `/workflow <task>` or `/workflow --from-spec <path>` — chain brainstorm → plan → execute → review.
- `/exit` — abort the active verb; return to the base prompt. Does **not** quit lean.
- `/quit` — exit the REPL process (also Ctrl-D).
- `/clear` — reset session memory and the token counter.
- `/help [<verb>]` — list verbs, or show details for one.
- `/status` — show token count, active verb, and current phase.

When a verb is active, the prompt shows it: `lean (brainstorm) | INVESTIGATE 1.2k/64k:`. Each agent verb stays active until it writes its completion artifact, or you `/exit`.


### One-shot subcommands

Each agent verb mirrors a CLI subcommand 1:1:

- `lean brainstorm "should we add streaming?"` — deep mode (5-phase brainstorm)
- `lean brainstorm --quick "should we add streaming?"` — 2-question feasibility verdict
- `lean plan "add retry logic to llm.py"` — inline task description
- `lean plan --from-spec docs/specs/foo-design.md` — use an existing spec
- `lean execute "test: tests/test_foo.py impl: src/foo.py"` — TDD loop on one pair
- `lean review` — review the current diff (default target)
- `lean review path/to/file.py` — review a specific path
- `lean workflow "add retry logic"` — brainstorm → plan → execute → review
- `lean workflow --from-spec docs/specs/foo-design.md` — skip the brainstorm stage
- `lean status` — re-run the `lean init` checklist without rebuilding the graph

`lean status` is CLI-only: it re-checks backend reachability, model availability, graph, and `.lean/` scaffolding, and exits non-zero when any row fails. (The REPL's `/status` is a separate in-memory snapshot.)


### Autonomy Flags

- `--auto` — no confirmation prompts
- `--dry-run` — preview actions only
- `--silent` — skip display output

These apply at the top level (e.g. `lean --auto`) or as flags on the `plan`, `execute`, `review`, and `workflow` subcommands. `brainstorm` uses the autonomy configured in `.lean/config.json`.


### Provider / Model Overrides

- `lean --model qwen2.5-coder:14b` — override model from config
- `lean --provider anthropic --model claude-sonnet-4-6` — choose `ollama` (default), `openai-compatible`, or `anthropic`
- `lean --host http://localhost:8080` — override provider base URL

`lean init` already auto-configures `provider` + `host` when it detects Ollama, llama-server, or LM Studio on a default port — the flags above are for per-invocation overrides or non-standard hosts. `lean status` displays the detected server with its friendly label (e.g. `llama-server @ http://localhost:8080` rather than the raw `openai-compatible`).


### Configuration

- `lean config` — print current config
- `lean config set context_limit 32000` — set a single value
- `lean config set model qwen2.5-coder:14b` — change the active model


### Graph Operations

- `lean graph rebuild` — re-run graphify and refresh `.lean/graph.json`

`lean` invokes graphify via `python -m graphify` against its own venv interpreter, so the graph build works without requiring `graphify` to be on `PATH`.


## Token Flow

**Sent to Ollama (lean):**

- Core system prompt (~500 tokens): role, JSON-only rule, tool-call examples, navigation rules
- Skill content (~500–1,500 tokens, when active): full skill markdown inlined
- Last turn recap (~2,000 tokens, or 0 if cleared): `.lean/last_turn.md`
- Session summary (~5,000 tokens, or 0 if cleared): `.lean/summary.md`
- **Fresh-session baseline:** ~350–500 tokens

**Sent to the Anthropic API (Claude Code):**

- Core system prompt (~4,200 tokens): role, task guidance, tone, formatting
- Environment block (~280 tokens): cwd, platform, git status, recent commits
- Global CLAUDE.md (~320 tokens): `~/.claude/CLAUDE.md`
- Project CLAUDE.md (~1,800 tokens): `./CLAUDE.md`
- Auto memory (~680 tokens): first 200 lines of `MEMORY.md`
- Tool schemas (~2,800–4,500 tokens) eager, or ~120 tokens when deferred via `ToolSearch`
- Skill index (~450 tokens): one-liners; full content loaded on demand
- Conversation history (~1,000–10,000 tokens): re-sent verbatim every turn with prompt caching; auto-compacted near the limit
- **Fresh-session baseline:** ~8,500–9,500 tokens

Claude Code numbers from the official [context window docs](https://code.claude.com/docs/en/context-window.md).

**Tracking (lean):** `stream_response()` counts `prompt_eval_count + eval_count`; the REPL prompt displays `lean (verb) [| PHASE] tokens/limit:` (e.g. `lean (brainstorm) | INVESTIGATE 1.2k/64k:`).

**Reset session:** type `/clear` in the REPL — truncates `last_turn.md`, `summary.md`, and the dead-ends ledger, and resets the token counter.


## Skills and Tool Access

Each agent runs with a per-skill tool allowlist enforced by the dispatcher. The four base tools are `graph_query`, `read_file`, `top_nodes`, and `write_file`.

- **brainstorm** — base tools only
- **write-plan** — base tools plus `transition_phase`, `approve_draft`, `propose_refinement` (phase-control signals for the two-phase state machine)
- **execute** — `graph_query`, `read_file`, `write_file` only (no `top_nodes`, no `bash`; the orchestrator drives pytest itself)
- **code-review** — base tools plus `bash` (for running test/lint commands during review)

Each REPL verb and CLI subcommand uses the matching allowlist above.

**Custom skills:** create `.lean/skills/<name>.md` (e.g. `.lean/skills/brainstorm.md`) to override the bundled skill of the same name.


## Workflows

`lean workflow "<task>"` chains the four agents end to end:

1. **BrainstormAgent** — turns the task into a design spec (skipped when `--from-spec` is given)
2. **WritePlanAgent** — turns the spec into a reviewed plan
3. **ExecutePlanAgent** — drives each plan task through the TDD state machine
4. **CodeReviewAgent** — reviews what was built

Inside the REPL, `/workflow <task>` does the same. Skip the brainstorm stage with `--from-spec path/to/spec.md` on either form (e.g. `lean workflow --from-spec docs/specs/foo.md` or `/workflow --from-spec docs/specs/foo.md`).

Configure the workflow's review gate via `codereview.fail_on`:

- `"blocker"` (default) — fail on any blocker finding
- `"important"` — fail on blocker or important
- `"any"` — fail on any finding including nits
- `"never"` — advisory mode


## Testing

- `pytest tests/ -v` — run all tests
- `pytest tests/test_cli.py` — a specific test file
- `pytest -k "token"` — tests matching a keyword


## License

MIT License
