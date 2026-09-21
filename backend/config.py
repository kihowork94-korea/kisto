import logging
import os
import shutil
import time

from dotenv import load_dotenv

from adapters.claude_adapter import ClaudeAdapter
from adapters.claude_harness_adapter import ClaudeHarnessAdapter
from adapters.openai_adapter import OpenAIAdapter
from adapters.gemini_adapter import GeminiAdapter
from lab import preferred_provider
from tracing import TracingAdapter, note_answer

load_dotenv()
log = logging.getLogger("kisto.config")

_adapters: dict[str, object] = {}


def _build_adapters() -> None:
    if os.environ.get("ANTHROPIC_API_KEY"):
        _adapters["claude"] = ClaudeAdapter()
    # API 키가 없어도 Claude Code에 로그인되어 있으면 이걸로 대체 가능.
    if shutil.which("claude"):
        _adapters["claude_harness"] = ClaudeHarnessAdapter()
    if os.environ.get("OPENAI_API_KEY"):
        _adapters["openai"] = OpenAIAdapter()
    if os.environ.get("GOOGLE_API_KEY"):
        _adapters["gemini"] = GeminiAdapter()

    if not _adapters:
        raise RuntimeError(
            "사용 가능한 provider가 없습니다. .env에 ANTHROPIC_API_KEY를 넣거나, "
            "Claude Code CLI(`claude`)에 로그인한 상태에서 실행하세요."
        )


_build_adapters()

# 모듈별 선호 provider. 해당 provider가 없으면 아래 순서로 자동 대체된다.
MODULE_MODEL_MAP = {
    "router": "claude",
    "persona": "claude",
    "research_coach": "claude",
    "analysis_partner": "openai",
    "writing_coach": "claude",
}

# preferred가 없을 때 시도할 대체 후보 (같은 "계열"부터).
_FALLBACK_CHAIN = {
    "claude": ["claude", "claude_harness", "openai", "gemini"],
    "openai": ["openai", "claude", "claude_harness", "gemini"],
    "gemini": ["gemini", "claude", "claude_harness", "openai"],
}

# 검증 에이전트는 "결과를 만든 provider와 다른 것"을 이 순서로 우선 선택한다.
# claude/claude_harness는 같은 모델 계열이라 서로를 대체품으로 치지 않는다.
VERIFIER_PREFERENCE = ["gemini", "openai", "claude", "claude_harness"]


VENDOR = {"claude": "anthropic", "claude_harness": "anthropic", "openai": "openai", "gemini": "google"}


# 호출 실패 분류 (예외 이름 + 메시지에서 찾는다)
# 일시적: 잠깐 기다렸다 같은 모델로 다시 — Gemini의 "high demand" 503처럼 몇 초 뒤면 풀리는 것
_TRANSIENT = ("503", "UNAVAILABLE", "overloaded", "Overloaded", "high demand", "529")
RETRY_WAITS = (4, 10)  # 초. 두 번 다시 해 보고 안 되면 다음 후보로
# 영구적: 이번 실행 동안 그 provider를 건너뛴다 (.env를 고치고 백엔드를 재시작하면 풀린다)
_PERMANENT = ("NotFoundError", "model_not_found", "AuthenticationError", "insufficient_quota",
              "credit_balance", "API_KEY_INVALID", "PermissionDenied")
# provider → 건너뛰는 이유 (/health에 보인다)
UNAVAILABLE: dict[str, str] = {}


class FallbackAdapter:
    """후보 모델을 순서대로 불러 보고, 실패하면(크레딧 소진·한도 초과·모델 없음·네트워크) 다음으로 넘어간다.

    '키가 있다'와 '실제로 쓸 수 있다'는 다르다 — 크레딧이 0원인 키도 등록은 된다. 폴백이 없으면
    그런 키 하나 때문에 대화 전체가 500으로 끊긴다. 실제로 답한 provider는 tracing에 남겨서
    '누가 만들고 누가 검토했는지' 기록이 사실과 어긋나지 않게 한다 (교차검증 표시의 근거).
    """

    def __init__(self, role: str, names: list[str]):
        if not names:
            raise RuntimeError("사용 가능한 어댑터가 없습니다 (exclude 조건 때문에 전부 제외됨).")
        self.role = role
        self._names = names
        self.name = names[0]  # 호출 전에는 1순위, 호출 뒤에는 실제로 답한 provider

    def generate(self, system_prompt: str, messages: list[dict]) -> str:
        failures = []
        for name in self._names:
            if name in UNAVAILABLE:
                failures.append(f"{name}: 건너뜀 ({UNAVAILABLE[name]})")
                continue
            for attempt, wait in enumerate((*RETRY_WAITS, None)):
                try:
                    text = TracingAdapter(_adapters[name]).generate(system_prompt, messages)
                except Exception as exc:  # SDK마다 예외 종류가 달라서 전부 받아 판단한다
                    reason = f"{type(exc).__name__}: {str(exc)[:200]}"
                    if any(k in reason for k in _PERMANENT):
                        # 모델 없음·키 틀림·크레딧 없음은 다시 해도 안 된다 — 재시작 전까지 건너뛴다
                        UNAVAILABLE[name] = reason
                    elif wait is not None and any(k in reason for k in _TRANSIENT):
                        log.warning("%s: %s 일시적 오류, %s초 뒤 다시 (%d회째): %s",
                                    self.role, name, wait, attempt + 1, reason)
                        time.sleep(wait)
                        continue
                    failures.append(f"{name}: {reason}")
                    log.warning("%s 호출 실패, 다음 후보로: %s", self.role, failures[-1])
                    break
                self.name = name
                note_answer(self.role, name)
                return text
        raise RuntimeError(" / ".join(failures))


def _dedupe(names) -> list[str]:
    seen: list[str] = []
    for n in names:
        if n and n in _adapters and n not in seen:
            seen.append(n)
    return seen


def get_adapter(module_name: str, exclude: str | None = None):
    # 연구실 설정에서 사용자가 이 역할에 모델을 지정했고 그 키가 있으면 그걸 먼저 쓴다.
    preferred = MODULE_MODEL_MAP.get(module_name, "claude")
    order = [preferred_provider(module_name)] + _FALLBACK_CHAIN.get(preferred, [preferred]) + list(_adapters)
    return FallbackAdapter(module_name, [n for n in _dedupe(order) if n != exclude])


def get_verifier_adapter(exclude: str):
    """결과를 만든 provider와 '다른 회사' 모델을 고른다 (설계 결정 2).

    사용자가 검토위원 모델을 지정했어도, 결과를 만든 쪽과 같은 회사면 따르지 않는다.
    다른 회사 모델이 하나도 없거나 전부 실패할 때만 같은 회사 모델로, 그것도 없으면 결과를 만든
    모델이 스스로 검토한다 (그 경우 검토 기록에 '같은 회사'로 남는다 — 검토를 건너뛰지는 않는다).
    """
    producer_vendor = VENDOR.get(exclude)
    order = _dedupe([preferred_provider("verifier")] + VERIFIER_PREFERENCE + list(_adapters))
    other = [n for n in order if VENDOR.get(n) != producer_vendor]
    same = [n for n in order if VENDOR.get(n) == producer_vendor and n != exclude]
    itself = [n for n in order if n == exclude]  # 최후의 수단: 만든 모델이 스스로 검토 (기록엔 '같은 회사')
    return FallbackAdapter("verifier", other + same + itself)


def available_providers() -> list[str]:
    return list(_adapters.keys())
