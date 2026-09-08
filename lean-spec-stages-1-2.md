# `lean` — Implementation Spec: Stages 1–2

This covers the CLI skeleton and project-state scaffolding. No graph, no LLM —
just enough structure that `lean init` and `lean status` work and are tested.

Snippets below are illustrative, not a file to paste in whole. Where a design
choice has a "why", it's called out — skip those if you don't need them.

## Project layout

```
lean/
├── pyproject.toml
├── src/lean/
│   ├── __init__.py      # version
│   ├── paths.py         # where .lean/ files live
│   ├── config.py        # schema + load/save/init
│   └── cli.py           # typer app
└── tests/
    ├── conftest.py
    ├── test_cli.py       # stage 1
    ├── test_config.py    # stage 2, no CLI
    └── test_init.py      # stage 2, through the CLI
```

> **Python note — `src/` layout.** Put the package under `src/lean/` rather
> than a bare `lean/` next to `tests/`. It forces `pytest` and any `import
> lean` to see only the *installed* package, never files that happen to be
> sitting in your cwd. Costs one extra directory level, saves you a class of
> "works on my machine" bugs.

---

## Stage 1 — Skeleton

### `pyproject.toml`

```toml
[project]
name = "lean"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = ["typer>=0.12.3", "pydantic>=2.6"]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-mock>=3.14"]

[project.scripts]
lean = "lean.cli:main"

[tool.pytest.ini_options]
addopts = "-m 'not integration'"
markers = ["integration: requires a running Ollama."]
```

`[project.scripts]` is what turns `pip install -e .` into an actual `lean`
command on your PATH — pip reads that line and generates a tiny wrapper
script that imports `lean.cli` and calls `main()`.

The `pytest` marker is scaffolding you won't use until stage 7, but it costs
nothing to add now and saves you from forgetting it later when there's an
actual Ollama-dependent test to exclude from the default run.

Install with `pip install -e ".[dev]"` — editable mode, so code changes take
effect without reinstalling.

### `__init__.py` — one source of truth for the version

```python
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("lean")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"
```

