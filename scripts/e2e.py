"""주제 탐색 → 분석 → 집필 전체 흐름을 실제 LLM으로 돌려보는 엔드투엔드 점검.

백엔드(uvicorn, 8420)를 먼저 띄운 뒤 실행한다:

    .venv\\Scripts\\python.exe scripts\\e2e.py

각 단계마다 어느 모듈이 받았는지, 로드맵이 실제로 채워졌는지, 교차검증이
다른 회사 모델로 돌았는지, 단계별 소요 시간을 확인해 data/e2e_result.json에 남긴다.
시나리오는 데모 대본(docs/demo_scenario.md)과 같다. 주제를 바꾸려면 STEPS만 고치면 된다.
"""

import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

API = "http://127.0.0.1:8420"
ROOT = Path(__file__).resolve().parent.parent
STORE_PATH = ROOT / "data" / "memory_store.json"
RESULT_PATH = ROOT / "data" / "e2e_result.json"

# 데모 시나리오: 신생아·영유아 비침습 연구 (docs/demo_scenario.md와 같은 대본).
# 분석 단계의 숫자는 시연용 **가상 데이터**다 — 실제 측정값처럼 발표하지 않는다.
# (보낼 메시지, 기대 모듈, 이 단계 후 기대 로드맵 %)
STEPS = [
    (
        "신생아랑 영유아 대상으로 비침습 연구를 해보고 싶은데, 신입이 시작할 만한 "
        "연구 주제를 어떻게 잡으면 좋을까?",
        "research_coach",
        40,
    ),
    (
        "카메라 기반 비접촉 심박 측정(rPPG) 데이터로 분석 돌려줘. 신생아 12명의 같은 "
        "시점 심박수(bpm)야. 심전도(ECG) 기준값은 142, 128, 155, 136, 149, 131, 160, 138, "
        "145, 152, 127, 140 이고, 카메라(rPPG) 측정값은 145, 125, 151, 139, 147, 135, 156, "
        "141, 149, 148, 131, 137 이야. 평균 절대 오차, 피어슨 상관계수, Bland-Altman "
        "편향과 95% 일치 한계를 계산해서 카메라 측정이 ECG를 대신할 수 있는지 봐줘.",
        "analysis_partner",
        80,
    ),
    ("이 결과를 논문 서론에 녹여서 초안 써줘.", "writing_coach", 80),
    (
        "제 해석은 이렇습니다. 편향이 거의 0이고 일치 한계가 ±7bpm 정도라, 카메라 측정이 "
        "신생아 심박 모니터링의 보조 수단으로는 가능성이 있다고 봅니다. 다만 12명뿐이고, "
        "조명과 움직임이 통제된 환경에서 잰 값이라 실제 신생아 중환자실 조건이나 다양한 "
        "피부톤에서도 같을지는 모릅니다. 서론에서는 전극 부착이 미숙아 피부 손상과 "
        "스트레스를 일으킨다는 문제를 비침습 측정이 필요한 이유로 강조하고 싶습니다.",
        "writing_coach",
        100,
    ),
]

# claude와 claude_harness는 같은 회사 모델이다.
VENDOR = {"claude": "anthropic", "claude_harness": "anthropic", "openai": "openai", "gemini": "google"}


def _request(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        API + path, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=900) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        # 백엔드는 모델 호출 실패(사용 한도 등)를 503 + 이유로 돌려준다 — 이유를 그대로 보여준다.
        detail = err.read().decode("utf-8", "replace")
        sys.exit(f"\n{method} {path} 실패 (HTTP {err.code}): {detail}")


def main() -> int:
    session_id = "e2e-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    providers = _request("GET", "/health")["providers"]
    print(f"providers: {providers}")
    print(f"session:   {session_id}\n")

    rows, failures = [], []
    for i, (message, expected_module, expected_pct) in enumerate(STEPS, 1):
        started = time.perf_counter()
        res = _request("POST", "/chat", {"session_id": session_id, "message": message})
        elapsed = time.perf_counter() - started

        threads = _request("GET", f"/threads/{session_id}")["threads"]
        pct = threads[-1]["progress"]["percent"] if threads else 0
        verified_by = res.get("verified_by")  # 해석을 묻는 질문 단계는 검증하지 않는다
        cross = verified_by is not None and VENDOR.get(res["produced_by"]) != VENDOR.get(verified_by)

        row = {
            "step": i,
            "module": res["module"],
            "produced_by": res["produced_by"],
            "verified_by": res["verified_by"],
            "cross_vendor_verification": cross,
            "roadmap_percent": pct,
            "seconds": round(elapsed, 1),
            "reply": res["reply"],
            "review": res.get("review"),
            "trace": res.get("trace"),
        }
        rows.append(row)
        print(
            f"[{i}] {res['module']:<16} 생성={res['produced_by']:<14} 검증={verified_by or '-':<14} "
            f"이종검증={'-' if verified_by is None else 'O' if cross else 'X'}  로드맵={pct:>3}%  {elapsed:6.1f}s"
        )

        if res.get("trace"):
            flow = " → ".join(
                f"{t['agent']}({', '.join(t['models']) or '-'})" for t in res["trace"]
            )
            print(f"      흐름: {flow}")

        if i == 1 and "참고 논문" not in res["reply"]:
            failures.append("1단계 답변에 실제 검색된 참고 논문 목록이 없다")
        if res["module"] != expected_module:
            failures.append(f"{i}단계 모듈: 기대 {expected_module}, 실제 {res['module']}")
        if pct != expected_pct:
            failures.append(f"{i}단계 로드맵: 기대 {expected_pct}%, 실제 {pct}%")

    # 마지막 응답에 저장된 초안이 원문 그대로 들어 있어야 한다.
    store = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    draft = store[session_id]["threads"][-1].get("draft", "")
    if not draft or draft not in res["reply"]:
        failures.append("마지막 응답에 저장된 초안이 원문 그대로 포함되지 않았다")

    RESULT_PATH.write_text(
        json.dumps(
            {"session_id": session_id, "providers": providers, "steps": rows, "failures": failures},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    total = sum(r["seconds"] for r in rows)
    print(f"\n총 소요: {total:.0f}초  결과: {RESULT_PATH}")
    if failures:
        print("실패:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("전 단계 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
