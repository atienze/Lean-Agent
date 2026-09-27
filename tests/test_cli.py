import json
import typer

from typer.testing import CliRunner

from src.cli import app
from src.paths import config_path


def test_cli_all_overrides(tmp_path, monkeypatch):
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        app,
        [
            "init",
            "--provider",
            "openai",
            "--model",
            "gpt-4",
            "--autonomy",
            "auto",
        ]
    )

    assert result.exit_code == 0

    saved_config = json.loads(
        config_path(tmp_path).read_text(encoding="utf-8")
    )

    assert saved_config["provider"] == "openai"
    assert saved_config["model"] == "gpt-4"
    assert saved_config["autonomy"] == "auto"

def test_cli_one_override(tmp_path, monkeypatch):
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        app,
        [
            "init", 
            "--provider",
            "anthropic",
        ]
    )

    assert result.exit_code == 0

    saved_config = json.loads(
        config_path(tmp_path).read_text(encoding="utf-8")
    )
    # check value was changed
    assert saved_config["provider"] == "anthropic"

    # check other values are unchanged
    assert saved_config["model"] == "qwen-3.5:27b"
    assert saved_config["autonomy"] == "confirm"