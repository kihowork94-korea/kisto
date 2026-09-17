# 키스토 (KISTO) — 프로토타입 백엔드

KIST AIX 성과공유회 출품용, "파편화된 AI 챗 대신 한 명의 연구 동료"
컨셉의 내부 두뇌 부분. 캐릭터 UI는 나중에 씌운다 — 지금은 라우터 +
멀티 프로바이더 어댑터 + 4개 전문 모듈 + 메모리 + 연구 로드맵이 실제로
동작하는지 확인하는 단계.

## 구조

- `backend/config.py` — provider 등록과 모듈별 모델 매핑. 키가 없는 provider는
  `_FALLBACK_CHAIN` 순서로 자동 대체된다
- `backend/adapters/` — provider별 ModelAdapter 구현 (`base.py`가 공통 인터페이스)
  - `claude_adapter.py` / `openai_adapter.py` / `gemini_adapter.py` — API 키 방식
  - `claude_harness_adapter.py` — **API 키 없이** 로그인된 Claude Code CLI를 그대로 사용
- `backend/instructions.py` + 루트 `KISTO.md` — 사용자가 편집하는 지침 파일
- `backend/orchestrator/router.py` — 의도 분류 + 세션 스레드 상태 관리
- `backend/orchestrator/persona.py` — 어떤 모듈/모델이 답했든 "키스토" 말투로 통일
- `backend/modules/`
  - `research_coach.py` — 문헌/가설 (모듈 A)
  - `analysis_partner.py` — 데이터/코드 분석, 샌드박스 실행 + 자동 재시도 (모듈 B)
  - `writing_coach.py` — 집필 지원. 대필하지 않고 먼저 사용자 해석을 물음 (모듈 C)
  - `verifier.py` — 결과를 만든 것과 다른 provider로 교차검증 (모듈 D)
- `backend/memory/store.py` — 세션별 연구 스레드 + **연구 로드맵 진행 상태**
- `backend/sandbox/executor.py` — 생성된 분석 코드 격리 실행

## 두 가지 실행 방식

**A. API 키 없이 (Claude Code 하네스 사용)**
`claude` CLI가 PATH에 있고 로그인되어 있으면 아무 설정 없이 그냥 실행하면 된다.
별도 과금키 발급이 필요 없어 개인 개발/데모에 적합하다.

**B. API 키 사용 (멀티 프로바이더)**
`.env.example`을 `.env`로 복사하고 원하는 키를 채운다. 세 개를 다 넣으면
모듈 B는 OpenAI 코딩 모델이, 검증 모듈 D는 Gemini가 맡는 식으로 교차검증이
실제로 서로 다른 회사 모델 사이에서 일어난다.

```bash
pip install -r requirements.txt
cd backend
uvicorn main:app --reload --port 8420
```

프론트엔드는 `fetch`를 쓰므로 file://로 열면 안 되고 HTTP로 서빙해야 한다:

```bash
cd frontend
python -m http.server 8500
```

그 다음 `http://localhost:8500/index.html` 접속.
`GET /health`로 현재 어떤 provider가 잡혔는지 확인할 수 있다.

## 키스토에게 지침 주기 — `KISTO.md`

루트의 `KISTO.md`가 CLAUDE.md와 같은 역할을 한다. 성격, 답변 규칙, 연구 분야를
적어두면 모듈 A/B(해석)/C와 페르소나 레이어의 프롬프트에 자동으로 주입된다.
**매 호출마다 새로 읽으므로 서버 재시작 없이 바로 반영된다.**

코드 생성 단계에는 일부러 주입하지 않는다 — "코드만 출력" 형식이 깨질 수 있어서,
사용자 지침은 해석 단계부터 반영된다.

## 연구 로드맵 (`GET /threads/{session_id}`)

"대화를 주제별 폴더로 묶는" 기능이 아니다. 그건 이미 다른 AI 챗에도 있다.
여기서 추적하는 건 **각 연구 주제가 연구 프로세스의 어느 단계까지 왔는가**이고,
게임 퀘스트처럼 시각화된다.

```
주제 잡기 → 가설 세우기 → 분석 돌리기 → 교차검증 → 초안 쓰기
```

각 단계는 장식이 아니라 실제 저장된 데이터로만 판정된다 (가설이 저장돼야
2단계 클리어, 분석 결과가 있어야 3단계, 교차검증 기록이 남아야 4단계).
교차검증은 분석 모듈이 돌았을 때만 달성으로 인정한다 — 잡담까지 "검증 완료"로
치면 로드맵이 의미를 잃기 때문.

## 지금 이 단계에서 확인할 것

- "이 분야 연구주제 뭐로 잡을까" → research_coach가 가설 후보 + 되묻는 질문을 내는지
- 코드가 필요한 분석 질문 → 코드 생성 → 실행 → (에러 시 재시도) → 가설과
  연결지은 해석까지 하는지
- "논문 서론에 녹여줘" → 바로 초안을 안 주고 먼저 사용자 해석을 묻는지
- 대화를 진행하면서 상단 로드맵의 단계가 하나씩 채워지는지
- 응답 끝의 `[디버그: 모듈명 / provider명]`은 개발 확인용 — 실제 데모/캐릭터
  UI에는 반드시 제거해야 한다 (사용자는 내부 구조를 몰라야 "한 명의 동료"라는
  컨셉이 산다)

## 알려진 한계 / 다음 단계

- 코드 샌드박스는 로컬 subprocess 격리 수준의 프로토타입이다. 실제 배포 전에는
  컨테이너 등 더 강한 격리가 필요하다.
- 하네스 어댑터는 매 호출이 독립된 1턴이라 CLI 쪽 대화 맥락은 이어지지 않는다
  (맥락은 키스토의 메모리 레이어가 담당한다).
- 라우터가 매 메시지마다 분류용 LLM 호출을 1회 더 하므로 약간의 지연이 있다.
- 메모리는 JSON 파일 하나 — 동시 사용자가 늘면 DB로 바꿔야 한다.
- 다음 단계: Electron으로 캐릭터 위젯 UI 씌우기, 디버그 표시 제거,
  KIST-PaperBanana 등 사내 시스템 연동은 로드맵으로 남긴다.
