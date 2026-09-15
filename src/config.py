from typing import Literal
from pydantic import BaseModel
from . import paths


AutonomyMode = Literal["confirm", "auto"]

class LeanConfig(BaseModel):
    schema_version: int = 1
    provider: str = "ollama"
    model: str = "qwen-3.5:27b"
    autonomy: AutonomyMode = "confirm"

def default_config() -> LeanConfig:
    # return a fresh model 
    return LeanConfig()

def merge_overrides(base: LeanConfig, overrides: dict) -> LeanConfig:
    # filter out None values
    changes = {}
    for key in overrides:
        if overrides[key] is not None:
            changes[key] = overrides[key]

    # merge values that have been changed
    merged = base.model_dump()
    for key in changes:
        merged[key] = changes[key]

    # return merged lean config
    return LeanConfig(**merged)

def init_project(root: None, overrides: None) -> LeanConfig:
    # MAY NEED TO GUARD MY SUMMARY.MD and LAST_TURN.MD LATER FROM BEING RE WRITTEN
    config = merge_overrides(default_config(), overrides or {})
    save_config(config, root)

    return config

def save_config(config: LeanConfig, root=None) -> None:
    # get the config path from root
    path = paths.config_path(root)

    # ensures creation of parent dir
    path.parent.mkdir(parents=True, exists_ok=True)

    # serialize pydantic model to json (indent 2 for pretty-printed)
    path.write_text(config.model_dump_json(indent=2), encoding="utf-8")







    










