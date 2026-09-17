from config import get_adapter
from instructions import with_custom_instructions
from memory.store import current_thread, get_session, save_session

ASK_OPINION_PROMPT = """\
너는 논문/보고서 작성을 돕는 전문 모듈이다. 아래는 지금까지 이 연구
스레드에서 논의된 가설과 분석 결과다. 대필하지 말고, 먼저 사용자에게
"이 결과를 보고 본인은 어떻게 해석하는지" 짧게 묻는 질문을 한국어로 만들어라.
"""

DRAFT_PROMPT = """\
너는 논문/보고서 작성을 돕는 전문 모듈이다. 아래 맥락(가설, 분석결과,
사용자의 해석)을 바탕으로 서론 문단 초안을 작성해라. 사용자의 해석을
반드시 반영하고, 어디까지나 초안임을 마지막 줄에 명시해라.
"""


def _thread_context(thread: dict | None) -> str:
    if not thread:
        return "(아직 논의된 내용 없음)"
    hyps = "\n".join(thread.get("hypotheses", []))
    analysis = "\n".join(a["interpretation"] for a in thread.get("analysis", []))
    return f"[가설]\n{hyps}\n\n[분석 해석]\n{analysis}"


def _ask_for_opinion(session_id: str) -> str:
    thread = current_thread(session_id)
    context = _thread_context(thread)
    adapter = get_adapter("writing_coach")
    return adapter.generate(
        with_custom_instructions(ASK_OPINION_PROMPT), [{"role": "user", "content": context}]
    )


def _draft_with_opinion(session_id: str, user_opinion: str) -> str:
    thread = current_thread(session_id)
    context = _thread_context(thread) + f"\n\n[사용자 해석]\n{user_opinion}"
    adapter = get_adapter("writing_coach")
    draft = adapter.generate(
        with_custom_instructions(DRAFT_PROMPT), [{"role": "user", "content": context}]
    )

    session = get_session(session_id)
    if session["threads"]:
        session["threads"][-1]["draft"] = draft
        session["threads"][-1]["_awaiting_opinion"] = False
        save_session(session_id, session)
    return draft


def run(session_id: str, message: str) -> str:
    thread = current_thread(session_id)

    if thread and not thread.get("draft") and not thread.get("_awaiting_opinion"):
        session = get_session(session_id)
        session["threads"][-1]["_awaiting_opinion"] = True
        save_session(session_id, session)
        return _ask_for_opinion(session_id)

    # 두 번째 호출부터는 사용자의 답을 '해석'으로 보고 초안을 작성한다.
    return _draft_with_opinion(session_id, message)
