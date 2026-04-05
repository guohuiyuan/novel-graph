from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


def _load_env_once() -> None:
    project_env = Path(__file__).resolve().parents[3] / ".env"
    if project_env.exists():
        load_dotenv(project_env, override=False)
    else:
        load_dotenv(override=False)


_load_env_once()


class LLMClient:
    def __init__(self, model: str | None = None) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://jj20cm.us.ci/v1").strip()
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.4")

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def generate_markdown(self, system_prompt: str, user_prompt: str) -> str:
        if not self.enabled:
            raise RuntimeError("未配置 OPENAI_API_KEY，无法使用 openai provider")

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        response = client.chat.completions.create(
            model=self.model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content or ""
        return content.strip()
