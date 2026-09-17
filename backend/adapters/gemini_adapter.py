import os

from google import genai

from .base import ModelAdapter


class GeminiAdapter(ModelAdapter):
    """긴 문헌을 한 번에 읽거나, 다른 provider 결과를 교차검증할 때 쓴다."""

    name = "gemini"

    def __init__(self, model: str = "gemini-2.5-pro"):
        self.client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        self.model = model

    def generate(self, system_prompt: str, messages: list[dict]) -> str:
        history = "\n\n".join(f"[{m['role']}] {m['content']}" for m in messages)
        response = self.client.models.generate_content(
            model=self.model,
            contents=f"{system_prompt}\n\n{history}",
        )
        return response.text
