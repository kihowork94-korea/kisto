import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
STORE_PATH = DATA_DIR / "memory_store.json"


def _load() -> dict:
    if not STORE_PATH.exists():
        return {}
    return json.loads(STORE_PATH.read_text(encoding="utf-8"))


def _save(data: dict) -> None:
    STORE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _default_session() -> dict:
    return {
        "profile": {"concepts_explained": [], "background_note": ""},
        "threads": [],
    }


def get_session(session_id: str) -> dict:
    data = _load()
    return data.get(session_id, _default_session())


def save_session(session_id: str, session: dict) -> None:
    data = _load()
    data[session_id] = session
    _save(data)


def start_new_thread(session_id: str, topic: str) -> None:
    session = get_session(session_id)
    session["threads"].append(
        {
            "topic": topic,
            "hypotheses": [],
            "analysis": [],
            "verifications": [],
            "draft": "",
            "_awaiting_opinion": False,
        }
    )
    save_session(session_id, session)


def current_thread(session_id: str) -> dict | None:
    session = get_session(session_id)
    return session["threads"][-1] if session["threads"] else None


def record_verification(session_id: str, note: str) -> None:
    session = get_session(session_id)
    if not session["threads"]:
        return
    session["threads"][-1].setdefault("verifications", []).append(note)
    save_session(session_id, session)


# 연구 로드맵의 5단계. AutoResearch 5단계 파이프라인과 대응된다.
STAGES = [
    {"key": "grounding", "label": "주제 잡기", "hint": "관심 분야를 키스토와 이야기해 연구 주제를 연다"},
    {"key": "hypothesis", "label": "가설 세우기", "hint": "후보 가설을 비교하고 방향을 고른다"},
    {"key": "analysis", "label": "분석 돌리기", "hint": "데이터로 가설을 검증한다"},
    {"key": "verification", "label": "교차검증", "hint": "다른 모델이 결과를 반박해본다"},
    {"key": "writing", "label": "초안 쓰기", "hint": "결과를 글로 정리한다"},
]


def _cleared_stages(thread: dict) -> list[bool]:
    """각 단계가 실제로 달성됐는지 — 저장된 데이터로만 판단한다 (장식용 아님)."""
    return [
        True,  # 스레드가 존재한다는 것 자체가 '주제 잡기' 완료
        bool(thread.get("hypotheses")),
        bool(thread.get("analysis")),
        bool(thread.get("verifications")),
        bool(thread.get("draft")),
    ]


def thread_progress(thread: dict) -> dict:
    cleared = _cleared_stages(thread)
    cleared_count = sum(cleared)
    current_index = next((i for i, done in enumerate(cleared) if not done), len(STAGES) - 1)
    return {
        "cleared": cleared,
        "cleared_count": cleared_count,
        "total": len(STAGES),
        "percent": round(cleared_count / len(STAGES) * 100),
        "current_index": current_index,
        "current_label": STAGES[current_index]["label"],
        "current_hint": STAGES[current_index]["hint"],
    }


def list_threads(session_id: str) -> list[dict]:
    session = get_session(session_id)
    return [
        {
            "topic": thread.get("topic", "(제목 없음)"),
            "progress": thread_progress(thread),
            "hypothesis_count": len(thread.get("hypotheses", [])),
            "analysis_count": len(thread.get("analysis", [])),
            "verification_count": len(thread.get("verifications", [])),
            "has_draft": bool(thread.get("draft")),
        }
        for thread in session["threads"]
    ]