> **Python note — `importlib.metadata`.** This reads the version from the
> *installed package's* metadata, which ultimately comes from
> `pyproject.toml`. The alternative — writing `__version__ = "0.1.0"` by hand
> in two places — guarantees they drift eventually. `PackageNotFoundError` is
> only hit if you run the module without installing it at all (rare, but
> importing a package shouldn't crash because of that).

### `cli.py` — the `status` stub

```python
import typer
from lean import __version__

app = typer.Typer(name="lean", no_args_is_help=True)

@app.command()
def status() -> None:
    """Show the lean version and config state."""
    typer.echo(f"lean {__version__}")
    # config path printing comes in stage 2, once config.py exists


def main() -> None:
    app()

if __name__ == "__main__":
    main()
```

> **Python note — Typer basics.** `@app.command()` turns a function into a
> CLI subcommand; the *type hints* on its parameters (not extra config) tell
> Typer how to build `--flag` options and validate them. You'll lean on this
> harder in stage 2, when a `Literal[...]` type hint becomes an automatic
> `--choice [a|b|c]` validator.
>
> `main()` is a one-line wrapper around `app()`. `app` is technically
> callable by itself, so `lean = "lean.cli:app"` would also work as the
> entry point — but going through `main()` gives you a seam to add
> process-wide setup later (logging config, etc.) without touching the
> Typer app.

### Test: CliRunner smoke test

```python
from typer.testing import CliRunner
from lean.cli import app

def test_status_runs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["status"])
    assert result.exit_code == 0
    assert "lean " in result.stdout
```

> **Python note — `CliRunner` and `monkeypatch`.** `CliRunner.invoke` calls
> your Typer app *in-process* (no subprocess), capturing stdout and the exit
> code. Because it's the same process, `monkeypatch.chdir(tmp_path)` — a
> built-in pytest fixture that temporarily changes the cwd and restores it
> after the test — actually affects what the command sees. `tmp_path` is
> another pytest built-in: a fresh, empty directory unique to that test run.

That's stage 1: a real, testable CLI that does almost nothing yet.

---

## Stage 2 — Project State

### `paths.py` — one place that knows the on-disk layout

```python
from pathlib import Path

LEAN_DIR_NAME = ".lean"

def lean_dir(root: Path | None = None) -> Path:
    base = root if root is not None else Path.cwd()
    return base / LEAN_DIR_NAME

def config_path(root: Path | None = None) -> Path:
    return lean_dir(root) / "config.json"

def is_initialized(root: Path | None = None) -> bool:
    return config_path(root).is_file()
```

Every function takes an optional `root` instead of always assuming
`Path.cwd()`. That's the difference between "testable by passing
`root=tmp_path`" and "testable only by `monkeypatch.chdir`-ing every test."
You'll want both later, but having the plain-argument version means
`config.py`'s own tests don't need the CLI at all.

Why a separate module instead of folding this into `config.py`? Stage 11
(graph rebuild) will add `graph.json` / `graph_meta.json` paths here too —
keeping path logic in one place means every consumer agrees on the layout
without importing `config.py` just to find a file.

### `config.py` — the schema

```python
from typing import Literal
from pydantic import BaseModel

AutonomyMode = Literal["confirm", "auto", "silent", "dry-run"]

class LeanConfig(BaseModel):
    schema_version: int = 1
    provider: str = "ollama"
    model: str = "llama3.1"
    autonomy: AutonomyMode = "confirm"
```

> **Python note — pydantic over a dataclass.** A `@dataclass` would happily
> accept `LeanConfig(autonomy="yolo")`; pydantic's `model_validate` rejects
> it. Since `config.json` is a file a human might hand-edit, that validation
> on *load* isn't optional — it's the whole reason to reach for pydantic
> here instead of the stdlib.
>
> `Literal[...]` is a closed set of allowed string values, checked both by
> pydantic and (as below) by Typer. Only `confirm`/`auto` get enforced until
> stage 4, but declaring all four now means the schema doesn't change when
> stage 4 lands.
>
> `schema_version` costs one field today and saves a migration headache once
> the schema inevitably grows in later stages.

### Custom exceptions

```python
class LeanError(Exception): ...
class AlreadyInitializedError(LeanError): ...
class NotInitializedError(LeanError): ...
class ConfigError(LeanError): ...
```

A small hierarchy, not one generic `ValueError` everywhere: `cli.py` can
catch `AlreadyInitializedError` specifically to print a clean message and
exit 1, while something in a later stage that just wants to know "is this
project unusable for any lean-specific reason" can catch `LeanError` broadly.

### Override merging — a pydantic gotcha worth knowing

```python
def merge_overrides(base: LeanConfig, overrides: dict) -> LeanConfig:
    changes = {k: v for k, v in overrides.items() if v is not None}
    merged = {**base.model_dump(), **changes}
    return LeanConfig.model_validate(merged)  # re-validates everything
```

The obvious-looking alternative is `base.model_copy(update=changes)` —
pydantic's normal "tweak a few fields" idiom. **Don't use it here**:
`model_copy(update=...)` skips validation entirely, so a bad value passed in
from anywhere other than Typer's own choice-checked options would silently
produce an invalid `LeanConfig`. Rebuilding via `model_validate` costs a
little more but keeps "a `LeanConfig` instance is always valid" true
unconditionally — worth it for a handful of fields.

`overrides` values default to `None` when a CLI flag wasn't passed, which is
why the dict comprehension filters those out first — `None` here means
"don't touch this field," not "set it to None."

### `init_project` — scaffolding `.lean/`

```python
def init_project(root=None, overrides=None, force=False) -> LeanConfig:
    if paths.is_initialized(root) and not force:
        raise AlreadyInitializedError(...)

    config = merge_overrides(default_config(), overrides or {})
    save_config(config, root)

    for path in (paths.summary_path(root), paths.last_turn_path(root)):
        if not path.exists():
            path.write_text("", encoding="utf-8")

    return config
```

Two design choices to flag, both easy to simplify if you don't want them:

- **`summary.md`/`last_turn.md` are only created if missing**, even under
  `--force`. So `--force` re-init fixes a typo'd model name without wiping
  real conversation history once stage 8 starts writing to those files. A
  simpler version could just always truncate them — fine if you'd rather
  keep `init` fully idempotent-by-overwrite.
- **`force` is a plain bool**, not baked into the config. It's an action you
  take once, not a setting that should persist.

### Wiring into the CLI

```python
@app.command()
def init(
    provider: str | None = typer.Option(None),
    model: str | None = typer.Option(None),
    autonomy: AutonomyMode | None = typer.Option(None),
    force: bool = typer.Option(False, "--force"),
) -> None:
    overrides = {"provider": provider, "model": model, "autonomy": autonomy}
    try:
        cfg = init_project(overrides=overrides, force=force)
    except AlreadyInitializedError as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(code=1)
    typer.echo(cfg.to_json())
```

Because `autonomy`'s type hint is `AutonomyMode | None` (a `Literal` under
the hood), `lean init --autonomy yolo` fails at the Typer/Click layer with
no code of yours involved — worth a test on its own, since it's easy to
assume validation logic is only in `config.py`.

