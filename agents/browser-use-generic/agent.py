from __future__ import annotations

import os
from browser_use import Agent, ChatGoogle


async def run(payload: dict, ctx: dict) -> dict:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set")

    task = payload.get("task")
    if not isinstance(task, str) or not task.strip():
        raise RuntimeError("payload.task (string) is required")

    model = payload.get("model", "gemini-flash-lite-latest")
    use_vision = bool(payload.get("use_vision", True))

    agent = Agent(
        task=task,
        llm=ChatGoogle(model=model, api_key=api_key),
        use_vision=use_vision,
    )

    history = await agent.run()
    result = history.final_result()

    return {"raw": "" if result is None else str(result)}
