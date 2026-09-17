import json

from config import get_adapter
from memory.store import current_thread, start_new_thread

ROUTER_SYSTEM_PROMPT = """\
너는 KISTO 시스템의 오케스트레이터다. 사용자 메시지를 분석해서 아래 중
하나로 분류하고 JSON만 출력해라. 다른 텍스트는 절대 출력하지 마라.

intent 종류:
- "chitchat": 잡담, 인사
- "topic_explore": 연구 주제/가설 탐색 (문헌, 아이디어 논의)
- "data_analysis": 데이터/코드 분석 요청
- "writing": 논문/보고서 작성 지원 요청
- "continue": 직전 스레드를 계속 이어가는 요청 (예: "이걸로 분석해줘", "논문에 녹여줘")

출력 형식: {"intent": "...", "new_topic": "새 주제라면 짧게 요약, 아니면 null"}
"""


def classify(message: str) -> dict:
    adapter = get_adapter("router")
    raw = adapter.generate(
        system_prompt=ROUTER_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": message}],
    )
    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        return json.loads(raw[start:end])
    except (ValueError, json.JSONDecodeError):
        return {"intent": "topic_explore", "new_topic": None}


def route(session_id: str, message: str) -> dict:
    """분류 결과 + 세션 스레드 상태를 합쳐서 다음에 호출할 모듈을 결정한다."""
    classification = classify(message)
    intent = classification.get("intent", "topic_explore")

    if intent == "topic_explore" and classification.get("new_topic"):
        start_new_thread(session_id, classification["new_topic"])

    thread = current_thread(session_id)
    if intent == "continue" and thread is None:
        intent = "topic_explore"

    module_map = {
        "chitchat": "chitchat",
        "topic_explore": "research_coach",
        "continue": "auto",
        "data_analysis": "analysis_partner",
        "writing": "writing_coach",
    }
    target = module_map.get(intent, "research_coach")

    if target == "auto" and thread is not None:
        if thread.get("draft") or thread.get("_awaiting_opinion"):
            target = "writing_coach"
        elif thread.get("hypotheses") and not thread.get("analysis"):
            target = "analysis_partner"
        else:
            target = "research_coach"

    return {"module": target, "thread": current_thread(session_id)}
