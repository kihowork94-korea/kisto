# .env에 넣은 OpenAI·Gemini 키가 실제로 되는지, 설정한 모델 이름으로 호출되는지 확인한다.
#
#   .venv\Scripts\python.exe scripts\check_api_keys.py
#
# 하는 일 (백엔드를 띄우기 전에 돌린다):
#   1. 키가 있는지 (키 값은 끝 4자리만 보여준다)
#   2. 그 키로 쓸 수 있는 모델 목록 — 모델 이름을 모를 때 여기서 고른다
#   3. 백엔드가 쓸 모델(.env의 *_MODEL, 비우면 어댑터 기본값)로 짧은 테스트 호출 1번
# 실패하면 이유를 한국어로 알려준다 (키 틀림 / 결제 필요 / 모델 이름 없음 …).
# 테스트 호출은 "OK" 한 단어를 받는 정도라 비용은 무시할 만하다.
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

if hasattr(sys.stdout, "reconfigure"):  # 한국어 Windows 콘솔(cp949) 대응
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

PROMPT = "Reply with the single word OK."
# 어댑터(backend/adapters)의 기본값과 같아야 한다
DEFAULT = {"openai": "gpt-5.1-codex", "gemini": "gemini-3.8-flash"}


def masked(key: str) -> str:
    return f"…{key[-4:]} ({len(key)}자)" if len(key) > 8 else "(너무 짧음 — 잘못 붙여넣은 것 같다)"


# 대화에 못 쓰는 모델(음성·이미지·임베딩 등)은 목록에서 뺀다
NOT_CHAT = re.compile(r"(tts|transcri|audio|realtime|search|image|embed|whisper|dall-e|moderation|instruct|"
                      r"babbage|davinci|sora|computer-use|customtools|16k)")


def newest_first(names: list[str]) -> list[str]:
    """버전 숫자가 큰 것부터 (gpt-5.5 > gpt-5.4 > gpt-4o, gemini-3.8 > gemini-2.5)."""
    def version(n: str):
        return [int(x) for x in re.findall(r"\d+", n.split("-20")[0])] or [0]
    return sorted((n for n in names if not NOT_CHAT.search(n)), key=lambda n: (version(n), n), reverse=True)


def show_models(names: list[str], current: str, limit: int = 25) -> None:
    names = newest_first(names)
    if not names:
        print("   쓸 수 있는 모델을 찾지 못했다")
        return
    mark = lambda n: " ◀ 지금 설정" if n == current else ""
    print(f"   이 키로 쓸 수 있는 모델 {len(names)}개 (일부):")
    for n in names[:limit]:
        print(f"     - {n}{mark(n)}")
    if current not in names:
        print(f"   ⚠ 지금 설정한 '{current}'이(가) 목록에 없다 → .env에서 위 이름 중 하나로 바꿀 것")


def check_openai() -> bool:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    print("\n[OpenAI · GPT]  분석 연구원 담당")
    if not key:
        print("   키 없음 — .env의 OPENAI_API_KEY= 뒤에 붙여넣기 (건너뜀)")
        return False
    print("   키:", masked(key))
    import openai

    client = openai.OpenAI(api_key=key)
    model = os.environ.get("OPENAI_MODEL") or DEFAULT["openai"]
    try:
        names = [m.id for m in client.models.list() if m.id.startswith(("gpt", "o"))]
        show_models(names, model)
    except openai.AuthenticationError:
        print("   ✗ 키가 틀렸다 (401). platform.openai.com → API keys에서 새로 만들어 다시 붙여넣을 것")
        return False
    except openai.APIConnectionError:
        print("   ✗ OpenAI 서버에 연결하지 못했다 — 인터넷·사내 방화벽 확인")
        return False

    print(f"   테스트 호출: {model} …")
    try:
        r = client.responses.create(model=model, instructions=PROMPT, input="ping")
        print(f"   ✓ 성공 — 답: {r.output_text.strip()[:40]!r}")
        return True
    except openai.NotFoundError:
        print(f"   ✗ '{model}' 모델이 없거나 이 계정에 권한이 없다 → .env의 OPENAI_MODEL을 위 목록 중 하나로")
    except openai.RateLimitError as e:
        if "insufficient_quota" in str(e):
            print("   ✗ 크레딧이 없다 — platform.openai.com → Billing에서 결제수단 등록·충전 필요")
            print("     (ChatGPT Plus 구독과 API 결제는 별개다)")
        else:
            print("   ✗ 호출 한도 초과 (429) — 잠시 뒤 다시")
    except openai.BadRequestError as e:
        print(f"   ✗ 요청 거부 (400): {getattr(e, 'message', e)}")
        print("     이 모델이 Responses API를 지원하지 않을 수 있다 → OPENAI_MODEL을 다른 모델로")
    except openai.APIError as e:
        print(f"   ✗ 실패: {getattr(e, 'message', e)}")
    return False


