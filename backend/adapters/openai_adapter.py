import os

from openai import OpenAI

from .base import ModelAdapter


class OpenAIAdapter(ModelAdapter):
    """'코덱스' 역할 — 코딩/분석에 강한 OpenAI 모델을 담당한다."""

    name = "openai"

    def __init__(self, model: str = "gpt-5.1-codex"):
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.model = model

    def generate(self, system_prompt: str, messages: list[dict]) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system_prompt}, *messages],
        )
        return response.choices[0].message.content
