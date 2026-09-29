import json
import typer

from typer.testing import CliRunner

from src.config import init_project
from src.paths import config_path

def test_init_project_creates_default_config(tmp_path):
    config = init_project(root=tmp_path)

    assert config.provider == "ollama"
    assert config.model == "qwen-3.5:27b"
    assert config.autonomy == "confirm"
    assert config.file_read_lines == 50

    config_file = config_path(tmp_path)

    assert config_file.is_file()
    assert (tmp_path / ".lean").is_dir()

    saved = json.loads(config_file.read_text(encoding="utf-8"))

    assert saved == {
        "provider": "ollama",
        "model": "qwen-3.5:27b",
        "autonomy": "confirm",
        "file_read_lines": 50,
    }