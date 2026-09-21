# 키스토(KISTO) 인수인계

> 2026-09-18 작성 (Claude Code → 다음 작업자/Codex). 이 문서만 읽고 이어서 작업할 수 있게 쓴다.
> 프로젝트의 원칙·결정 기록은 `CLAUDE.md`, 사용법은 `README.md`. 이 문서와 겹치는 부분은 이 문서가 요약이다.

## 1. 한 줄 요약과 마감

**2026 KIST AIX 성과 공유회 출품작.** 신입 연구자가 바탕화면 캐릭터 '키스토' 한 명과 대화하면, 뒤에서
문헌·분석·검토·집필 AI 연구원들이 협업하는 "나만의 연구실". 핵심 차별점은 **결과를 만든 모델과 다른 회사
모델이 검토하는 교차검증**, **실제 검색된 논문만 인용**, **대필 금지(연구자 해석을 먼저 물음)**, **게임식 연구실**.

| 일정 | 날짜 |
|---|---|
| 서류 마감 | **2026-10-02(금)** |
| 1단계 결과 | ~10-08 |
| 발표 | 10-28 (10분 + Q&A 5분) |

심사배점: 창의성 40 / 업무활용성 30 / 확산가능성 30.

## 2. 지금 바로 실행하기

```bat
:: 바탕화면의 "키스토" 아이콘 = 아래와 같다 (백엔드 + 위젯 + 대화창 펼침 + 연구실)
run.cmd -Chat -Lab
:: 백엔드만
run.cmd -BackendOnly
```

- 백엔드: `http://127.0.0.1:8420` (FastAPI, `backend/`). `run.ps1`이 창 없이 띄우고 로그는 `data/backend.log*`.
- 위젯: Electron (`widget/`). 트레이 아이콘, `Ctrl+Shift+K` 보이기/숨기기, 캐릭터 위 💬🏠➖✕ 버튼.
- **이 PC의 도구 경로 (PATH에 없음)**: Python `C:\Users\user\Python314` (프로젝트는 `.venv`),
  Node `C:\Users\user\nodejs`, Claude CLI는 Claude 데스크톱 앱 번들
  (`%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude\claude-code\<버전>\claude.exe`, `run.ps1`이 자동 탐색).
- 새 PC라면: `python -m venv .venv` → `.venv\Scripts\pip install -r requirements.txt` → `cd widget && npm install`.

### 모델(provider) 구성 — 중요

`GET /health`가 보여주는 provider 중 **최소 하나**가 있어야 백엔드가 뜬다 (`backend/config.py`).

| provider | 조건 | 지금 |
|---|---|---|
| `claude_harness` | 로그인된 Claude Code CLI가 PATH에 있음 (API 키 불필요, 사용자의 Claude Pro 한도를 씀) | **이것만 있음** |
| `claude` | `.env`의 `ANTHROPIC_API_KEY` | 없음 |
| `openai` | `.env`의 `OPENAI_API_KEY` | 없음 (사용자가 마지막에 넣기로 함) |
| `gemini` | `.env`의 `GOOGLE_API_KEY` | 없음 (사용자가 마지막에 넣기로 함) |

- **Codex 환경에서 이어받는 경우**: Claude Code CLI가 없으면 `claude_harness`가 안 잡힌다. `.env`에 키를
  하나 이상 넣어야 서버가 뜬다 (`.env.example` 복사). 키는 커밋하지 않는다 (`.env`는 gitignore).
- 하네스만 쓰면 답변 1회에 1~3분, Claude Pro **사용 한도에 실제로 걸린 적 있음** → 테스트를 동시에 여러 개
  돌리지 말 것. 한도에 걸리면 `/chat`이 503 + 이유를 돌려준다.
- 모델 이름은 `.env`의 `ANTHROPIC_MODEL`/`OPENAI_MODEL`/`GEMINI_MODEL`로 바꾼다. 기본값
  (`claude-opus-5`, `gpt-5.1-codex`, `gemini-2.5-pro`) 중 OpenAI·Gemini는 **실제 호출로 확인한 적 없음**
  (키가 없어서 가짜 서버로 요청 형태만 검증). 키를 넣으면 제일 먼저 확인할 것.

## 3. 코드 지도

