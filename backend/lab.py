"""키스토 연구실 — 에이전트를 '연구실 구성원'으로 다루는 설정과 게임 요소.

사용자는 연구실의 책임연구원(PI)이고, 키스토는 연구실 매니저다. 뒤에서 일하는 에이전트는
각자 연구실 안에 자리(서재, 실험대, 노트북, 검토 데스크)가 있는 연구원이다.
사용자는 연구원마다 어느 회사 모델을 쓸지와 따로 지킬 지침을 정할 수 있다 (역할 부여).
"""

import json
import time

from memory.store import DATA_DIR, STAGES, thread_progress

SETTINGS_PATH = DATA_DIR / "lab_settings.json"

# key: 설정·어댑터에서 쓰는 이름 / modules: 이 역할이 맡는 내부 모듈
ROLES = [
    {
        "key": "manager",
        "name": "연구실 매니저 키스토",
        "place": "연구실",
        "emoji": "🧑‍🔬",
        "duty": "연구자와 직접 대화하고, 요청을 알맞은 연구원에게 나눠 준다",
        "modules": ["router", "persona"],
    },
    {
        "key": "research_coach",
        "name": "문헌 연구원",
        "place": "서재",
        "emoji": "📚",
        "duty": "실제 논문을 찾아 읽고, 선행 연구 흐름과 후보 가설을 정리한다",
        "modules": ["research_coach"],
    },
    {
        "key": "analysis_partner",
        "name": "분석 연구원",
        "place": "실험대",
        "emoji": "🧪",
        "duty": "데이터 분석 코드를 짜서 돌리고, 결과를 가설과 연결해 해석한다",
        "modules": ["analysis_partner"],
    },
    {
        "key": "writing_coach",
        "name": "집필 연구원",
        "place": "노트북",
        "emoji": "✍️",
        "duty": "연구자의 해석을 먼저 듣고 그걸 반영해 논문 초안을 쓴다 (대필 금지)",
        "modules": ["writing_coach"],
    },
    {
        "key": "verifier",
        "name": "외부 검토위원",
        "place": "검토 데스크",
        "emoji": "🔍",
        "duty": "결과를 만든 연구원과 다른 회사 출신으로, 모든 결과를 반박해 본다",
        "modules": ["verifier"],
    },
]
_ROLE_OF_MODULE = {m: r["key"] for r in ROLES for m in r["modules"]}

LEVEL_TITLES = ["새내기 연구실", "자리 잡는 연구실", "탄탄한 연구실", "우수 연구실", "명예의 전당"]
STARS_PER_LEVEL = 5


def load_settings() -> dict:
    if not SETTINGS_PATH.exists():
        return {}
    return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))


def save_settings(settings: dict) -> None:
    valid = {r["key"] for r in ROLES}
    cleaned = {
        key: {
            "provider": (value.get("provider") or None),
            "instructions": (value.get("instructions") or "").strip()[:2000],
        }
        for key, value in settings.items()
        if key in valid
    }
    SETTINGS_PATH.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")


def preferred_provider(module_name: str) -> str | None:
    """사용자가 이 모듈(의 역할)에 지정한 provider. 없으면 None (기본 배치를 따른다)."""
    role = _ROLE_OF_MODULE.get(module_name)
    return load_settings().get(role, {}).get("provider") if role else None


def role_instructions(role: str) -> str:
    return load_settings().get(role, {}).get("instructions", "")


# tracing 단계 이름 → 그 일을 한 연구원
_ROLE_OF_STEP = {
    "라우터": "manager",
    "페르소나": "manager",
    "키스토 (대화)": "manager",
    "문헌 검색": "research_coach",
    "연구 코치": "research_coach",
    "분석 코드 작성": "analysis_partner",
    "코드 실행": "analysis_partner",
    "결과 해석": "analysis_partner",
    "집필 코치": "writing_coach",
    "교차검증": "verifier",
}
# 발표용 모델 이름 → 회사 (대시보드의 회사별 모델 사용 비율)
_COMPANY = {"Anthropic": "Anthropic", "OpenAI": "OpenAI", "Google": "Google"}
_MODULE_TEXT = {
    "research_coach": "문헌 연구원이 선행 연구·가설 정리",
    "analysis_partner": "분석 연구원이 데이터 분석",
    "writing_coach": "집필 연구원이 초안 작업",
    "chitchat": "키스토와 대화",
}


def _company(model_label: str) -> str | None:
    return next((c for key, c in _COMPANY.items() if key in model_label), None)


# 검토 기록의 stage 문구("분석 연구원의 분석 결과" 등) → 결과를 만든 연구원
_PRODUCER_WORDS = (("문헌", "research_coach"), ("분석", "analysis_partner"), ("집필", "writing_coach"))
_PRODUCERS = [role for _, role in _PRODUCER_WORDS]
_DOING = {
    "research_coach": "선행 연구·가설 정리",
    "analysis_partner": "데이터 분석",
    "writing_coach": "초안 작업",
}


