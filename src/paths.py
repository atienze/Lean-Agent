from pathlib import Path

LEAN_DIR_NAME = ".lean"

# lean pathdir
def lean_dir(root: Path | None = None) -> Path:
    if root is not None:
        base = root
    else:
        base = Path.cwd()
    return base / LEAN_DIR_NAME

# config pathdir
def config_path(root: Path | None = None) -> Path:
    return lean_dir(root) / "config.json"

# check if "lean init" has been ran
def is_initialized(root: Path | None = None) -> bool:
    return config_path(root).is_file()
