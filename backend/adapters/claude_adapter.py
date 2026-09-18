import os

from anthropic import Anthropic

from .base import ModelAdapter


class ClaudeAdapter(ModelAdapter):
    name = "claude"

    def __init__(self, model: str | None = None):
        self.client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.model = model or os.environ.get("ANTHROPIC_MODEL") or "claude-opus-5"

    def generate(self, system_prompt: str, messages: list[dict]) -> str:
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            system=system_prompt,
            messages=messages,
            # 안전 분류기가 요청을 거절하면 서버가 알아서 다른 모델로 재시도한다.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("Claude가 이 요청에 대한 응답을 거절했습니다.")
        # 최신 모델은 thinking이 기본으로 켜져 있어 첫 블록이 텍스트가 아닐 수 있다.
        return "".join(block.text for block in response.content if block.type == "text")