```
backend/
  main.py            API 전부. /chat 흐름: 개인정보 가림 → 라우터 → 모듈 → (교차검증 ∥ 페르소나 병렬) → 기록
                     접근 제한 미들웨어(guard): 토큰 + Origin 허용 목록 + Host 검사
  config.py          provider 등록, 모듈별 모델 매핑, 연구실 역할 설정 반영, 검토위원은 "다른 회사" 강제
  lab.py             연구실: 연구원(역할) 정의, 역할별 모델·지침 설정, 레벨/별, 대시보드 집계
  tracing.py         요청마다 에이전트·회사 모델·소요 시간 기록(trace), 진행 중 에이전트(LIVE → /progress)
  literature.py      PubMed → OpenAlex 실제 논문 검색. 참고문헌 목록은 코드가 만든다
  privacy.py         주민번호·전화번호·이메일 가림
  research_note.py   연구노트(Markdown) 생성
  instructions.py    KISTO.md(전체 지침) + 역할별 지침 주입
  memory/store.py    JSON 메모리(data/memory_store.json), 로드맵 판정, thread_brief(모듈에 넘기는 맥락)
  orchestrator/      router.py(의도 분류 + 영어 검색어), persona.py(키스토 말투)
  modules/           research_coach(문헌) / analysis_partner(분석) / writing_coach(집필) / verifier(교차검증)
  adapters/          claude / claude_harness / openai / gemini
  sandbox/executor.py 생성 코드 실행 (UTF-8, 백엔드와 같은 인터프리터, PIP_NO_INDEX로 설치 차단)
widget/
  main.js preload.js 창·트레이·IPC. --chat/--lab 시작 옵션. 백엔드 토큰은 data/.kisto_token에서 읽음
  index.html renderer.js style.css chroma.js   투명 캐릭터 위젯 + 대화창 (WebGL 크로마키)
  lab.html lab.js lab.css   연구실 창(장면 + 서랍) + 📊 대시보드 탭
  lab-assets/        연구실 이미지 에셋 자리 (lab.json + 규격 README). 지금은 벡터 그림
    prompts/         에셋 생성 프롬프트 (00 스타일 → 01 배경 → 02~12 가구, 13~14 선택)
      plain/         한 파일 = 이미지 한 장, 복붙용 (도구 지시문은 HOW_TO_ORDER.md)
  character/         idle.mp4(캐릭터 영상, 워터마크는 crop으로 가림), icon.png/ico, character.json
scripts/
  e2e.py             데모 시나리오 4단계를 실제 LLM으로 돌려 점검 (data/e2e_result.json)
  verifier_eval.py   오류 심은 사례로 검토위원 탐지율 측정 (--verifier gemini 등으로 비교)
  build_application_hwpx.py   제출용 신청서 hwpx 생성 (내용은 파일 위쪽 GENERAL/SUMMARY/BODY)
  check_hwpx.ps1     한글 COM으로 hwpx 열기 + PDF 내보내기 (한글이 실제로 여는지 확인)
  ui_snapshot.js     연구실·대시보드 화면 캡처 (Electron)
docs/
  KISTO_AIX_신청서.hwpx   제출용 신청서 (7쪽, 붉은 [ ] 칸 미작성)
  application_draft.md    신청서 마크다운 초안
  demo_scenario.md        시연영상 대본 + 리허설 기록
  judging_review.md       심사위원 관점 약점·대응·예상 Q&A
  demo_rppg.csv           시연용 가상 데이터
  images/                 신청서에 넣은 실제 실행 화면
KISTO.md             키스토 지침 (연구 분야: 신생아·영유아 비침습 연구)
run.cmd / run.ps1    실행기 (-BackendOnly / -Lab / -Chat)
```

### API

`POST /chat`(답변 + `review` 검토 노트 + `trace` + `masked`), `GET /progress/{s}`, `POST /upload`(CSV),
`GET /threads/{s}`(로드맵), `GET /threads/{s}/{i}/detail`, `GET /threads/{s}/{i}/note`(연구노트),
`GET /lab/session/{s}`, `GET /lab/session/{s}/dashboard`, `GET/PUT /lab/roles`, `GET /health`.
브라우저 요청은 `X-Kisto-Token` 헤더(값: `data/.kisto_token`) 필요. 스크립트·curl(Origin 없음)은 그냥 된다.

