from __future__ import annotations

import json
import re
import os
from pydantic import BaseModel
from browser_use import Agent, ChatGoogle


def extract_json_object(text: str) -> dict | None:
    # 텍스트 안에 JSON이 섞여 있을 때 추출(대충이라도)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def build_task(task: str, schema: str, schema_hint: str | None) -> str:
    hint = schema_hint.strip() if schema_hint else ""
    return f"""
Return ONLY valid JSON. Do not include any other text.

Output must be EXACTLY one JSON object in this envelope:
{{
  "schema": "{schema}",
  "data": <any valid JSON>,
  "raw": null
}}

Rules:
- No prose.
- No markdown.
- No code fences.
- If you cannot comply, still output the JSON object with data=null and raw as a string.

Schema hint:
{hint}

User task:
{task}
""".strip()


async def run(payload: dict, ctx: dict) -> dict:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set")

    task = payload.get("task")
    if not task or not isinstance(task, str):
        raise RuntimeError("payload.task (string) is required")

    schema = payload.get("schema", "generic.v1")
    schema_hint = payload.get("schema_hint", "")

    use_vision = bool(
        payload.get("use_vision", False)
    )  # 기본은 False (headless + 텍스트 추출 위주)
    model = payload.get("model", "gemini-flash-lite-latest")

    agent = Agent(
        task=build_task(task=task, schema=schema, schema_hint=schema_hint),
        llm=ChatGoogle(model=model, api_key=api_key),
        use_vision=use_vision,
    )

    history = await agent.run()
    result = history.final_result()

    # 1) dict면 그대로
    if isinstance(result, dict):
        return result

    # 2) pydantic 모델이면 dump
    if isinstance(result, BaseModel):
        return result.model_dump()

    # 3) 문자열이면 JSON 파싱 시도
    if isinstance(result, str):
        # 1) 먼저 JSON이 텍스트에 섞여 있나 확인
        extracted = extract_json_object(result)
        if extracted and isinstance(extracted, dict):
            return extracted

        # 2) 순수 JSON 파싱 시도
        try:
            parsed = json.loads(result)
            if isinstance(parsed, dict):
                return parsed
            return {"schema": schema, "data": parsed, "raw": None}
        except Exception:
            pass

        # 3) 재시도: raw 텍스트를 schema envelope JSON으로 "변환만" 요청
        reform_task = f"""
Convert the following text into ONLY valid JSON in this exact envelope:
{{
  "schema": "{schema}",
  "data": <json>,
  "raw": null
}}

Schema hint:
{schema_hint}

Text to convert:
{result}
""".strip()

        reform_agent = Agent(
            task=reform_task,
            llm=ChatGoogle(model=model, api_key=api_key),
            use_vision=False,
        )
        reform_history = await reform_agent.run()
        reform_result = reform_history.final_result()

        if isinstance(reform_result, dict):
            return reform_result
        if isinstance(reform_result, BaseModel):
            return reform_result.model_dump()
        if isinstance(reform_result, str):
            extracted2 = extract_json_object(reform_result)
            if extracted2 and isinstance(extracted2, dict):
                return extracted2
            try:
                parsed2 = json.loads(reform_result)
                if isinstance(parsed2, dict):
                    return parsed2
                return {"schema": schema, "data": parsed2, "raw": None}
            except Exception:
                return {"schema": schema, "data": None, "raw": reform_result}

        return {"schema": schema, "data": None, "raw": str(reform_result)}

    # 4) 그 외 타입
    return {"schema": schema, "data": None, "raw": str(result)}
