import os

from anthropic import Anthropic

from .base import ModelAdapter


class ClaudeAdapter(ModelAdapter):
    name = "claude"

    def __init__(self, model: str = "claude-sonnet-4-5"):
        self.client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.model = model

    def generate(self, system_prompt: str, messages: list[dict]) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=system_prompt,
            messages=messages,
        )
        return response.content[0].text