## 4. 반드시 지킬 설계 결정 (요약 — 원문은 CLAUDE.md)

1. Co-Scientist·Kosmos와 "연동했다"고 쓰지 않는다. "패턴을 참고해 자체 재구현"
2. **교차검증은 다른 회사 모델로.** 사용자가 같은 회사를 골라도 다른 회사가 있으면 그쪽으로 배정
3. "주제별 대화 폴더" UI 금지. 5단계 로드맵만, 단계는 저장된 실데이터로만 판정
4. 사용자에게 내부 구조(모듈·모델 이름)를 보이지 않는다. 예외: 검토 노트, 발표 모드(트레이, 기본 꺼짐)
5. 집필은 대필 금지 — 연구자 해석을 먼저 묻는다
6. 데모 분석 데이터는 **가상 데이터**. 실측처럼 쓰지 않는다
7. 사용자가 준 사업계획서(`Desktop\창업성공패키지_...hwpx`)는 서식 참고용. 개인·회사 정보가 있으니 **저장소에 넣지 않는다**
8. 친구가 만든 Unity 빌드(`Desktop\AIWAIFU_OUTPUT`)에는 OpenAI 키가 박혀 있다. **저장소에 넣지 않는다** (영상만 꺼내 씀)

## 5. 검증된 사실 (2026-09-18, Claude 하네스 단독)

| 항목 | 결과 | 근거 |
|---|---|---|
| 데모 시나리오 4단계 | 전부 통과, 로드맵 0→40→80→100%, **총 297초** (병렬화 전 435초) | `scripts/e2e.py` |
| 단계별 시간 | 주제 탐색 78초 / 분석 77초 / 해석 질문 13초 / 초안 130초 | 〃 |
| 실제 논문 인용 | 초안까지 실제 논문(Villarroel 2019 등)만 인용, 참고문헌 코드 생성 | 〃 |
| 검토위원 정량 평가 | 심어 둔 오류 **10/10 탐지**, 정상 결과 오탐 **0/2** (채점도 Claude, 사례가 쉬워 천장 효과) | `scripts/verifier_eval.py` |
| 이종 모델 교차검증 | **아직 한 번도 안 돌려 봄** (provider가 Claude뿐) | — |
| 신청서 hwpx | 한글 2022에서 열림, 7쪽 | `scripts/check_hwpx.ps1` |
| 보안 | 악성 Origin·위조 Host 403, 위젯(토큰) 200 | 실서버 확인 |

## 6. 남은 일 (우선순위 순)

1. **API 키 넣고 이종 모델 실증** (사용자가 `.env`에 OpenAI·Gemini 키를 넣기로 함 — 키는 채팅으로 받지 말 것)
   - `run.cmd -BackendOnly` 재시작 → `GET /health`에 openai·gemini가 보이는지
   - OpenAI·Gemini 기본 모델 이름이 실제로 호출되는지 확인, 안 되면 `.env`의 `*_MODEL`로 교체
   - `python scripts/e2e.py` → "이종검증" 열이 O인지, 대시보드 "다른 회사 모델 검토 비율"이 올라가는지
   - `python scripts/verifier_eval.py --verifier gemini` / `--verifier openai` → 같은 회사 결과와 비교.
     **사례가 쉬워 천장 효과**가 있으니 더 미묘한 오류 사례(교란 변수, 단위 착오, 자유도 오류 등)를 추가해야 차이가 보인다
   - 결과를 신청서(`scripts/build_application_hwpx.py`의 3-2 표, 3-1 소요 시간)와 `docs/*`에 반영
2. **신청서 붉은 칸 채우기** (사용자 입력 필요): 신청자·참여 인원·개발 기간, before 소요 시간, 링크.
   `build_application_hwpx.py`의 `GENERAL`/`BODY`를 고치고 `--template <사업계획서 hwpx>`로 재생성 →
   `scripts/check_hwpx.ps1`로 열리는지 확인. 원본 **공모전 신청서 양식 파일은 아직 못 받음** — 받으면 목차 맞추기
