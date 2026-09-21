import os

from google import genai
from google.genai import errors, types

from .base import ModelAdapter

# GEMINI_MODEL이 붐벼서(503) 안 받으면 차례로 넘어갈 같은 회사 모델 — 검토가 Claude로 떨어지면
# 같은 회사 검토가 되어 버리므로, 다른 회사 모델 안에서 먼저 버틴다. (2026-09-21 이 키로 호출 확인)
DEFAULT_FALLBACKS = "gemini-3.5-flash,gemini-flash-latest"


class GeminiAdapter(ModelAdapter):
    """긴 문헌을 한 번에 읽거나, 다른 provider 결과를 교차검증할 때 쓴다."""

    name = "gemini"

    def __init__(self, model: str | None = None):
        self.client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        self.model = model or os.environ.get("GEMINI_MODEL") or "gemini-3.8-flash"
        extra = os.environ.get("GEMINI_FALLBACK_MODELS", DEFAULT_FALLBACKS)
        self.models = [self.model] + [m.strip() for m in extra.split(",") if m.strip() and m.strip() != self.model]

    def generate(self, system_prompt: str, messages: list[dict]) -> str:
        contents = [
            types.Content(
                role="model" if m["role"] == "assistant" else "user",
                parts=[types.Part(text=m["content"])],
            )
            for m in messages
        ]
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            # 도구 호출을 쓰지 않는다 — 켜 두면 SDK가 호출마다 AFC 경고를 찍는다
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        for i, model in enumerate(self.models):
            try:
                response = self.client.models.generate_content(model=model, contents=contents, config=config)
                return response.text or ""
            except errors.ServerError:
                # 붐비는 모델이면 다음 모델로. 마지막 모델까지 막히면 그대로 올려 보내서
                # config.FallbackAdapter가 잠깐 기다렸다 다시 하거나 다른 회사로 넘긴다.
                if i == len(self.models) - 1:
                    raise
        raise RuntimeError("Gemini 모델 목록이 비어 있다")
