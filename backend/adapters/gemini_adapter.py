import os

from google import genai
from google.genai import types

from .base import ModelAdapter


class GeminiAdapter(ModelAdapter):
    """긴 문헌을 한 번에 읽거나, 다른 provider 결과를 교차검증할 때 쓴다."""

    name = "gemini"

    def __init__(self, model: str | None = None):
        self.client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        self.model = model or os.environ.get("GEMINI_MODEL") or "gemini-3.8-flash"

    def generate(self, system_prompt: str, messages: list[dict]) -> str:
        contents = [
            types.Content(
                role="model" if m["role"] == "assistant" else "user",
                parts=[types.Part(text=m["content"])],
            )
            for m in messages
        ]
        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                # 도구 호출을 쓰지 않는다 — 켜 두면 SDK가 호출마다 AFC 경고를 찍는다
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        return response.text or ""
