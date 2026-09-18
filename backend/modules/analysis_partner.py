from datetime import datetime

import tracing
from config import get_adapter
from instructions import with_custom_instructions
from memory.store import current_thread, get_session, save_session, thread_brief
from sandbox.executor import run_python

CODE_SYSTEM_PROMPT = """\
너는 데이터 분석 코드를 작성하는 전문 모듈이다. 사용자 요청에 맞는 Python
코드만 출력해라 (설명 없이 코드 블록만, ```python 으로 감싸서). 결과는 반드시
print()로 출력해라.
쓸 수 있는 라이브러리는 표준 라이브러리와 numpy, scipy, pandas뿐이다. 패키지를
설치하는 코드(pip 등)는 절대 쓰지 마라.
사용자가 주지 않은 판정 기준(예: "임상 허용 오차 ±10")을 임의로 정해서 "통과/실패"
같은 결론을 출력하지 마라. 계산한 수치만 출력한다.
"""

FIX_SYSTEM_PROMPT = """\
아래 코드가 실행 중 에러가 났다. 에러 메시지를 참고해서 코드를 고쳐서
다시 Python 코드만 출력해라 (```python 으로 감싸서).
쓸 수 있는 라이브러리는 표준 라이브러리와 numpy, scipy, pandas뿐이다. 없는 모듈이면
설치하지 말고 이 라이브러리들로 다시 구현해라.
"""

INTERPRET_SYSTEM_PROMPT = """\
아래는 데이터 분석 실행 결과다. [요청]에 사용자가 밝힌 데이터의 출처와 조건을
전제로, 이 세션에서 앞서 논의된 연구 가설과 연결지어 이 결과가 가설을
지지하는지/반박하는지 짧게 해석해라.
"""

MAX_RETRY = 2


def _extract_code(text: str) -> str:
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            stripped = part.strip()
            if stripped.startswith("python"):
                return stripped[len("python"):].strip()
        return parts[1].strip() if len(parts) > 1 else text.strip()
    return text.strip()


def _files_block(files: list[dict]) -> str:
    if not files:
        return ""
    lines = [
        f"- {f['name']}: {f['rows']}행, 열 = {', '.join(f['columns'])}" for f in files
    ]
    return (
        "\n\n[첨부 데이터 파일] 현재 작업 폴더에 있으니 파일명 그대로 읽어라 "
        "(예: pd.read_csv('파일명')).\n" + "\n".join(lines)
    )


def run(session_id: str, message: str) -> str:
    thread = current_thread(session_id)
    files = (thread or {}).get("files", [])
    previous = (thread or {}).get("analysis", [])
    # 후속 분석("로그 변환해서 다시")이 앞선 코드를 이어받을 수 있게 직전 코드를 넘긴다.
    previous_block = f"\n\n[직전 분석 코드]\n{previous[-1]['code'][:2000]}" if previous else ""

    coder = get_adapter("analysis_partner")
    with tracing.step("분석 코드 작성"):
        code = _extract_code(
            coder.generate(
                CODE_SYSTEM_PROMPT,
                [{"role": "user", "content": message + _files_block(files) + previous_block}],
            )
        )

    paths = [f["path"] for f in files]
    with tracing.step("코드 실행") as rec:
        ok, output = run_python(code, paths)
        attempts = 0
        while not ok and attempts < MAX_RETRY:
            attempts += 1
            fix_prompt = f"[코드]\n{code}\n\n[에러]\n{output}"
            code = _extract_code(
                coder.generate(FIX_SYSTEM_PROMPT, [{"role": "user", "content": fix_prompt}])
            )
            ok, output = run_python(code, paths)
        rec["detail"] = ("성공" if ok else "실패") + (f" (자동 수정 {attempts}회)" if attempts else "")

    # 해석은 연구 문맥 이해가 중요하므로 문헌/가설 담당 모듈과 같은 provider를 쓴다.
    # 코드 생성 단계에는 KISTO.md 지침을 넣지 않는다 — "코드만 출력" 형식이 깨질 수 있어서,
    # 사용자 지침은 해석 단계에서만 반영한다.
    with tracing.step("결과 해석"):
        interpreter = get_adapter("research_coach")
        interpretation = interpreter.generate(
            system_prompt=with_custom_instructions(INTERPRET_SYSTEM_PROMPT, "analysis_partner"),
            messages=[
                {
                    "role": "user",
                    # 원래 요청을 빼면 해석이 "이 데이터가 누구 것인지 모른다"고 헛짚는다.
                    "content": (
                        f"[요청]\n{message}\n\n[지금까지의 연구 맥락]\n{thread_brief(thread)}\n\n"
                        f"[코드]\n{code}\n\n[실행결과]\n{output}"
                    ),
                }
            ],
        )

    session = get_session(session_id)
    if session["threads"]:
        session["threads"][-1]["analysis"].append(
            {
                "code": code,
                "output": output,
                "interpretation": interpretation,
                "ok": ok,
                "at": datetime.now().isoformat(timespec="seconds"),
            }
        )
        save_session(session_id, session)

    status = "성공" if ok else "실패 (재시도 소진)"
    return f"[분석 {status}]\n\n실행 결과:\n{output}\n\n해석:\n{interpretation}"