### Tests — three layers, not one

1. **`test_config.py`** — call `init_project(root=tmp_path, ...)` directly.
   No CLI, no `chdir`. This is what "run init against `tmp_path`" means in
   the original spec.

   ```python
   def test_init_project_writes_files(tmp_path):
       cfg = init_project(root=tmp_path, overrides={"model": "qwen2.5-coder"})
       assert cfg.model == "qwen2.5-coder"
       assert paths.config_path(tmp_path).is_file()
   ```

2. **`test_init.py`** — same behavior through `CliRunner`, catching wiring
   bugs (wrong flag name, wrong type hint) the unit test can't see:

   ```python
   def test_init_merges_overrides(runner, tmp_path, monkeypatch):
       monkeypatch.chdir(tmp_path)
       runner.invoke(app, ["init", "--model", "qwen2.5-coder"])
       written = json.loads(paths.config_path().read_text())
       assert written["model"] == "qwen2.5-coder"
       assert written["provider"] == "ollama"  # untouched default
   ```

   Note the assertion is against **parsed JSON**, not raw text — the test
   shouldn't care about indentation or key order, only values.

3. **A validation-boundary test**, easy to forget:

   ```python
   def test_init_rejects_invalid_autonomy(runner, tmp_path, monkeypatch):
       monkeypatch.chdir(tmp_path)
       result = runner.invoke(app, ["init", "--autonomy", "yolo"])
       assert result.exit_code != 0
       assert not paths.config_path().exists()
   ```

---

## Checklist against the original stage descriptions

- [x] pyproject + typer stub; `lean status` prints version (config path
      added once `paths.py` exists)
- [x] `CliRunner` smoke test
- [x] `config.py` — pydantic schema with defaults
- [x] `lean init` scaffolds `.lean/` (config.json, empty summary.md /
      last_turn.md)
- [x] test: init against `tmp_path`, correct defaults
- [x] test: override merging (some fields changed, others left default)
- [x] no graph, no LLM touched anywhere in this stage

## Deliberately not here yet

- Autonomy modes aren't *enforced* — `confirm`/`silent`/`dry-run` just sit
  in the schema until stage 4's `write_md` guard reads them.
- `provider`/`model` aren't used to instantiate anything — stage 7 is the
  first thing that calls Ollama.
- No `--path` override for where `.lean/` lives — everything assumes
  `Path.cwd()`, which is why tests lean on `monkeypatch.chdir` or the
  `root=` parameter rather than a CLI flag.
