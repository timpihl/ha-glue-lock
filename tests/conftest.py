"""Load the modules that have no Home Assistant imports, without the package."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

COMPONENT = Path(__file__).parent.parent / "custom_components" / "glue_lock"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"glue_{name}", COMPONENT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_load("api")
_load("state")
