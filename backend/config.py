import os
import shutil

from dotenv import load_dotenv

from adapters.claude_adapter import ClaudeAdapter
from adapters.claude_harness_adapter import ClaudeHarnessAdapter
from adapters.openai_adapter import OpenAIAdapter
from adapters.gemini_adapter import GeminiAdapter
from lab import preferred_provider
from tracing import TracingAdapter

load_dotenv()

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


def get_adapter(module_name: str, exclude: str | None = None):
    # 연구실 설정에서 사용자가 이 역할에 모델을 지정했고 그 키가 있으면 그걸 먼저 쓴다.
    chosen = preferred_provider(module_name)
    if chosen in _adapters and chosen != exclude:
        return TracingAdapter(_adapters[chosen])
    preferred = MODULE_MODEL_MAP.get(module_name, "claude")
    for candidate in _FALLBACK_CHAIN.get(preferred, [preferred]):
        if candidate in _adapters and candidate != exclude:
            return TracingAdapter(_adapters[candidate])
    for name, adapter in _adapters.items():
        if name != exclude:
            return TracingAdapter(adapter)
    raise RuntimeError("사용 가능한 어댑터가 없습니다 (exclude 조건 때문에 전부 제외됨).")


def get_verifier_adapter(exclude: str):
    """결과를 만든 provider와 '다른 회사' 모델을 고른다 (설계 결정 2).

    사용자가 검토위원 모델을 지정했어도, 결과를 만든 쪽과 같은 회사면 따르지 않는다.
    다른 회사 모델이 하나도 없을 때만 같은 회사 모델로 대신한다.
    """
    producer_vendor = VENDOR.get(exclude)
    chosen = preferred_provider("verifier")
    candidates = ([chosen] if chosen else []) + VERIFIER_PREFERENCE
    for name in candidates:
        if name in _adapters and VENDOR.get(name) != producer_vendor:
            return TracingAdapter(_adapters[name])
    for name in VERIFIER_PREFERENCE:
        if name in _adapters and name != exclude:
            return TracingAdapter(_adapters[name])
    return TracingAdapter(next(iter(_adapters.values())))


def available_providers() -> list[str]:
    return list(_adapters.keys())
