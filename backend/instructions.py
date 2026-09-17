from pathlib import Path

# 프로젝트 루트의 KISTO.md — CLAUDE.md와 같은 패턴이다. 사용자가 이 파일만
# 편집하면 코드를 안 건드리고도 키스토의 성격/규칙을 바꿀 수 있다.
INSTRUCTIONS_PATH = Path(__file__).resolve().parent.parent / "KISTO.md"


def load_custom_instructions() -> str:
    """매 호출마다 새로 읽는다 — 서버 재시작 없이 KISTO.md 수정이 바로 반영된다."""
    if not INSTRUCTIONS_PATH.exists():
        return ""
    return INSTRUCTIONS_PATH.read_text(encoding="utf-8").strip()


def with_custom_instructions(base_system_prompt: str) -> str:
    custom = load_custom_instructions()
    if not custom:
        return base_system_prompt
    return f"{base_system_prompt}\n\n[사용자 지정 지침 — KISTO.md]\n{custom}"
