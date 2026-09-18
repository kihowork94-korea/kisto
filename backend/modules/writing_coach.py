import re
from datetime import datetime

import tracing
from config import get_adapter
from instructions import with_custom_instructions
from literature import format_for_prompt, format_reference_list
from memory.store import current_thread, get_session, save_session

# 이 질문은 페르소나 레이어를 거치지 않고 그대로 사용자에게 간다 (main.py).
# 페르소나에 넘기면 질문에 스스로 답해버리므로, 여기서 키스토 말투까지 완성한다.
ASK_OPINION_PROMPT = """\
너는 '키스토(KISTO)'라는 AI 연구 동료이고, KIST 신입 연구자의 선배처럼 말한다.
사용자가 논문 초안을 부탁했다. 아래는 이 연구 스레드에서 논의된 가설과 분석 결과다.
바로 초안을 써주지 말고:
1) 초안은 연구자의 해석이 들어가야 제대로 된 글이 된다는 점을 한 문장으로 말하고
2) 분석 결과의 핵심을 1~2줄로만 짚은 뒤
3) "이 결과를 본인은 어떻게 해석하는지", "서론에서 무엇을 강조하고 싶은지"를 묻는
   질문 2개 이내로 끝내라.
네가 직접 결과를 해석하거나 질문에 답하지 마라. 전체 5~7문장 이내로 짧게.
"""

DRAFT_PROMPT = """\
너는 논문/보고서 작성을 돕는 전문 모듈이다. 아래 맥락(가설, 분석결과,
사용자의 해석)을 바탕으로 서론 문단 초안을 작성해라. 사용자의 해석을
반드시 반영하고, 어디까지나 초안임을 마지막 줄에 명시해라.
맥락에 없는 수치, 판정 기준, 문헌 인용을 지어내지 마라.
[참고문헌 후보]가 있으면, 그 초록이 실제로 뒷받침하는 문장에만 [번호]로 인용해라.
후보로 뒷받침되지 않는데 인용이 필요한 자리는 [참고문헌 필요]로 표시해라.
참고문헌 목록은 따로 붙으니 본문만 써라.
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
    with tracing.step("집필 코치", detail="연구자 해석 묻기"):
        adapter = get_adapter("writing_coach")
        return adapter.generate(
            with_custom_instructions(ASK_OPINION_PROMPT, "writing_coach"),
            [{"role": "user", "content": context}],
        )


def _draft_with_opinion(session_id: str, user_opinion: str) -> str:
    thread = current_thread(session_id)
    refs = (thread or {}).get("references", [])
    context = _thread_context(thread) + f"\n\n[사용자 해석]\n{user_opinion}"
    if refs:
        context += f"\n\n[참고문헌 후보]\n{format_for_prompt(refs)}"
    with tracing.step("집필 코치", detail="초안 작성"):
        adapter = get_adapter("writing_coach")
        draft = adapter.generate(
            with_custom_instructions(DRAFT_PROMPT, "writing_coach"),
            [{"role": "user", "content": context}],
        )

    # 참고문헌 목록은 모델이 아니라 코드가 붙인다 — 본문에서 실제로 인용한 번호만,
    # 검색으로 찾은 실제 논문 정보 그대로.
    cited = sorted({int(n) for n in re.findall(r"\[(\d+)\]", draft) if 1 <= int(n) <= len(refs)})
    if cited:
        draft += "\n\n**참고문헌**\n\n" + "\n\n".join(
            format_reference_list([refs[n - 1]], start=n) for n in cited
        )

    session = get_session(session_id)
    if session["threads"]:
        current = session["threads"][-1]
        current["draft"] = draft
        current["draft_at"] = datetime.now().isoformat(timespec="seconds")
        if current.get("_awaiting_opinion") or not current.get("interpretation"):
            current["interpretation"] = user_opinion
        current["_awaiting_opinion"] = False
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
