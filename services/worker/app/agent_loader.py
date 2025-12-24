from __future__ import annotations
import importlib.util
import os
from types import ModuleType

AGENTS_DIR = os.getenv("AGENTS_DIR", "/agents")

def load_agent_module(agent_id: str) -> ModuleType:
    agent_path = os.path.join(AGENTS_DIR, agent_id, "agent.py")
    if not os.path.exists(agent_path):
        raise FileNotFoundError(f"agent.py not found: {agent_path}")

    spec = importlib.util.spec_from_file_location(f"agent_{agent_id}", agent_path)
    if not spec or not spec.loader:
        raise RuntimeError(f"Failed to load agent module: {agent_id}")

    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    return mod