import contextvars
import csv
import io
import re
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import tracing
from config import UNAVAILABLE, available_providers, get_adapter, get_verifier_adapter
from instructions import with_custom_instructions
from lab import ROLES, dashboard, lab_overview, load_settings, save_settings
from literature import format_reference_list
from memory.store import (
    DATA_DIR,
    STAGES,
    add_review,
    add_turn,
    current_thread,
    get_session,
    list_threads,
    record_verification,
    save_session,
    start_new_thread,
    thread_brief,
    thread_progress,
)
from tracing import VENDOR_LABEL
from modules import analysis_partner, research_coach, verifier, writing_coach
from orchestrator.persona import CHITCHAT_SYSTEM_PROMPT, wrap_in_persona
from orchestrator.router import route
from privacy import mask
from research_note import build_note

app = FastAPI(title="KISTO")

# ── 접근 제한 ──
# 분석 단계가 LLM이 만든 코드를 이 PC에서 실행하므로, 아무 웹사이트나 127.0.0.1:8420을 부를 수
# 있으면 안 된다. 위젯·연구실은 백엔드가 만든 토큰 파일을 읽어 헤더로 보내고, 브라우저 요청
# (Origin이 붙는 요청)은 토큰이 있거나 로컬 테스트 페이지일 때만 받는다. Origin이 없는 요청은
# 브라우저가 아닌 로컬 도구(scripts/e2e.py, curl)다.
TOKEN_PATH = DATA_DIR / ".kisto_token"
if not TOKEN_PATH.exists():
    TOKEN_PATH.write_text(secrets.token_urlsafe(32), encoding="utf-8")
API_TOKEN = TOKEN_PATH.read_text(encoding="utf-8").strip()
TEST_PAGE_ORIGINS = {"http://localhost:8500", "http://127.0.0.1:8500"}
ALLOWED_HOSTS = {"127.0.0.1:8420", "localhost:8420"}


@app.middleware("http")
async def guard(request: Request, call_next):
    # DNS 리바인딩(악성 도메인을 127.0.0.1로 돌려 같은 출처처럼 읽기) 방지
    if request.headers.get("host") not in ALLOWED_HOSTS:
        return JSONResponse({"detail": "허용되지 않은 호스트"}, status_code=403)
    origin = request.headers.get("origin")
    token_ok = secrets.compare_digest(request.headers.get("x-kisto-token", ""), API_TOKEN)
    if request.method != "OPTIONS" and origin and origin not in TEST_PAGE_ORIGINS and not token_ok:
        return JSONResponse({"detail": "키스토 위젯에서만 접근할 수 있어요"}, status_code=403)
    return await call_next(request)


# 위젯·연구실은 file:// 페이지라 Origin이 "null"로 온다 (토큰으로 따로 확인한다).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["null", *TEST_PAGE_ORIGINS],
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type", "X-Kisto-Token"],
)

UPLOAD_DIR = DATA_DIR / "uploads"
# 검토 기록에 남길 단계 이름 (연구실 화면에서 어느 연구원의 결과를 검토했는지 보여준다)
MODULE_LABEL = {
    "research_coach": "문헌 연구원의 가설 정리",
    "analysis_partner": "분석 연구원의 분석 결과",
    "writing_coach": "집필 연구원의 초안",
    "chitchat": "키스토의 대화",
}
MAX_UPLOAD_BYTES = 2 * 1024 * 1024


class ChatRequest(BaseModel):
    session_id: str
    message: str


class UploadRequest(BaseModel):
    session_id: str
    filename: str
    content: str  # CSV/TSV/TXT 텍스트


@app.get("/health")
def health():
    # unavailable: 키는 있지만 호출이 영구 실패해서(모델 없음·크레딧 없음 등) 건너뛰는 provider와 이유
    return {"providers": available_providers(), "unavailable": UNAVAILABLE}


@app.get("/threads/{session_id}")
def threads(session_id: str):
    """연구 주제별 로드맵 진행 상황. 대화 폴더 목록이 아니라 파이프라인 상태다."""
    return {"stages": STAGES, "threads": list_threads(session_id)}


@app.get("/threads/{session_id}/{index}/note")
def research_note(session_id: str, index: int):
    """연구 주제 하나를 연구노트(Markdown)로 정리한다."""
    session = get_session(session_id)
    if not 0 <= index < len(session["threads"]):
        raise HTTPException(404, "해당 연구 주제가 없습니다.")
    return build_note(session["threads"][index], STAGES)


