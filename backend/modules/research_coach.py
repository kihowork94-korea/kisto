from config import get_adapter
from instructions import with_custom_instructions
from memory.store import get_session, save_session

SYSTEM_PROMPT = """\
너는 문헌 조사와 연구 가설 수립을 돕는 전문 모듈이다.
1) 사용자 주제에 대해 관련 선행 연구 흐름을 간단히 요약하고
2) 후보 가설/연구방향을 2~3개 제시한 뒤, 서로 비교(참신성/실현가능성)해서 순위를 매기고
3) 바로 정답처럼 결론짓지 말고, 사용자가 왜 이 방향에 관심 있는지 되묻는
   질문을 마지막에 하나 포함해라.
출력은 한국어, 신입 연구자가 이해하기 쉬운 톤으로.
"""


def run(session_id: str, message: str) -> str:
    adapter = get_adapter("research_coach")
    result = adapter.generate(
        system_prompt=with_custom_instructions(SYSTEM_PROMPT),
        messages=[{"role": "user", "content": message}],
    )

    session = get_session(session_id)
    if session["threads"]:
        session["threads"][-1]["hypotheses"].append(result)
        save_session(session_id, session)

    return result
