from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import get_adapter, available_providers
from memory.store import STAGES, list_threads, record_verification
from orchestrator.router import route
from orchestrator.persona import wrap_in_persona
from modules import research_coach, analysis_partner, writing_coach, verifier

app = FastAPI(title="KISTO")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


class ChatRequest(BaseModel):
    session_id: str
    message: str


@app.get("/health")
def health():
    return {"providers": available_providers()}


@app.get("/threads/{session_id}")
def threads(session_id: str):
    """연구 주제별 로드맵 진행 상황. 대화 폴더 목록이 아니라 파이프라인 상태다."""
    return {"stages": STAGES, "threads": list_threads(session_id)}


@app.post("/chat")
def chat(req: ChatRequest):
    routing = route(req.session_id, req.message)
    module = routing["module"]

    if module == "chitchat":
        adapter = get_adapter("persona")
        raw = adapter.generate(
            "가볍게 친근한 선배 톤으로 대답해라.",
            [{"role": "user", "content": req.message}],
        )
        produced_by = adapter.name
    elif module == "analysis_partner":
        raw = analysis_partner.run(req.session_id, req.message)
        produced_by = get_adapter("analysis_partner").name
    elif module == "writing_coach":
        raw = writing_coach.run(req.session_id, req.message)
        produced_by = get_adapter("writing_coach").name
    else:  # research_coach 및 그 외 fallback
        raw = research_coach.run(req.session_id, req.message)
        produced_by = get_adapter("research_coach").name

    # 분석 결과가 나온 뒤에만 교차검증을 로드맵 달성으로 인정한다
    # (잡담까지 '검증 완료'로 치면 로드맵이 의미 없어진다).
    check = verifier.verify(raw, produced_by=produced_by)
    if module == "analysis_partner":
        record_verification(req.session_id, check)
    if "특이사항 없음" not in check:
        raw = f"{raw}\n\n(검증 메모: {check})"

    persona_adapter = get_adapter("persona")
    reply = wrap_in_persona(persona_adapter, raw)

    return {"reply": reply, "module": module, "produced_by": produced_by}
