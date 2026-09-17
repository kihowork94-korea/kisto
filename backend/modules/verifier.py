from config import get_verifier_adapter

VERIFY_PROMPT = """\
너는 다른 모델이 만든 연구 관련 결과를 비판적으로 재검토하는 검증
에이전트다. 아래 결과에서:
1) 근거 없이 과잉해석된 부분
2) 통계적으로 의심스러운 주장
3) 재현 가능성이 낮아 보이는 부분
을 지적해라. 문제가 없으면 정확히 "특이사항 없음"이라고만 답해라.
"""


def verify(content: str, produced_by: str) -> str:
    """결과를 만든 provider와 가급적 다른 provider로 교차검증한다."""
    adapter = get_verifier_adapter(exclude=produced_by)
    return adapter.generate(VERIFY_PROMPT, [{"role": "user", "content": content}])
