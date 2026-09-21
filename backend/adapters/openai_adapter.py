import os

from openai import OpenAI

from .base import ModelAdapter


class OpenAIAdapter(ModelAdapter):
    """'코덱스' 역할 — 코딩/분석에 강한 OpenAI 모델을 담당한다."""

    name = "openai"

    def __init__(self, model: str | None = None):
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.model = model or os.environ.get("OPENAI_MODEL") or "gpt-5.3-codex"

    def generate(self, system_prompt: str, messages: list[dict]) -> str:
        # codex 계열은 Chat Completions가 아니라 Responses API로만 호출된다.
        response = self.client.responses.create(
            model=self.model,
            instructions=system_prompt,
            input=messages,
        )
        return response.output_text
