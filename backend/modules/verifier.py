import tracing
from config import get_verifier_adapter
from lab import role_instructions
from literature import format_for_prompt

VERIFY_PROMPT = """\
너는 다른 모델이 만든 연구 관련 결과를 비판적으로 재검토하는 검증
에이전트다. 아래 결과에서:
1) 근거 없이 과잉해석된 부분
2) 통계적으로 의심스러운 주장
3) 재현 가능성이 낮아 보이는 부분
4) [근거 논문]이 주어졌다면, [번호] 인용이 해당 논문 초록과 맞지 않거나 초록에 없는
   내용을 말하는 부분
을 지적해라. 지적은 항목당 한두 문장으로 짧게. 문제가 없으면 정확히 "특이사항 없음"이라고만 답해라.
"""


def verify(
    content: str, produced_by: str, sources: list[tuple[int, dict]] | None = None
) -> str:
    """결과를 만든 provider와 가급적 다른 provider로 교차검증한다.

    sources: (인용 번호, 논문) 목록 — 본문의 [번호]와 같은 번호로 보여줘야 대조할 수 있다.
    """
    body = content
    if sources:
        listing = "\n".join(format_for_prompt([p], start=n) for n, p in sources)
        body += f"\n\n[근거 논문]\n{listing}"
    with tracing.step("교차검증"):
        adapter = get_verifier_adapter(exclude=produced_by)
        # 검토위원에게는 KISTO.md(말투 지침)는 주지 않고, 연구실에서 이 역할에 준 지침만 붙인다.
        extra = role_instructions("verifier")
        prompt = VERIFY_PROMPT + (f"\n[연구 책임자가 이 역할에 준 지침]\n{extra}" if extra else "")
        return adapter.generate(prompt, [{"role": "user", "content": body}])
