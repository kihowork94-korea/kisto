import json
from datetime import datetime
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
            "references": [],  # 문헌 검색으로 찾은 실제 논문. 인용 번호 = 목록 순서 + 1
            "turns": [],  # 최근 대화 (모듈에 연구 맥락으로 넘긴다)
            "interpretation": "",  # 초안 전에 받은 연구자의 해석 (연구노트에 남긴다)
            "created_at": datetime.now().isoformat(timespec="minutes"),
        }
    )
    save_session(session_id, session)


def current_thread(session_id: str) -> dict | None:
    session = get_session(session_id)
    return session["threads"][-1] if session["threads"] else None


def update_current_thread(session_id: str, **fields) -> None:
    session = get_session(session_id)
    if session["threads"]:
        session["threads"][-1].update(fields)
        save_session(session_id, session)


MAX_TURNS = 12
TURN_CHARS = 1200


def add_turn(
    session_id: str,
    user_message: str,
    reply: str,
    module: str | None = None,
    seconds: float | None = None,
    trace: list[dict] | None = None,
) -> None:
    """최근 대화(맥락용)와, 대시보드용 전체 활동 기록(누가·언제·몇 초)을 남긴다."""
    session = get_session(session_id)
    if not session["threads"]:
        return
    thread = session["threads"][-1]
    turns = thread.setdefault("turns", [])
    turns.append({"user": user_message[:TURN_CHARS], "kisto": reply[:TURN_CHARS]})
    del turns[:-MAX_TURNS]
    # 대시보드용 활동 기록은 잘라내지 않는다 (본문 없이 요약만 남겨 가볍게 유지).
    thread.setdefault("activity", []).append(
        {
            "at": datetime.now().isoformat(timespec="seconds"),
            "module": module,
            "message": user_message[:80],
            "seconds": seconds,
            "steps": [
                {"agent": s["agent"], "models": s["models"], "seconds": s["seconds"]}
                for s in (trace or [])
            ],
        }
    )
    save_session(session_id, session)


def add_review(session_id: str, review: dict) -> None:
    session = get_session(session_id)
    if not session["threads"]:
        return
    review["at"] = datetime.now().isoformat(timespec="minutes")
    session["threads"][-1].setdefault("reviews", []).append(review)
    save_session(session_id, session)


def add_references(session_id: str, papers: list[dict]) -> list[int]:
    """논문을 스레드 참고문헌에 추가하고 각 논문의 인용 번호(1부터)를 돌려준다."""
    session = get_session(session_id)
    if not session["threads"]:
        return []
    refs = session["threads"][-1].setdefault("references", [])
    numbers = []
    for p in papers:
        key = (p.get("doi") or p["title"]).lower()
        existing = next(
            (i for i, r in enumerate(refs) if (r.get("doi") or r["title"]).lower() == key), None
        )
        if existing is None:
            refs.append(p)
            existing = len(refs) - 1
        numbers.append(existing + 1)
    save_session(session_id, session)
    return numbers


def thread_brief(thread: dict | None, max_chars: int = 3500) -> str:
    """모듈에 넘길 '지금까지의 연구 맥락'. 파편화된 챗과 달리 키스토는 이걸 매번 들고 간다."""
    history_keys = ("hypotheses", "analysis", "interpretation", "files", "turns")
    if not thread or not any(thread.get(k) for k in history_keys):
        # 주제 이름만 있을 때 맥락을 넘기면 모델이 "지난번에 말씀드린 것처럼"이라며 없는 대화를 지어낸다.
        return "(없음 — 이 주제로는 처음 이야기하는 중이다)"
    parts = [f"연구 주제: {thread.get('topic')}"]
    if thread.get("hypotheses"):
        parts.append(f"[최근 가설 논의 요약]\n{thread['hypotheses'][-1][:1200]}")
    for a in thread.get("analysis", [])[-2:]:
        parts.append(f"[분석 결과]\n{a['output'][:600]}\n[해석]\n{a['interpretation'][:500]}")
    if thread.get("interpretation"):
        parts.append(f"[연구자 본인의 해석]\n{thread['interpretation'][:600]}")
    if thread.get("files"):
        parts.append("[첨부된 데이터 파일] " + ", ".join(f["name"] for f in thread["files"]))
    if thread.get("turns"):
        recent = "\n".join(
            f"- 연구자: {t['user'][:200]}\n  키스토: {t['kisto'][:200]}" for t in thread["turns"][-4:]
        )
        parts.append(f"[최근 대화]\n{recent}")
    return "\n\n".join(parts)[:max_chars]


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