def _producer_of(stage: str | None) -> str | None:
    return next((role for word, role in _PRODUCER_WORDS if word in (stage or "")), None)


def org_chart(threads: list[dict], live: dict | None = None) -> dict:
    """연구실 조직도·업무 흐름 — 누가 누구에게 일을 받아 무엇을 넘겼고, 지금 누가 일하는지.

    선 위의 숫자와 카드의 내용은 전부 저장된 기록(activity·reviews·산출물)에서 센다.
    live는 tracing.LIVE의 한 항목 (지금 진행 중인 요청이 없으면 None).
    """
    nodes = {
        r["key"]: {"key": r["key"], "name": r["name"], "place": r["place"], "duty": r["duty"], "emoji": r["emoji"],
                   "requests": 0, "seconds": 0.0, "models": [], "last": None, "working": None}
        for r in ROLES
    }
    reviews = {role: {"count": 0, "issues": 0, "cross": 0} for role in _PRODUCERS}
    counts = {"turns": 0, "papers": 0, "hypotheses": 0, "analyses": 0, "analyses_ok": 0, "drafts": 0,
              "hypothesis_projects": 0, "analysis_projects": 0}

    def touch(role: str, at: str | None, text: str) -> None:
        last = nodes[role]["last"]
        if at and (last is None or at > last["at"]):
            nodes[role]["last"] = {"at": at, "text": text}

    for t in threads:
        topic = t.get("topic", "(제목 없음)")
        counts["papers"] += len(t.get("references", []))
        counts["hypotheses"] += len(t.get("hypotheses", []))
        counts["analyses"] += len(t.get("analysis", []))
        counts["analyses_ok"] += sum(1 for a in t.get("analysis", []) if a.get("ok", True))
        counts["drafts"] += 1 if t.get("draft") else 0
        # 다음 연구원에게 넘어간 산출물: 가설이 있는 프로젝트 → 분석, 분석이 있는 프로젝트 → 집필
        counts["hypothesis_projects"] += 1 if t.get("hypotheses") else 0
        counts["analysis_projects"] += 1 if t.get("analysis") else 0

        for act in t.get("activity", []):
            counts["turns"] += 1
            module = act.get("module")
            if module in nodes:
                nodes[module]["requests"] += 1
                touch(module, act.get("at"), f"{_DOING.get(module, '작업')} · {topic}")
            owner = nodes[module]["name"] if module in nodes else "키스토"
            message = act.get("message", "")
            touch("manager", act.get("at"),
                  f"{owner}에게 전달 · “{message[:40]}{'…' if len(message) > 40 else ''}”")
            for step in act.get("steps", []):
                role = _ROLE_OF_STEP.get(step["agent"])
                if not role:
                    continue
                nodes[role]["seconds"] += step.get("seconds") or 0
                for model in step.get("models", []):
                    if _company(model) and model not in nodes[role]["models"]:
                        nodes[role]["models"].append(model)

        for r in t.get("reviews", []):
            role = _producer_of(r.get("stage"))
            if role:
                reviews[role]["count"] += 1
                reviews[role]["issues"] += 1 if r.get("issues") else 0
                reviews[role]["cross"] += 1 if r.get("producer") != r.get("reviewer") else 0
            touch("verifier", r.get("at"),
                  f"{'지적 있음' if r.get('issues') else '특이사항 없음'} · {r.get('stage', '결과')} 검토")

    total_reviews = sum(v["count"] for v in reviews.values())
    summary = {
        "manager": f"대화 {counts['turns']}번을 받아 나눠 줌",
        "research_coach": f"실제 논문 {counts['papers']}편 · 가설 정리 {counts['hypotheses']}건",
        "analysis_partner": f"분석 {counts['analyses']}건 (성공 {counts['analyses_ok']})",
        "writing_coach": f"초안 {counts['drafts']}편",
        "verifier": f"검토 {total_reviews}건 · 지적 {sum(v['issues'] for v in reviews.values())}건",
    }
    for key, node in nodes.items():
        node["summary"] = summary[key]
        node["seconds"] = round(node["seconds"], 1)

    if live:
        role = _ROLE_OF_STEP.get(live.get("agent"))
        if role:
            nodes[role]["working"] = {"step": live["agent"], "seconds": round(time.time() - live["since"], 1)}

    return {
        "nodes": nodes,
        "live": any(n["working"] for n in nodes.values()),
        "edges": {
            "turns": counts["turns"],
            "requests": {role: nodes[role]["requests"] for role in _PRODUCERS},
            "handoffs": {
                "research_coach": counts["hypothesis_projects"],  # 문헌 → 분석: 가설
                "analysis_partner": counts["analysis_projects"],  # 분석 → 집필: 분석 결과
            },
            "reviews": reviews,
        },
    }


