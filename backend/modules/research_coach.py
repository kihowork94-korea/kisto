import tracing
from config import get_adapter
from instructions import with_custom_instructions
from literature import format_for_prompt, search_papers
from memory.store import add_references, current_thread, get_session, save_session, thread_brief

SYSTEM_PROMPT = """\
너는 문헌 조사와 연구 가설 수립을 돕는 전문 모듈이다.
1) 사용자 주제에 대해 관련 선행 연구 흐름을 간단히 요약하고
2) 후보 가설/연구방향을 2~3개 제시한 뒤, 서로 비교(참신성/실현가능성)해서 순위를 매기고
3) 바로 정답처럼 결론짓지 말고, 사용자가 왜 이 방향에 관심 있는지 되묻는
   질문을 마지막에 하나 포함해라.
[검색된 논문]이 주어지면 선행 연구 요약은 반드시 그 논문들의 초록에 근거하고, 근거로 쓴
문장 끝에 [번호]로 인용해라. 목록에 없는 논문·저자·수치를 지어내지 마라. 초록만으로
확인되지 않는 내용은 "초록만으로는 확인되지 않는다"고 말해라.
[지금까지의 연구 맥락]이 있으면 앞서 나눈 이야기를 이어서 말해라 (처음 만난 것처럼 굴지 마라).
출력은 한국어, 신입 연구자가 이해하기 쉬운 톤으로. 참고문헌 목록은 따로 붙으니 쓰지 마라.
"""


def run(session_id: str, message: str, search_query: str | None = None) -> tuple[str, list[tuple[int, dict]]]:
    """(답변, 이번에 근거로 쓴 논문들의 (인용 번호, 논문) 목록)."""
    thread = current_thread(session_id)
    papers, numbered = [], []
    if search_query:
        with tracing.step("문헌 검색", detail=search_query) as rec:
            papers, source = search_papers(search_query)
            rec["models"].append(f"{source or '검색 실패'} {len(papers)}편")
        numbers = add_references(session_id, papers)
        numbered = list(zip(numbers, papers))

    paper_block = ""
    if numbered:
        paper_block = "\n\n[검색된 논문]\n" + "\n".join(
            format_for_prompt([p], start=n) for n, p in numbered
        )

    with tracing.step("연구 코치"):
        adapter = get_adapter("research_coach")
        result = adapter.generate(
            system_prompt=with_custom_instructions(SYSTEM_PROMPT, "research_coach"),
            messages=[
                {
                    "role": "user",
                    "content": f"[지금까지의 연구 맥락]\n{thread_brief(thread)}\n\n"
                    f"[사용자 메시지]\n{message}{paper_block}",
                }
            ],
        )

    session = get_session(session_id)
    if session["threads"]:
        session["threads"][-1]["hypotheses"].append(result)
        save_session(session_id, session)

    return result, numbered
