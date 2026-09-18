from pathlib import Path

# 프로젝트 루트의 KISTO.md — CLAUDE.md와 같은 패턴이다. 사용자가 이 파일만
# 편집하면 코드를 안 건드리고도 키스토의 성격/규칙을 바꿀 수 있다.
INSTRUCTIONS_PATH = Path(__file__).resolve().parent.parent / "KISTO.md"


def load_custom_instructions() -> str:
    """매 호출마다 새로 읽는다 — 서버 재시작 없이 KISTO.md 수정이 바로 반영된다."""
    if not INSTRUCTIONS_PATH.exists():
        return ""
    return INSTRUCTIONS_PATH.read_text(encoding="utf-8").strip()


def with_custom_instructions(base_system_prompt: str, role: str | None = None) -> str:
    """KISTO.md(연구실 전체 지침) + 연구실 설정에서 이 역할에 준 지침을 붙인다."""
    from lab import role_instructions  # lab → memory → ... 순환 import를 피하려고 여기서 불러온다

    prompt = base_system_prompt
    custom = load_custom_instructions()
    if custom:
        prompt += f"\n\n[사용자 지정 지침 — KISTO.md]\n{custom}"
    extra = role_instructions(role) if role else ""
    if extra:
        prompt += f"\n\n[연구 책임자가 이 역할에 준 지침]\n{extra}"
    return prompt