@app.get("/threads/{session_id}/{index}/detail")
def thread_detail(session_id: str, index: int):
    """연구실 화면용 — 프로젝트 하나의 전체 기록 (문헌, 분석, 검토, 해석, 초안, 첨부)."""
    session = get_session(session_id)
    if not 0 <= index < len(session["threads"]):
        raise HTTPException(404, "해당 연구 주제가 없습니다.")
    t = session["threads"][index]
    return {
        "topic": t.get("topic"),
        "created_at": t.get("created_at"),
        "progress": thread_progress(t),
        "hypotheses": t.get("hypotheses", [])[-1:],
        "references": t.get("references", []),
        "analysis": t.get("analysis", []),
        "reviews": t.get("reviews", []),
        "interpretation": t.get("interpretation", ""),
        "draft": t.get("draft", ""),
        "files": [{k: f[k] for k in ("name", "rows", "columns")} for f in t.get("files", [])],
    }


class RoleSetting(BaseModel):
    provider: str | None = None
    instructions: str = ""


@app.get("/lab/roles")
def lab_roles():
    """연구원 명단 + 역할별 설정 + 지금 쓸 수 있는 모델 (역할 부여 화면)."""
    settings = load_settings()
    providers = available_providers()
    return {
        "roles": [{**r, **settings.get(r["key"], {})} for r in ROLES],
        "providers": [{"key": p, "label": VENDOR_LABEL.get(p, p)} for p in providers],
    }


@app.put("/lab/roles")
def update_lab_roles(settings: dict[str, RoleSetting]):
    save_settings({k: v.model_dump() for k, v in settings.items()})
    return lab_roles()


@app.get("/lab/session/{session_id}")
def lab_session(session_id: str):
    """연구실 전체 현황 — 프로젝트별 진행도, 연구실 레벨·별, 연구원별 업무 기록."""
    return lab_overview(get_session(session_id)["threads"])


@app.get("/lab/session/{session_id}/dashboard")
def lab_dashboard(session_id: str):
    """연구실 대시보드 — 전체 진행 지표, 단계 퍼널, 연구원별 업무·시간, 회사별 모델 사용, 타임라인."""
    return dashboard(get_session(session_id)["threads"], live=tracing.LIVE.get(session_id))