3. **시연영상** — 대본 `docs/demo_scenario.md` (API 키 넣은 뒤, 발표 모드 켜고, 가상 데이터 명시)
4. **연구실 이미지 에셋** — 사용자가 제작 중. 받으면 `widget/lab-assets/`에 넣고 `lab.json`만 수정 (규격은 그 폴더 README).
   생성 프롬프트는 `widget/lab-assets/prompts/` (시키는 법은 `prompts/HOW_TO_ORDER.md`).
   받은 그림은 `scripts\prep_lab_assets.py`로 다듬고 `scripts\check_lab_assets.py`로 점검한다 (pillow 필요)
5. **GitHub 공개 여부 결정** — 신청서 첨부용. 공개 전 `docs/KISTO_AIX_신청서.hwpx`·스크린샷 포함 여부 확인
6. 발표자료 (10-28용, 1단계 결과 뒤)

## 7. 이번에 실제로 밟은 함정 (재발 방지)

- **한국어 Windows cp949**: subprocess 출력은 반드시 `encoding="utf-8"`. 자식 파이썬에는 `PYTHONIOENCODING=utf-8`.
  안 하면 CLI 출력이 통째로 `None`이 되거나 한글이 깨진다
- **Claude 데스크톱 앱(MSIX) 안에서 실행하면 AppData 쓰기가 가상화된다**: 여기서 설치 프로그램(msi)을 돌리면
  실패한다. 그래서 Python·Node를 zip으로 사용자 폴더에 풀었다. AppData 경로가 앱 안팎에서 다르게 보일 수 있다
- **PowerShell 5.1은 BOM 없는 UTF-8 .ps1의 한글을 깨뜨린다** → `run.ps1`, `check_hwpx.ps1`은 BOM 포함으로 저장
- 이 환경은 `NoDefaultCurrentDirectoryInExePath=1` → `cmd /c ".\run.cmd"`처럼 `.\`를 붙여야 한다
- **hwpx**: 템플릿의 `header.xml`에 있는 `secCnt`(구역 수)가 실제 section 수와 다르면 한글이 못 연다.
  줄바꿈 캐시(`linesegarray`)는 빼도 한글이 다시 계산한다. 새 문단 모양은 `paraProperties itemCnt`도 올려야 한다
- **LLM 여러 층의 프롬프트 상호작용**: 페르소나 레이어가 (a) 초안을 남이 쓴 글로 평가, (b) 질문에 스스로 답,
  (c) 연구 코치 답변을 "사용자가 정리해 준 글"로 착각한 적이 있다 → 초안·질문은 페르소나를 거치지 않고,
  페르소나 프롬프트에 "네가 사용자에게 건넬 답변 초안"임을 명시했다. 빈 맥락을 넘기면 "지난번에"를 지어낸다
- **생성 코드가 가상환경에 pip 설치를 한 적 있다** → `PIP_NO_INDEX`로 차단. 진짜 격리는 아님(컨테이너 필요)
- FastAPI `TestClient`로 테스트할 때는 `base_url="http://127.0.0.1:8420"` (Host 검사 때문에 기본값은 403)
- 백그라운드에서 띄운 Electron 창은 Windows가 앞으로 못 나오게 막는다 → `bringToFront()`(잠깐 최상단)
- 위젯은 투명 창 + 클릭 통과라 `.solid` 클래스가 붙은 요소만 클릭을 받는다. 새 버튼은 `.solid` 안에 둘 것

## 8. 검증 방법 모음

```bat
.venv\Scripts\python.exe scripts\e2e.py                         :: 전체 흐름 (백엔드 먼저)
.venv\Scripts\python.exe scripts\verifier_eval.py [--verifier gemini]
cd widget && node_modules\electron\dist\electron.exe ..\scripts\ui_snapshot.js <세션ID>   :: 연구실 캡처 → data\snapshots
powershell -ExecutionPolicy Bypass -File scripts\check_hwpx.ps1 docs\KISTO_AIX_신청서.hwpx
```

## 9. Git

- 작업 브랜치 `feat/research-lab` (main에 병합 전). 원격 푸시는 아직 안 함.
- 커밋 작성자는 저장소 주인 계정 `kihowork94-korea <kihowork94@gmail.com>`로 해 왔다 (이 PC엔 git 사용자 설정이
  없어서 커밋마다 `git -c user.name=... -c user.email=...`로 지정). 다른 계정으로 할지는 사용자에게 확인.
- 커밋하지 않는 것: `.env`, `data/`의 메모리·로그·업로드·토큰·연구실 설정·스냅샷 (gitignore 참고).
