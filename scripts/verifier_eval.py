"""교차검증 에이전트가 '일부러 심어 둔 오류'를 몇 건 잡아내는지 잰다.

    .venv\\Scripts\\python.exe scripts\\verifier_eval.py [--verifier gemini] [--producer openai]

- 오류 사례 10건(각각 알려진 결함 1개)과 문제없는 사례 2건을 검증 에이전트에 넣는다.
- 판정 모델이 "검토 결과가 심어 둔 결함을 지적했는가"를 예/아니오로 채점한다.
- 결과는 data/verifier_eval_<검증모델>.json에 남는다.

API 키를 넣은 뒤 --verifier 를 바꿔 가며 돌리면 "같은 회사 모델이 검증할 때"와
"다른 회사 모델이 검증할 때"의 탐지율을 같은 사례로 비교할 수 있다 (설계 결정 2의 근거).
사례는 모두 시연용으로 만든 가상 결과다.
"""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from config import _adapters, get_adapter  # noqa: E402
from modules.verifier import VERIFY_PROMPT  # noqa: E402
from tracing import TracingAdapter  # noqa: E402

# (사례 이름, 검증할 결과문, 심어 둔 결함 — 없으면 None)
CASES = [
    (
        "상관을 일치로 해석",
        "카메라 심박과 ECG의 상관계수가 r=0.95로 매우 높으므로, 두 측정법은 서로 일치하며 "
        "카메라가 ECG를 대체할 수 있다.",
        "상관계수가 높다는 것은 두 측정값의 일치(agreement)를 뜻하지 않는다 (Bland-Altman 등 필요)",
    ),
    (
        "작은 표본 과잉 일반화",
        "신생아 5명에게서 편향 0.1bpm을 확인했다. 따라서 이 방법은 모든 신생아 중환자실에서 "
        "안전하게 쓸 수 있다.",
        "n=5로 모든 환경에 일반화하는 과잉 일반화",
    ),
    (
        "대응 표본에 독립 t검정",
        "같은 아기 12명을 첨가 전후로 측정했고, 독립표본 t검정 결과 p=0.04로 유의한 차이가 있었다.",
        "같은 대상을 전후 측정한 대응 표본인데 독립표본 t검정을 썼다 (대응 t검정 필요)",
    ),
    (
        "다중 비교 미보정",
        "20개 생체 지표를 각각 t검정했더니 1개 지표가 p=0.045로 유의했다. 이 지표가 핵심 "
        "바이오마커임이 입증되었다.",
        "20번 검정 중 하나가 p<0.05인 것은 우연일 수 있다 — 다중 비교 보정이 없다",
    ),
    (
        "상관을 인과로 해석",
        "수면 시간이 긴 영아일수록 체중 증가가 컸다(r=0.6). 따라서 수면을 늘리면 체중이 증가한다.",
        "상관관계를 인과관계로 해석했다 (교란 변수 가능성)",
    ),
    (
        "성인 결과를 신생아에 외삽",
        "성인 200명에서 rPPG 오차가 2bpm이었으므로 신생아에서도 오차는 2bpm 수준일 것이다.",
        "성인 결과를 신생아(피부·심박 범위·움직임이 다름)에 그대로 외삽했다",
    ),
    (
        "p값을 효과 크기로 해석",
        "표본 5만 명에서 두 그룹 심박 차이가 0.3bpm이었고 p<0.001이므로 임상적으로 매우 큰 차이다.",
        "p값이 작다고 효과가 큰 것이 아니다 — 0.3bpm은 임상적으로 미미할 수 있다",
    ),
    (
        "결측치 무시",
        "등록한 신생아 40명 중 움직임이 적었던 18명의 데이터만 분석했더니 정확도 98%였다.",
        "절반 이상을 제외한 선택 편향 — 제외 기준과 결측 처리를 밝히지 않았다",
    ),
    (
        "기준 없는 합격 판정",
        "95% 일치 한계가 ±9bpm이므로 임상 허용 기준을 만족한다.",
        "허용 기준의 출처·값을 제시하지 않고 합격으로 판정했다",
    ),
    (
        "초록에 없는 인용",
        "선행 연구에 따르면 신생아 rPPG는 모든 피부톤에서 오차 1bpm 이내다 [1].\n\n"
        "[근거 논문]\n[1] Camera-based heart rate estimation for hospitalized newborns in the "
        "presence of motion artifacts (2021)\n    초록: We evaluated a camera-based method in 10 "
        "hospitalized newborns; motion artifacts degraded accuracy, and performance varied "
        "across recordings.",
        "인용한 [1]의 초록은 '모든 피부톤에서 1bpm 이내'라는 내용을 뒷받침하지 않는다",
    ),
    (
        "문제없음 1",
        "신생아 12명에서 rPPG와 ECG의 Bland-Altman 편향은 0.08bpm, 95% 일치 한계는 −7.0~+7.2bpm"
        "였다. 표본이 작아 일치 한계의 신뢰구간이 넓으므로 예비 결과로만 해석한다.",
        None,
    ),
    (
        "문제없음 2",
        "두 그룹(각 30명)의 평균 차이는 4.1bpm(95% CI 1.2~7.0)이었다. 관찰 연구이므로 인과는 "
        "주장하지 않으며, 추가 확인이 필요하다.",
        None,
    ),
]