@app.post("/upload")
def upload(req: UploadRequest):
    """분석할 데이터 파일을 현재 연구 주제에 첨부한다. 개인정보로 보이는 값은 가려서 저장한다."""
    if len(req.content.encode("utf-8")) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "2MB 이하의 CSV/TSV/TXT 파일만 첨부할 수 있어요.")
    name = re.sub(r"[^\w.\-가-힣]", "_", Path(req.filename).name) or "data.csv"
    content, masked = mask(req.content)

    dialect = csv.excel_tab if name.lower().endswith((".tsv", ".txt")) and "\t" in content else csv.excel
    rows = list(csv.reader(io.StringIO(content), dialect))
    columns = rows[0] if rows else []

    folder = UPLOAD_DIR / re.sub(r"[^\w\-]", "_", req.session_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(content, encoding="utf-8")

    if current_thread(req.session_id) is None:
        start_new_thread(req.session_id, f"{name} 데이터 분석")
    session = get_session(req.session_id)
    files = session["threads"][-1].setdefault("files", [])
    files[:] = [f for f in files if f["name"] != name]
    info = {"name": name, "path": str(path), "rows": max(len(rows) - 1, 0), "columns": columns[:30]}
    files.append(info)
    save_session(req.session_id, session)
    return {**{k: info[k] for k in ("name", "rows", "columns")}, "masked": masked}


@app.get("/progress/{session_id}")
def progress(session_id: str):
    """답을 기다리는 동안 위젯이 묻는다: 지금 어느 연구원이 일하는 중인가."""
    live = tracing.LIVE.get(session_id)
    if not live:
        return {"agent": None}
    return {"agent": live["agent"], "seconds": round(time.time() - live["since"], 1)}


@app.post("/chat")
def chat(req: ChatRequest):
    try:
        return _chat(req)
    except RuntimeError as exc:
        # 모델 호출 실패(사용 한도 초과, 타임아웃 등)는 500 대신 이유를 담아 돌려준다.
        # 시연 중에 걸려도 위젯이 무엇이 문제인지 바로 보여줄 수 있게.
        raise HTTPException(503, f"모델 호출 실패: {exc}") from exc
    finally:
        tracing.finish(req.session_id)


def _chat(req: ChatRequest):
    started = time.perf_counter()
    trace = tracing.start(req.session_id)
    # 외부 모델로 나가기 전에 개인정보로 보이는 부분부터 가린다.
    message, masked = mask(req.message)

    with tracing.step("라우터"):
        routing = route(req.session_id, message)
    module = routing["module"]
    sources: list[tuple[int, dict]] = []

    if module == "chitchat":
        with tracing.step("키스토 (대화)"):
            adapter = get_adapter("persona")
            # 정체성을 안 주면 하네스(Claude Code)가 자기 기능을 소개해버린다.
            raw = adapter.generate(
                with_custom_instructions(CHITCHAT_SYSTEM_PROMPT, "manager"),
                [
                    {
                        "role": "user",
                        "content": f"[지금까지의 연구 맥락]\n{thread_brief(current_thread(req.session_id))}"
                        f"\n\n[사용자 메시지]\n{message}",
                    }
                ],
            )
        produced_by = adapter.name
    elif module == "analysis_partner":
        raw = analysis_partner.run(req.session_id, message)
        produced_by = tracing.answered("analysis_partner") or get_adapter("analysis_partner").name
    elif module == "writing_coach":
        raw = writing_coach.run(req.session_id, message)
        produced_by = tracing.answered("writing_coach") or get_adapter("writing_coach").name
    else:  # research_coach 및 그 외 fallback
        raw, sources = research_coach.run(req.session_id, message, routing.get("search_query"))
        produced_by = tracing.answered("research_coach") or get_adapter("research_coach").name

    def respond(reply: str, review: str | None, verified_by: str | None) -> dict:
        seconds = round(time.perf_counter() - started, 1)
        add_turn(req.session_id, message, reply, module=module, seconds=seconds, trace=trace)
        return {
            "reply": reply,
            # 교차검증 결과는 답변에 섞지 않고 '검토 노트'로 따로 보여준다.
            "review": review,
            "module": module,
            "produced_by": produced_by,
            "verified_by": verified_by,
            "trace": trace,
            "masked": masked,
            "seconds": seconds,
        }

    thread = current_thread(req.session_id)
    if module == "writing_coach" and thread and thread.get("_awaiting_opinion"):
        # 초안 전에 연구자의 해석을 묻는 질문이다. 검증할 내용이 없고, 페르소나에 넘기면
        # 질문에 스스로 답해버리므로 그대로 돌려준다 (질문 프롬프트가 이미 키스토 말투).
        return respond(raw, None, None)

    # 교차검증과 페르소나 다듬기는 서로의 결과가 필요 없으므로 동시에 돌린다 (답변당 수십 초 단축).
    # 초안은 사용자의 결과물이 될 글이라 페르소나로 다시 쓰지 않는다.
    rewrite = not (module == "writing_coach" and thread and thread.get("draft") == raw)

    def polish() -> str:
        with tracing.step("페르소나"):
            return wrap_in_persona(get_adapter("persona"), raw)

    with ThreadPoolExecutor(max_workers=2) as pool:
        # 각 스레드에 현재 요청의 추적 기록(contextvar)을 그대로 넘긴다.
        checking = pool.submit(
            contextvars.copy_context().run, verifier.verify, raw, produced_by, sources
        )
        polishing = pool.submit(contextvars.copy_context().run, polish) if rewrite else None
        check = checking.result()
        reply = polishing.result() if polishing else raw

    # 분석 결과가 나온 뒤에만 교차검증을 로드맵 달성으로 인정한다
    # (잡담까지 '검증 완료'로 치면 로드맵이 의미 없어진다).
    if module == "analysis_partner":
        record_verification(req.session_id, check)
    review = None if "특이사항 없음" in check else check.strip()
    verified_by = tracing.answered("verifier") or get_verifier_adapter(exclude=produced_by).name
    # 연구실의 검토 데스크에 쌓이는 기록 (로드맵 4단계 판정은 분석 검증만 따로 센다).
    add_review(req.session_id, {
        "stage": MODULE_LABEL.get(module, module),
        "producer": VENDOR_LABEL.get(produced_by, produced_by),
        "reviewer": VENDOR_LABEL.get(verified_by, verified_by),
        "text": review or "특이사항 없음",
        "issues": review is not None,
    })

    if sources:
        # 참고문헌은 모델이 아니라 코드가 붙인다 — 실제 검색된 논문 정보 그대로.
        reply += "\n\n---\n**참고 논문** (실제 검색 결과)\n\n" + "\n\n".join(
            format_reference_list([p], start=n) for n, p in sources
        )
    return respond(reply, review, verified_by)
