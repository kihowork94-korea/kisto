from abc import ABC, abstractmethod


class ModelAdapter(ABC):
    """모든 provider가 구현해야 하는 공통 인터페이스.

    상위 레이어(라우터/모듈)는 이 인터페이스만 알면 되고, 실제로 Claude인지
    OpenAI인지 Gemini인지는 신경 쓰지 않는다.
    """

    name: str

    @abstractmethod
    def generate(self, system_prompt: str, messages: list[dict]) -> str:
        """messages: [{"role": "user"|"assistant", "content": str}, ...]"""
        raise NotImplementedError