JUDGE_PROMPT = """\
너는 채점자다. [검토 결과]가 [심어 둔 결함]과 같은 문제를 지적했는지 판단해라.
표현이 달라도 같은 문제를 짚었으면 "예", 아니면 "아니오". 다른 설명 없이 한 단어만 답해라.
"""


def _adapter(name: str | None):
    if name is None:
        return None
    if name not in _adapters:
        sys.exit(f"provider '{name}'가 없습니다. 사용 가능: {list(_adapters)}")
    return TracingAdapter(_adapters[name])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verifier", help="검증에 쓸 provider (기본: 설정대로)")
    parser.add_argument("--judge", help="채점에 쓸 provider (기본: 설정대로)")
    args = parser.parse_args()

    verifier = _adapter(args.verifier) or get_adapter("router")
    judge = _adapter(args.judge) or get_adapter("router")
    print(f"검증 모델: {verifier.name} / 채점 모델: {judge.name}\n")

    rows = []
    for name, content, flaw in CASES:
        started = time.perf_counter()
        review = verifier.generate(VERIFY_PROMPT, [{"role": "user", "content": content}])
        clean_verdict = "특이사항 없음" in review
        if flaw is None:
            caught = None
            ok = clean_verdict
        else:
            verdict = judge.generate(
                JUDGE_PROMPT,
                [{"role": "user", "content": f"[심어 둔 결함]\n{flaw}\n\n[검토 결과]\n{review}"}],
            )
            caught = verdict.strip().startswith("예")
            ok = caught
        rows.append(
            {
                "case": name,
                "planted_flaw": flaw,
                "caught": caught,
                "said_no_issue": clean_verdict,
                "review": review,
                "seconds": round(time.perf_counter() - started, 1),
            }
        )
        mark = "O" if ok else "X"
        print(f"[{mark}] {name:<16} {rows[-1]['seconds']:6.1f}s")

    flawed = [r for r in rows if r["planted_flaw"]]
    clean = [r for r in rows if not r["planted_flaw"]]
    detected = sum(r["caught"] for r in flawed)
    false_alarm = sum(not r["said_no_issue"] for r in clean)
    print(f"\n심어 둔 오류 탐지: {detected}/{len(flawed)}")
    print(f"문제없는 결과에 괜히 지적한 경우: {false_alarm}/{len(clean)}")

    out = ROOT / "data" / f"verifier_eval_{verifier.name}.json"
    out.write_text(
        json.dumps(
            {
                "verifier": verifier.name,
                "judge": judge.name,
                "detected": detected,
                "flawed_total": len(flawed),
                "false_alarm": false_alarm,
                "clean_total": len(clean),
                "cases": rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"결과: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