def dashboard(threads: list[dict], live: dict | None = None) -> dict:
    """연구실 전체 진행을 한 화면에 — 모든 프로젝트를 합친 지표, 조직도·업무 흐름, 단계 퍼널,
    연구원별 업무·시간, 회사별 모델 사용, 최근 활동 타임라인."""
    overview = lab_overview(threads)
    role_seconds = {r["key"]: 0.0 for r in ROLES}
    company_calls: dict[str, int] = {}
    timeline = []
    totals = {
        "projects": len(threads),
        "stars": overview["level"]["stars"],
        "stages_total": len(threads) * len(STAGES),
        "papers": 0,
        "analyses": 0,
        "analyses_ok": 0,
        "reviews": 0,
        "review_issues": 0,
        "cross_vendor_reviews": 0,
        "drafts": 0,
        "turns": 0,
        "agent_seconds": 0.0,
    }

    for t in threads:
        topic = t.get("topic", "(제목 없음)")
        totals["papers"] += len(t.get("references", []))
        totals["analyses"] += len(t.get("analysis", []))
        totals["analyses_ok"] += sum(1 for a in t.get("analysis", []) if a.get("ok", True))
        totals["drafts"] += 1 if t.get("draft") else 0
        for r in t.get("reviews", []):
            totals["reviews"] += 1
            totals["review_issues"] += 1 if r.get("issues") else 0
            totals["cross_vendor_reviews"] += 1 if r.get("producer") != r.get("reviewer") else 0
            if r.get("at"):
                icon = "📌" if r.get("issues") else "✅"
                timeline.append({"at": r["at"], "project": topic, "icon": icon,
                                 "text": f"외부 검토위원이 {r.get('stage')} 검토 ({r.get('reviewer')})"})
        if t.get("created_at"):
            timeline.append({"at": t["created_at"], "project": topic, "icon": "🆕", "text": "새 프로젝트 시작"})
        if t.get("draft_at"):
            timeline.append({"at": t["draft_at"], "project": topic, "icon": "✍️", "text": "초안 완성"})
        for act in t.get("activity", []):
            totals["turns"] += 1
            totals["agent_seconds"] += act.get("seconds") or 0
            for step in act.get("steps", []):
                role = _ROLE_OF_STEP.get(step["agent"])
                if role:
                    role_seconds[role] += step.get("seconds") or 0
                for model in step.get("models", []):
                    company = _company(model)
                    if company:
                        company_calls[company] = company_calls.get(company, 0) + 1
            timeline.append({
                "at": act["at"],
                "project": topic,
                "icon": "💬",
                "text": f"{_MODULE_TEXT.get(act.get('module'), '대화')} — “{act.get('message', '')}”",
                "seconds": act.get("seconds"),
            })

    timeline.sort(key=lambda e: e["at"], reverse=True)
    funnel = [
        {"label": s["label"], "count": sum(1 for p in overview["projects"] if p["progress"]["cleared"][i])}
        for i, s in enumerate(STAGES)
    ]
    researchers = [
        {
            "key": r["key"],
            "name": r["name"],
            "emoji": r["emoji"],
            "work": overview["work"][r["key"]],
            "seconds": round(role_seconds[r["key"]], 1),
        }
        for r in ROLES
    ]
    totals["agent_seconds"] = round(totals["agent_seconds"], 1)
    return {
        "level": overview["level"],
        "totals": totals,
        "funnel": funnel,
        "researchers": researchers,
        "companies": [{"company": c, "calls": company_calls.get(c, 0)} for c in _COMPANY.values()],
        "projects": overview["projects"],
        "timeline": timeline[:40],
        "org": org_chart(threads, live),
    }


def lab_overview(threads: list[dict]) -> dict:
    """연구실 화면에 필요한 것: 프로젝트 진행도, 레벨·별, 연구원별 업무 기록."""
    projects = []
    stars = 0
    for index, t in enumerate(threads):
        progress = thread_progress(t)
        stars += progress["cleared_count"]
        projects.append(
            {
                "index": index,
                "topic": t.get("topic", "(제목 없음)"),
                "created_at": t.get("created_at"),
                "progress": progress,
                "counts": {
                    "papers": len(t.get("references", [])),
                    "analyses": len(t.get("analysis", [])),
                    "reviews": len(t.get("reviews", [])),
                    "files": len(t.get("files", [])),
                    "draft": bool(t.get("draft")),
                },
            }
        )

    level = stars // STARS_PER_LEVEL + 1
    work = {
        "manager": sum(len(t.get("turns", [])) for t in threads),
        "research_coach": sum(len(t.get("references", [])) for t in threads),
        "analysis_partner": sum(len(t.get("analysis", [])) for t in threads),
        "writing_coach": sum(1 for t in threads if t.get("draft")),
        "verifier": sum(len(t.get("reviews", [])) for t in threads),
    }
    return {
        "stages": STAGES,
        "projects": projects,
        "level": {
            "level": level,
            "title": LEVEL_TITLES[min(level - 1, len(LEVEL_TITLES) - 1)],
            "stars": stars,
            "into_level": stars % STARS_PER_LEVEL,
            "per_level": STARS_PER_LEVEL,
        },
        "work": work,
    }
