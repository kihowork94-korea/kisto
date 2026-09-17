from config import get_adapter
from instructions import with_custom_instructions
from memory.store import current_thread, get_session, save_session
from sandbox.executor import run_python

CODE_SYSTEM_PROMPT = """\
너는 데이터 분석 코드를 작성하는 전문 모듈이다. 사용자 요청에 맞는 Python
코드만 출력해라 (설명 없이 코드 블록만, ```python 으로 감싸서). pandas/numpy
등 표준 라이브러리를 가정해도 된다. 결과는 반드시 print()로 출력해라.
"""

FIX_SYSTEM_PROMPT = """\
아래 코드가 실행 중 에러가 났다. 에러 메시지를 참고해서 코드를 고쳐서
다시 Python 코드만 출력해라 (```python 으로 감싸서).
"""

INTERPRET_SYSTEM_PROMPT = """\
아래는 데이터 분석 실행 결과다. 이 세션에서 앞서 논의된 연구 가설과
연결지어, 이 결과가 가설을 지지하는지/반박하는지 짧게 해석해라.
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


def run(session_id: str, message: str) -> str:
    coder = get_adapter("analysis_partner")
    code = _extract_code(
        coder.generate(CODE_SYSTEM_PROMPT, [{"role": "user", "content": message}])
    )

    ok, output = run_python(code)
    attempts = 0
    while not ok and attempts < MAX_RETRY:
        attempts += 1
        fix_prompt = f"[코드]\n{code}\n\n[에러]\n{output}"
        code = _extract_code(
            coder.generate(FIX_SYSTEM_PROMPT, [{"role": "user", "content": fix_prompt}])
        )
        ok, output = run_python(code)

    thread = current_thread(session_id)
    hypotheses_context = "\n".join(thread["hypotheses"]) if thread and thread.get("hypotheses") else "(없음)"

    # 해석은 연구 문맥 이해가 중요하므로 문헌/가설 담당 모듈과 같은 provider를 쓴다.
    # 코드 생성 단계에는 KISTO.md 지침을 넣지 않는다 — "코드만 출력" 형식이 깨질 수 있어서,
    # 사용자 지침은 해석 단계에서만 반영한다.
    interpreter = get_adapter("research_coach")
    interpretation = interpreter.generate(
        system_prompt=with_custom_instructions(INTERPRET_SYSTEM_PROMPT),
        messages=[
            {
                "role": "user",
                "content": f"[가설]\n{hypotheses_context}\n\n[코드]\n{code}\n\n[실행결과]\n{output}",
            }
        ],
    )

    session = get_session(session_id)
    if session["threads"]:
        session["threads"][-1]["analysis"].append(
            {"code": code, "output": output, "interpretation": interpretation}
        )
        save_session(session_id, session)

    status = "성공" if ok else "실패 (재시도 소진)"
    return f"[분석 {status}]\n\n실행 결과:\n{output}\n\n해석:\n{interpretation}"
