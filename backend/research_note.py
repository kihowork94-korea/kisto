"""연구 주제 하나(스레드)를 연구노트 형식의 Markdown으로 정리한다.

국가 R&D 과제는 연구노트 작성이 의무라, 키스토가 쌓은 기록(가설 논의, 분석 코드와
결과, 교차검증, 연구자 해석, 초안, 참고문헌)을 그대로 연구노트 초안으로 뽑아준다.
모델을 부르지 않고 저장된 데이터만으로 만든다 — 기록이 바뀌지 않아야 하기 때문이다.
"""

import re
from datetime import datetime

from literature import format_reference_list
from memory.store import thread_progress


def _slug(text: str) -> str:
    return re.sub(r"[^\w가-힣]+", "_", text).strip("_")[:40] or "research"


def build_note(thread: dict, stages: list[dict]) -> dict:
    progress = thread_progress(thread)
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [
        f"# 연구노트 — {thread.get('topic')}",
        "",
        f"- 작성일: {today} (시작: {thread.get('created_at', '기록 없음')})",
        "- 진행 단계: "
        + " → ".join(
            f"{'✅' if done else '⬜'} {s['label']}" for s, done in zip(stages, progress["cleared"])
        ),
        "- 작성 방식: 키스토가 대화 기록을 자동 정리한 **초안**. 연구자가 검토 후 서명해야 연구노트로 인정된다.",
        "",
        "## 1. 연구 주제 및 가설 논의",
        "",
    ]
    hypotheses = thread.get("hypotheses", [])
    lines += [hypotheses[-1] if hypotheses else "(기록 없음)", ""]

    lines += ["## 2. 데이터 및 분석", ""]
    for f in thread.get("files", []):
        lines.append(f"- 첨부 데이터: `{f['name']}` ({f['rows']}행, 열: {', '.join(f['columns'])})")
    analyses = thread.get("analysis", [])
    if not analyses:
        lines += ["", "(기록 없음)"]
    for i, a in enumerate(analyses, 1):
        lines += [
            "",
            f"### 분석 {i}",
            "",
            "**실행 코드**",
            "",
            "```python",
            a["code"],
            "```",
            "",
            "**실행 결과**",
            "",
            "```",
            a["output"],
            "```",
            "",
            "**해석**",
            "",
            a["interpretation"],
        ]

    lines += ["", "## 3. 교차검증 기록 (결과를 만든 것과 다른 모델의 검토)", ""]
    verifications = thread.get("verifications", [])
    lines += [f"### 검토 {i}\n\n{v}\n" for i, v in enumerate(verifications, 1)] or ["(기록 없음)"]

    lines += ["", "## 4. 연구자 해석", "", thread.get("interpretation") or "(기록 없음)", ""]
    lines += ["## 5. 초안", "", thread.get("draft") or "(아직 없음)", ""]

    refs = thread.get("references", [])
    if refs:
        lines += ["## 6. 검색한 참고문헌", "", format_reference_list(refs).replace("\n", "\n\n"), ""]

    lines += ["---", "", "검토자: ______________ 서명: ______________ 날짜: ______________", ""]
    return {
        "filename": f"{today}_{_slug(thread.get('topic', ''))}.md",
        "markdown": "\n".join(lines),
    }
