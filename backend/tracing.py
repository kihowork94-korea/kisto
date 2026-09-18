"""요청 하나 동안 어떤 에이전트가 어떤 모델로 몇 초 걸렸는지 기록한다.

사용자에게는 "키스토 한 명"만 보이지만(설계 결정 4), 발표·심사 때는 뒤에서 여러
에이전트와 서로 다른 회사 모델이 협업했다는 걸 보여줘야 한다. 위젯의 발표 모드가
이 기록(`trace`)을 그대로 보여준다.
"""

import time
from contextlib import contextmanager
from contextvars import ContextVar

_steps: ContextVar[list | None] = ContextVar("kisto_trace_steps", default=None)
_current: ContextVar[dict | None] = ContextVar("kisto_trace_current", default=None)
_session: ContextVar[str | None] = ContextVar("kisto_trace_session", default=None)

# 세션별로 "지금 어느 에이전트가 일하는 중인지" — 위젯이 기다리는 동안 보여준다 (GET /progress).
LIVE: dict[str, dict] = {}

# 발표 모드에서 보여줄 이름. 내부 provider 키 → 사람이 읽는 이름.
VENDOR_LABEL = {
    "claude": "Claude · Anthropic",
    "claude_harness": "Claude · Anthropic",
    "openai": "GPT · OpenAI",
    "gemini": "Gemini · Google",
}


def start(session_id: str | None = None) -> list:
    steps: list = []
    _steps.set(steps)
    _current.set(None)
    _session.set(session_id)
    return steps


def finish(session_id: str) -> None:
    LIVE.pop(session_id, None)


@contextmanager
def step(agent: str, detail: str | None = None):
    """에이전트 한 단계를 기록한다. 안에서 호출된 모델은 TracingAdapter가 채운다."""
    steps = _steps.get()
    record = {"agent": agent, "models": [], "detail": detail, "seconds": 0.0}
    parent = _current.get()
    token = _current.set(record)
    started = time.perf_counter()
    session_id = _session.get()
    if session_id and parent is None:
        LIVE[session_id] = {"agent": agent, "since": time.time()}
    try:
        yield record
    finally:
        record["seconds"] = round(time.perf_counter() - started, 1)
        _current.reset(token)
        if steps is not None and parent is None:
            steps.append(record)
        elif parent is not None:
            # 중첩된 단계의 모델 호출은 바깥 단계에 합친다.
            for m in record["models"]:
                if m not in parent["models"]:
                    parent["models"].append(m)


def note_model(provider: str) -> None:
    record = _current.get()
    if record is not None:
        label = VENDOR_LABEL.get(provider, provider)
        if label not in record["models"]:
            record["models"].append(label)


class TracingAdapter:
    """어댑터를 감싸서, 호출될 때 현재 단계에 '어느 회사 모델이 답했는지'를 남긴다."""

    def __init__(self, inner):
        self._inner = inner
        self.name = inner.name

    def generate(self, system_prompt: str, messages: list[dict]) -> str:
        note_model(self._inner.name)
        return self._inner.generate(system_prompt, messages)
