from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse

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
    def __init__(self, model: str | None = None, profile: str = "default") -> None:
        self.profile = profile.strip().lower() or "default"
        self.api_key, self.base_url, env_model = self._resolve_config(self.profile)
        self.model = model or env_model

    @staticmethod
    def _resolve_config(profile: str) -> tuple[str, str, str]:
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
        model = os.getenv("OPENAI_MODEL", "gpt-5.4").strip() or "gpt-5.4"
        api_key = os.getenv("OPENAI_API_KEY", "").strip()

        if profile == "graph":
            api_key = os.getenv("GRAPH_OPENAI_API_KEY", api_key).strip()
            base_url = os.getenv("GRAPH_OPENAI_BASE_URL", base_url).strip()
            model = os.getenv("GRAPH_OPENAI_MODEL", model).strip() or model

        return api_key, base_url, model

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _client(self) -> OpenAI:
        default_headers = self._default_headers()
        if default_headers:
            return OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                default_headers=default_headers,
            )
        return OpenAI(api_key=self.api_key, base_url=self.base_url)

    def _default_headers(self) -> dict[str, str]:
        host = (urlparse(self.base_url).hostname or "").lower()
        if host == "jj20cm.us.ci":
            origin = f"{urlparse(self.base_url).scheme}://{host}"
            return {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/135.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Origin": origin,
                "Referer": f"{origin}/",
            }
        return {}

    def generate_markdown(self, system_prompt: str, user_prompt: str) -> str:
        if not self.enabled:
            raise RuntimeError("未配置 OPENAI_API_KEY，无法使用 openai provider")

        client = self._client()
        try:
            response = self._create_with_retry(
                client,
                model=self.model,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except Exception as exc:
            raise RuntimeError(self._format_error(exc)) from exc
        content = response.choices[0].message.content or ""
        return content.strip()

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        if not self.enabled:
            raise RuntimeError("未配置 OPENAI_API_KEY，无法使用 openai provider")

        client = self._client()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            try:
                response = self._create_with_retry(
                    client,
                    model=self.model,
                    temperature=0.1,
                    response_format={"type": "json_object"},
                    messages=messages,
                )
            except Exception:
                response = self._create_with_retry(
                    client,
                    model=self.model,
                    temperature=0.1,
                    messages=messages,
                )
        except Exception as exc:
            raise RuntimeError(self._format_error(exc)) from exc

        content = response.choices[0].message.content or ""
        json_text = self._extract_json_text(content)
        try:
            return json.loads(json_text)
        except json.JSONDecodeError:
            repaired = self._sanitize_json_text(json_text)
            return json.loads(repaired)

    @staticmethod
    def _extract_json_text(content: str) -> str:
        text = content.strip()
        fenced = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL)
        if fenced:
            text = fenced[0].strip()

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end >= start:
            return text[start : end + 1]
        return text

    @staticmethod
    def _sanitize_json_text(text: str) -> str:
        normalized = text.replace("\ufeff", "")
        normalized = re.sub(r",(\s*[}\]])", r"\1", normalized)

        escaped: list[str] = []
        in_string = False
        escape = False
        for char in normalized:
            if in_string:
                if escape:
                    escaped.append(char)
                    escape = False
                    continue
                if char == "\\":
                    escaped.append(char)
                    escape = True
                    continue
                if char == '"':
                    escaped.append(char)
                    in_string = False
                    continue
                if char == "\n":
                    escaped.append("\\n")
                    continue
                if char == "\r":
                    escaped.append("\\r")
                    continue
                if char == "\t":
                    escaped.append("\\t")
                    continue
                escaped.append(char)
                continue

            escaped.append(char)
            if char == '"':
                in_string = True

        return "".join(escaped)

    def _format_error(self, exc: Exception) -> str:
        message = str(exc).strip()
        return (
            "LLM 调用失败。"
            f" profile={self.profile};"
            f" base_url={self.base_url};"
            f" model={self.model};"
            f" error={type(exc).__name__}: {message}"
        )

    def _create_with_retry(self, client: OpenAI, **kwargs):
        last_error: Exception | None = None
        for attempt in range(1, 5):
            try:
                return client.chat.completions.create(**kwargs)
            except Exception as exc:
                last_error = exc
                if attempt >= 4 or not self._is_retryable(exc):
                    raise
                time.sleep(min(20, attempt * 5))
        raise last_error or RuntimeError("未知 LLM 调用失败")

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        message = str(exc).lower()
        retry_tokens = (
            "504",
            "503",
            "502",
            "gateway time-out",
            "gateway timeout",
            "temporarily unavailable",
            "timeout",
            "timed out",
            "connection",
            "try again",
        )
        return any(token in message for token in retry_tokens)