def check_gemini() -> bool:
    key = os.environ.get("GOOGLE_API_KEY", "").strip()
    print("\n[Google · Gemini]  외부 검토위원 담당 (교차검증 1순위)")
    if not key:
        print("   키 없음 — .env의 GOOGLE_API_KEY= 뒤에 붙여넣기 (건너뜀)")
        return False
    print("   키:", masked(key))
    from google import genai
    from google.genai import errors, types

    client = genai.Client(api_key=key)
    model = os.environ.get("GEMINI_MODEL") or DEFAULT["gemini"]
    try:
        names = list(
            m.name.removeprefix("models/")
            for m in client.models.list()
            if "gemini" in (m.name or "") and "generateContent" in (m.supported_actions or [])
        )
        show_models(names, model)
    except errors.ClientError as e:
        if e.code in (400, 401, 403):
            print(f"   ✗ 키가 틀렸거나 막혀 있다 ({e.code}). aistudio.google.com/apikey에서 확인할 것")
        else:
            print(f"   ✗ 실패 ({e.code}): {e.message}")
        return False
    except Exception as e:  # 네트워크 등
        print(f"   ✗ Google 서버에 연결하지 못했다: {e}")
        return False

    print(f"   테스트 호출: {model} …")
    try:
        r = client.models.generate_content(
            model=model, contents="ping", config=types.GenerateContentConfig(system_instruction=PROMPT)
        )
        print(f"   ✓ 성공 — 답: {(r.text or '').strip()[:40]!r}")
        return True
    except errors.ClientError as e:
        if e.code == 404:
            print(f"   ✗ '{model}' 모델을 쓸 수 없다 → .env의 GEMINI_MODEL을 위 목록 중 하나로")
            print(f"     Google 안내: {(e.message or '')[:160]}")
        elif e.code == 429:
            print("   ✗ 호출 한도 초과 (429) — 무료 등급 한도일 수 있다. 잠시 뒤 다시, 또는 결제 등록")
        else:
            print(f"   ✗ 실패 ({e.code}): {e.message}")
    except errors.ServerError as e:
        print(f"   ✗ Google 쪽 오류 ({e.code}) — 잠시 뒤 다시")
    return False


def main() -> int:
    if not (ROOT / ".env").exists():
        print(".env 파일이 없다 — 프로젝트 폴더에 .env를 만들고 키를 넣을 것 (.env.example 참고)")
        return 1
    ok = {"openai": check_openai(), "gemini": check_gemini()}
    print("\n── 결과 ──")
    if any(ok.values()):
        names = [n for n, v in ok.items() if v]
        print(f"✓ {', '.join(names)} 사용 가능 → 백엔드를 재시작하면 반영된다:  run.cmd -BackendOnly")
        print("  그다음:  .venv\\Scripts\\python.exe scripts\\e2e.py   (이종검증 열이 O인지)")
        return 0
    print("✗ 쓸 수 있는 키가 없다 — 위 메시지대로 고친 뒤 다시 돌릴 것")
    return 1


if __name__ == "__main__":
    sys.exit(main())
