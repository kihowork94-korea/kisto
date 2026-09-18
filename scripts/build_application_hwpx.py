"""KIST AIX 성과 공유회 신청서를 한글(hwpx) 파일로 만든다.

    .venv\\Scripts\\python.exe scripts\\build_application_hwpx.py --template <서식으로 쓸 hwpx>

- 목차(틀)는 공모전 신청서 항목(추진배경 및 목적 / AI 활용 내용 / 주요 성과 및 개선 효과 /
  확산 가능성 / 첨부자료)을 따른다.
- 세부 서식(글꼴, 제목 상자, 소제목, ◦/- 개조식, 회색 머리글 표)은 --template 으로 준 hwpx의
  스타일 정의(header.xml)와 문단·표 모양을 그대로 빌려 쓴다. 템플릿의 본문·그림·메타데이터는
  가져오지 않는다.
- 붉은 글씨 [ ... ] 는 제출 전에 직접 채워야 하는 칸이다 (실측 수치, 개인 정보, 링크 등).
- 수치를 채운 뒤 이 파일의 CONTENT만 고치고 다시 실행하면 된다.
"""

import argparse
import re
import struct
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
IMAGES = ROOT / "docs" / "images"

# ── 템플릿에서 빌려 쓰는 스타일 번호 (header.xml의 charPr / paraPr / borderFill id) ──
C_BOX_TITLE, C_BOX_SUB = "42", "56"  # 제목 상자: HY울릉도M 16pt / 14pt
C_SQUARE, C_SQUARE_TEXT = "50", "42"  # □ 머리: 휴먼명조 / HY울릉도M
C_SUBHEAD = "82"  # 1-1. 소제목: 맑은 고딕 16pt 굵게
C_BULLET, C_DASH = "5", "7"  # ◦ 12pt 굵게 / - 12pt
C_NOTE, C_RED = "40", "85"  # ※ 안내 10pt / 붉은 12pt (본문 속 채워야 할 칸)
C_TH, C_TD, C_TD_RED = "44", "1", "88"  # 표 머리글 11pt 굵게 / 본문 10pt / 붉은 굵은 10pt
P_TITLE, P_NOTE, P_SQUARE, P_SUBHEAD, P_BODY = "20", "17", "3", "14", "28"
P_CELL_CENTER, P_CELL_LEFT, P_IMAGE, P_SPACER = "26", "3", "22", "5"
B_TH, B_TD, B_TABLE = "24", "23", "5"  # 회색 머리글 칸 / 본문 칸 / 표 테두리
B_BOX_L, B_BOX_R = "12", "13"  # 제목 상자 왼쪽·오른쪽 칸
# 제목이 쪽 맨 아래에 홀로 남지 않도록 "다음 문단과 함께" 속성을 켠 문단 모양을 새로 만든다
# (템플릿 문단 모양을 복사해 번호만 새로 붙인다 — build()의 add_keep_with_next 참고).
KEEP_WITH_NEXT = {P_SUBHEAD: None, "21": None, P_SPACER: None}  # 원래 번호 → 새 번호
TEXT_WIDTH = 48188  # 본문 폭 (HWPUNIT)

# ── 문서 내용 ─────────────────────────────────────────────────────────────
# 문자열 안의 [[...]] 은 붉은 글씨(채워야 할 칸)로 들어간다.
TITLE = "AIX 성과 공유회 신청서"
NOTE = "붉은 글씨 [ ] 는 제출 전 작성 · 시연 데이터는 가상 데이터 · 첨부: GitHub 저장소, 시연영상"

GENERAL = [
    ("과제명", "키스토(KISTO) — 바탕화면에 사는 AI 연구 동료: 멀티에이전트 연구 파이프라인과 이종 모델 교차검증"),
    ("신청자", "[[ 소속 / 직급 / 성명 ]]"),
    ("참여 인원", "[[ 명 ]]"),
    ("개발 기간", "[[ 2026.  ~ 2026.10 ]] (현재 동작하는 프로토타입 완성)"),
    ("활용 AI", "Claude(Anthropic) · GPT(OpenAI) · Gemini(Google) 멀티 모델 구조, PubMed·OpenAlex 문헌 검색"),
    ("첨부자료", "GitHub 저장소 [[ 링크 ]] · 시연영상 [[ 링크 ]]"),
]

SUMMARY = [
    ("과제 소개", [
        "신입 연구자가 바탕화면 캐릭터 '키스토' 한 명과 대화하면, 그 뒤에서 문헌·분석·검토·집필을 맡은 "
        "AI 연구원들이 협업하는 '나만의 연구실'",
    ]),
    ("핵심 차별성", [
        "① 결과를 만든 모델과 다른 회사 모델이 검토하는 이종 모델 교차검증",
        "② 실제 검색된 논문만 인용 (참고문헌 목록은 모델이 아니라 코드가 생성)",
        "③ 대필 금지 — 초안 전에 연구자의 해석을 먼저 물음",
        "④ 게임처럼 쌓이는 연구실·로드맵·대시보드, 연구노트 자동 정리",
    ]),
    ("활용 대상", ["KIST 신입·학생 연구원, 새로운 연구 분야에 진입하는 연구자"]),
    ("주요 성과", [
        "주제 탐색 → 데이터 분석 → 논문 서론 초안까지 전 과정 자동 수행 (약 5분, 데모 시나리오)",
        "통계·해석 오류를 심어 둔 분석 결과 10건 중 10건 탐지 (검토 에이전트 정량 평가)",
    ]),
]

# 본문: ("box", 번호·제목, 영문) / ("h", 소제목) / ("b", ◦ 문장) / ("d", - 문장)
#       ("table", 열 너비 비율, [머리글, 행...]) / ("img", 파일, 캡션[, 최대 폭]) / ("note", ※ 문장) / ("gap",)
BODY = [
    ("box", "1. 추진배경 및 목적", "(Background)"),
    ("h", "1-1. 추진 배경"),
    ("b", "신입 연구자가 가장 오래 막히는 단계는 연구 주제 설정과 논문 작성"),
    ("d", "코딩 역량은 있으나 도메인 배경지식이 부족해 선행 연구 파악과 가설 수립에 많은 시간이 듦"),
    ("d", "분석 결과의 해석과 서론 작성은 선배 연구자의 피드백에 기대야 함"),
    ("b", "기존 AI 챗봇의 한계"),
    ("d", "질문 단위로 파편화되어 주제 → 가설 → 분석 → 논문으로 이어지는 연구 맥락을 이어가지 못함"),
    ("d", "답을 만든 모델이 스스로 검증해 같은 편향을 공유하고, 존재하지 않는 논문을 인용하기도 함"),
    ("d", "요청하면 바로 대필 → 연구윤리 문제와 학습 기회 상실"),
    ("h", "1-2. 추진 목적"),
    ("b", "'도구 여러 개'가 아니라 '물어볼 수 있는 선배 한 명' 같은 연구 동료 에이전트 개발"),
    ("d", "연구 초기 단계(주제 탐색·가설·분석·초안)의 소요 시간 단축"),
    ("d", "다른 회사 모델의 교차검증으로 과잉해석·통계 오류를 미리 걸러내는 신뢰성 확보"),
    ("d", "연구자의 해석을 먼저 묻는 방식으로 연구윤리 준수와 학습 효과를 함께 달성"),
    ("gap",),
    ("box", "2. AI 활용 내용", "(AI Solution)"),
    ("h", "2-1. 시스템 구성 — '나만의 연구실'"),
    ("b", "연구자는 책임연구원(PI), 키스토는 연구실 매니저, AI 에이전트는 자리가 있는 연구원"),
    ("table", [22, 16, 62], [
        ["구성원", "자리", "하는 일"],
        ["연구실 매니저 키스토", "바탕화면 캐릭터", "연구자와 대화하고 요청을 알맞은 연구원에게 배분, 모든 답변을 한 사람의 말투로 통일"],
        ["문헌 연구원", "서재", "PubMed·OpenAlex에서 실제 논문 검색, 초록 근거로 선행 연구 요약·후보 가설 비교"],
        ["분석 연구원", "실험대", "분석 코드 작성 → 격리 환경에서 실행 → 오류 자동 수정 → 가설과 연결한 해석"],
        ["외부 검토위원", "검토 보드", "결과를 만든 연구원과 다른 회사 모델이 과잉해석·통계 오류·인용 불일치를 지적"],
        ["집필 연구원", "노트북", "연구자의 해석을 먼저 묻고, 그 해석과 실제 문헌만으로 논문 초안 작성"],
    ]),
    ("d", "Google AI Co-Scientist, FutureHouse Kosmos 등의 멀티에이전트 연구 패턴을 참고해 자체 재구현"),
    ("d", "(해당 서비스들은 공개 API가 없어 연동이 아니라 구조를 차용함)"),
    ("img", "widget_chat.png", "▲ 바탕화면 위젯 — 대화창 위쪽의 연구 로드맵이 실제 기록에 따라 채워지고, 단계 클리어 시 연출", 24000),
    ("h", "2-2. 핵심 차별점"),
    ("b", "① 이종 모델 교차검증"),
    ("d", "같은 모델이 자기 결과를 검증하면 같은 편향을 공유 → 결과를 만든 모델과 다른 회사 모델만 검토에 배정"),
    ("d", "Google Co-Scientist도 같은 모델 계열(Gemini) 안에서 검증 — 키스토의 구조적 차별점"),
    ("d", "검토 결과는 답변에 섞지 않고 '검토 노트'로 분리해 보여줌"),
    ("b", "② 환각 없는 문헌 근거"),
    ("d", "실제 검색된 논문에만 번호를 매겨 인용하게 하고, 참고문헌 목록은 검색 결과로 코드가 생성"),
    ("d", "→ 존재하지 않는 논문 인용이 구조적으로 불가능, 검토위원이 인용 문장과 초록을 대조"),
    ("b", "③ 대필하지 않는 집필"),
    ("d", "\"초안 써줘\" 요청에 먼저 연구자의 해석을 묻고, 그 해석을 반영해 초안 작성"),
    ("b", "④ 게임처럼 쌓이는 연구실과 대시보드"),
    ("d", "주제 잡기 → 가설 → 분석 → 교차검증 → 초안 5단계 로드맵, 저장된 실제 기록으로만 단계 판정"),
    ("d", "찾은 논문만큼 책장이 차고 분석 횟수만큼 시험관이 차며, 다음 할 일에 퀘스트 표시"),
    ("d", "대시보드: 전체 진행, 다른 회사 모델 검토 비율, 연구원별 업무·작업 시간, 활동 타임라인"),
    ("img", "lab_room.png", "▲ 키스토 연구실 — 자리를 누르면 그 연구원이 한 일(논문·분석·검토·초안)을 확인"),
    ("img", "lab_dashboard.png", "▲ 연구실 대시보드 — 전체 프로젝트 진행과 교차검증 현황을 한 화면에"),
    ("h", "2-3. 기술 구성"),
    ("table", [22, 78], [
        ["구분", "내용"],
        ["백엔드", "Python FastAPI, 모델 어댑터 4종(Claude API·Claude Code·OpenAI·Gemini), 키 없는 모델 자동 대체"],
        ["문헌 검색", "PubMed E-utilities, OpenAlex API"],
        ["분석 실행", "격리된 Python 실행 환경(numpy·scipy·pandas), 생성 코드의 패키지 설치 차단"],
        ["위젯·연구실", "Electron, WebGL 실시간 배경 투명 처리, 투명 영역 클릭 통과"],
        ["보안", "개인정보(주민번호·전화번호·이메일) 자동 가림, 로컬 서버 접근 토큰·출처 검사"],
        ["맞춤 설정", "지침 파일(KISTO.md)로 연구 분야·말투 지정, 연구원별 담당 모델·지침 부여"],
    ]),
    ("gap",),
    ("box", "3. 주요 성과 및 개선 효과", "(Result)"),
    ("h", "3-1. 동작 검증"),
    ("b", "데모 시나리오: 신생아·영유아 비침습 연구 (카메라 기반 비접촉 심박 측정 vs 심전도)"),
    ("table", [16, 64, 20], [
        ["단계", "키스토가 한 일", "소요 시간"],
        ["① 주제 탐색", "실제 논문 6편 검색(PubMed), 초록 근거로 선행 연구 요약·후보 가설 비교, 연구 동기와 IRB·보호자 동의 확인", "78초"],
        ["② 데이터 분석", "분석 코드 작성·실행, MAE·상관계수·Bland-Altman 계산, 가설과 연결한 해석", "77초"],
        ["③ 초안 요청", "바로 쓰지 않고 연구자의 해석을 묻는 질문", "13초"],
        ["④ 초안 작성", "연구자 해석을 반영한 서론 초안, 실제 논문 인용 + 참고문헌 자동 첨부", "130초"],
        ["합계", "주제 탐색부터 논문 서론 초안까지 (로드맵 0 → 40 → 80 → 100%)", "297초 (약 5분)"],
    ]),
    ("note", "분석 데이터는 시연용 가상 데이터 · API 키 없이 Claude 단독 구성으로 측정 (2026-09-18)"),
    ("h", "3-2. 교차검증 효과 (정량 평가)"),
    ("b", "통계·해석 오류를 하나씩 심어 둔 분석 결과 10건 + 문제없는 결과 2건으로 검토위원 평가"),
    ("table", [26, 74], [
        ["항목", "결과"],
        ["심어 둔 오류 탐지", "10건 중 10건 — 상관≠일치, 과잉 일반화, 대응표본 오류, 다중비교 미보정, 인과 오해석, "
                         "외삽, p값≠효과크기, 선택 편향, 기준 없는 판정, 초록에 없는 인용"],
        ["문제없는 결과 오탐", "2건 중 0건"],
        ["다른 회사 모델 검토", "[[ API 키 연동 후 측정 ]]"],
    ]),
    ("d", "한계: 같은 회사 모델이 채점 → 이종 모델 비교와 난이도 높은 사례를 추가해 재평가 예정"),
    ("h", "3-3. 시간 단축 (before / after)"),
    ("table", [34, 22, 22, 22], [
        ["작업", "기존 방식", "키스토", "비고"],
        ["연구 주제 후보 도출 + 선행 연구 파악", "[[ ]]", "약 1분 20초", ""],
        ["분석 코드 작성·디버깅·결과 해석", "[[ ]]", "약 1분 20초", ""],
        ["논문 서론 초안 작성", "[[ ]]", "약 2분 20초", "해석 질문 포함"],
        ["결과 검토 (통계·해석 오류 점검)", "[[ ]]", "자동", "교차검증"],
    ]),
    ("d", "측정 방법: 같은 연구 질문으로 기존 방식(검색 + 개별 AI 챗 + 직접 코딩)과 키스토를 각각 진행"),
    ("h", "3-4. 정성적 효과"),
    ("b", "대필 대신 해석을 묻는 방식"),
    ("d", "연구자가 결과를 스스로 해석하는 훈련, 연구윤리 리스크 감소"),
    ("b", "검토 노트"),
    ("d", "신입이 놓치기 쉬운 통계적 함정(표본 크기, 검정 가정, 인과 해석)을 자연스럽게 학습"),
    ("b", "연구노트 자동 정리"),
    ("d", "코드·결과·검토·해석·초안·참고문헌·서명란을 담은 연구노트 초안 → 국가 R&D 연구노트 작성 부담 경감"),
    ("b", "연구실·대시보드"),
    ("d", "여러 주제를 병행할 때 각 주제가 어느 단계에서 멈춰 있는지 한눈에 관리"),
    ("gap",),
    ("box", "4. 확산 가능성", "(Scale-up)"),
    ("h", "4-1. 적용 범위"),
    ("b", "분야 무관 — 연구 분야는 지침 파일(KISTO.md) 하나로 지정"),
    ("d", "재료·바이오·의공학 등 KIST 전 분야에 코드 수정 없이 적용"),
    ("d", "논문 검색도 PubMed(생의학)와 OpenAlex(전 분야)를 함께 사용"),
    ("h", "4-2. 도입 용이성"),
    ("b", "개인 PC에서 바탕화면 아이콘 하나로 실행, 별도 서버 불필요"),
    ("b", "연구원별 담당 모델을 설정으로 교체 → 보안 요구가 높은 과제는 사내·로컬 LLM으로 대체 가능한 구조"),
    ("b", "연구 데이터 보호 — 개인정보 자동 가림, 외부 웹사이트의 로컬 서버 접근 차단"),
    ("h", "4-3. 향후 계획"),
    ("b", "신입 연구원 온보딩 도구 — 선배가 매번 설명하던 연구 과정을 로드맵으로 구조화"),
    ("b", "KIST 사내 시스템 연동, 연구실 단위 공유 메모리, 컨테이너 기반 분석 격리 강화"),
    ("gap",),
    ("box", "5. 첨부자료", "(Appendix)"),
    ("b", "GitHub 저장소: [[ 링크 ]]"),
    ("b", "시연영상: [[ 링크 ]] — 위젯 대화 → 연구실 → 대시보드 → 연구노트 내보내기 (약 3분 30초)"),
]


# ── XML 조각 ──────────────────────────────────────────────────────────────
def runs(text: str, char: str, red: str = C_RED) -> str:
    """[[...]] 부분만 붉은 글씨로 나눠 run을 만든다."""
    out = []
    for i, part in enumerate(re.split(r"\[\[(.*?)\]\]", text)):
        if part:
            shown = f"[{part}]" if i % 2 else part
            out.append(f'<hp:run charPrIDRef="{red if i % 2 else char}"><hp:t>{escape(shown)}</hp:t></hp:run>')
    return "".join(out) or f'<hp:run charPrIDRef="{char}"/>'


def para(inner: str, para_pr: str) -> str:
    return (f'<hp:p id="2147483648" paraPrIDRef="{para_pr}" styleIDRef="0" pageBreak="0" '
            f'columnBreak="0" merged="0">{inner}</hp:p>')


class Builder:
    def __init__(self):
        self.next_id = 1900000000
        self.images: list[tuple[str, bytes]] = []  # (BinData 파일명, 내용)

    def uid(self) -> int:
        self.next_id += 1
        return self.next_id

    def cell(self, row: int, col: int, width: int, lines: list[str], header: bool, center: bool) -> str:
        char = C_TH if header else C_TD
        pr = P_CELL_CENTER if header or center else P_CELL_LEFT
        body = "".join(para(runs(line, char, C_TD_RED), pr) for line in lines)
        return (f'<hp:tc name="" header="{1 if header else 0}" hasMargin="0" protect="0" editable="0" dirty="0" '
                f'borderFillIDRef="{B_TH if header else B_TD}"><hp:subList id="" textDirection="HORIZONTAL" '
                f'lineWrap="BREAK" vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" textWidth="0" '
                f'textHeight="0" hasTextRef="0" hasNumRef="0">{body}</hp:subList>'
                f'<hp:cellAddr colAddr="{col}" rowAddr="{row}"/><hp:cellSpan colSpan="1" rowSpan="1"/>'
                f'<hp:cellSz width="{width}" height="1800"/>'
                f'<hp:cellMargin left="425" right="425" top="200" bottom="200"/></hp:tc>')

    def table(self, ratios: list[int], rows: list[list], header_row: bool = True, header_col: bool = False) -> str:
        total = TEXT_WIDTH - 400
        widths = [round(total * r / sum(ratios)) for r in ratios]
        # 열 안의 값이 모두 짧으면 그 열만 가운데 정렬 (칸마다 정하면 한 열 안에서 들쭉날쭉해진다).
        # 왼쪽이 항목명인 표(일반현황 등)의 값은 늘 왼쪽 정렬.
        body_rows = rows[1:] if header_row else rows
        centered = [not header_col and all(len(str(r[c])) <= 16 for r in body_rows) for c in range(len(ratios))]
        trs = []
        for r, row in enumerate(rows):
            cells = []
            for c, value in enumerate(row):
                lines = value if isinstance(value, list) else [value]
                header = (header_row and r == 0) or (header_col and c == 0)
                center = header or centered[c]
                cells.append(self.cell(r, c, widths[c], lines, header, center))
            trs.append("<hp:tr>" + "".join(cells) + "</hp:tr>")
        tbl = (f'<hp:tbl id="{self.uid()}" zOrder="1" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" '
               f'textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="CELL" repeatHeader="1" '
               f'rowCnt="{len(rows)}" colCnt="{len(ratios)}" cellSpacing="0" borderFillIDRef="{B_TABLE}" noAdjust="0">'
               f'<hp:sz width="{sum(widths)}" widthRelTo="ABSOLUTE" height="{1800 * len(rows)}" heightRelTo="ABSOLUTE" protect="0"/>'
               f'<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" '
               f'vertRelTo="PARA" horzRelTo="PARA" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
               f'<hp:outMargin left="141" right="141" top="141" bottom="141"/>'
               f'<hp:inMargin left="140" right="140" top="140" bottom="140"/>{"".join(trs)}</hp:tbl>')
        return para(f'<hp:run charPrIDRef="{C_TD}">{tbl}<hp:t/></hp:run>', P_SPACER)

    def box(self, title: str, sub: str) -> str:
        """1. 추진배경 및 목적 (Background) — 템플릿의 색 띠 제목 상자."""
        left = max(17829, 1650 * len(title) + 950 * len(sub))
        right = 2261
        cells = (
            f'<hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" dirty="0" borderFillIDRef="{B_BOX_L}">'
            f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" linkListIDRef="0" '
            f'linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
            + para(f'<hp:run charPrIDRef="{C_BOX_TITLE}"><hp:t> {escape(title)} </hp:t></hp:run>'
                   f'<hp:run charPrIDRef="{C_BOX_SUB}"><hp:t>{escape(sub)}</hp:t></hp:run>', P_TITLE)
            + f'</hp:subList><hp:cellAddr colAddr="0" rowAddr="0"/><hp:cellSpan colSpan="1" rowSpan="1"/>'
            f'<hp:cellSz width="{left}" height="3005"/><hp:cellMargin left="141" right="141" top="141" bottom="141"/></hp:tc>'
            f'<hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" dirty="0" borderFillIDRef="{B_BOX_R}">'
            f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" linkListIDRef="0" '
            f'linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
            + para('<hp:run charPrIDRef="28"/>', "1")
            + f'</hp:subList><hp:cellAddr colAddr="1" rowAddr="0"/><hp:cellSpan colSpan="1" rowSpan="1"/>'
            f'<hp:cellSz width="{right}" height="3005"/><hp:cellMargin left="141" right="141" top="141" bottom="141"/></hp:tc>'
        )
        tbl = (f'<hp:tbl id="{self.uid()}" zOrder="3" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" '
               f'textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="NONE" repeatHeader="1" rowCnt="1" '
               f'colCnt="2" cellSpacing="0" borderFillIDRef="{B_TABLE}" noAdjust="0">'
               f'<hp:sz width="{left + right}" widthRelTo="ABSOLUTE" height="3005" heightRelTo="ABSOLUTE" protect="0"/>'
               f'<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" '
               f'vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
               f'<hp:outMargin left="140" right="140" top="140" bottom="140"/>'
               f'<hp:inMargin left="140" right="140" top="140" bottom="140"/><hp:tr>{cells}</hp:tr></hp:tbl>')
        return para(f'<hp:run charPrIDRef="{C_SQUARE}">{tbl}<hp:t/></hp:run>', KEEP_WITH_NEXT["21"])

    def image(self, filename: str, caption: str, max_width: int = 44000) -> str:
        """max_width는 HWPUNIT (본문 폭 48188). 세로로 긴 화면은 작게 넣어야 한 쪽에 들어간다."""
        data = (IMAGES / filename).read_bytes()
        px_w, px_h = struct.unpack(">II", data[16:24])  # PNG IHDR의 가로·세로
        org_w, org_h = px_w * 75, px_h * 75  # 96dpi 픽셀 → HWPUNIT
        cur_w = min(max_width, org_w)
        cur_h = round(org_h * cur_w / org_w)
        index = len(self.images) + 1
        self.images.append((f"image{index}.png", data))
        s = cur_w / org_w
        pic = (f'<hp:pic id="{self.uid()}" zOrder="{10 + index}" numberingType="PICTURE" textWrap="TOP_AND_BOTTOM" '
               f'textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" href="" groupLevel="0" instid="{self.uid()}" reverse="0">'
               f'<hp:offset x="0" y="0"/><hp:orgSz width="{org_w}" height="{org_h}"/>'
               f'<hp:curSz width="{cur_w}" height="{cur_h}"/><hp:flip horizontal="0" vertical="0"/>'
               f'<hp:rotationInfo angle="0" centerX="{cur_w // 2}" centerY="{cur_h // 2}" rotateimage="1"/>'
               f'<hp:renderingInfo><hc:transMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
               f'<hc:scaMatrix e1="{s:.6f}" e2="0" e3="0" e4="0" e5="{s:.6f}" e6="0"/>'
               f'<hc:rotMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/></hp:renderingInfo>'
               f'<hc:img binaryItemIDRef="image{index}" bright="0" contrast="0" effect="REAL_PIC" alpha="0"/>'
               f'<hp:imgRect><hc:pt0 x="0" y="0"/><hc:pt1 x="{org_w}" y="0"/><hc:pt2 x="{org_w}" y="{org_h}"/>'
               f'<hc:pt3 x="0" y="{org_h}"/></hp:imgRect><hp:imgClip left="0" right="{org_w}" top="0" bottom="{org_h}"/>'
               f'<hp:inMargin left="0" right="0" top="0" bottom="0"/><hp:imgDim dimwidth="{org_w}" dimheight="{org_h}"/>'
               f'<hp:effects/><hp:sz width="{cur_w}" widthRelTo="ABSOLUTE" height="{cur_h}" heightRelTo="ABSOLUTE" protect="0"/>'
               f'<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" '
               f'vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" horzAlign="CENTER" vertOffset="0" horzOffset="0"/>'
               f'<hp:outMargin left="0" right="0" top="0" bottom="0"/><hp:shapeComment>그림입니다.</hp:shapeComment></hp:pic>')
        return (para(f'<hp:run charPrIDRef="{C_TD}">{pic}<hp:t/></hp:run>', P_IMAGE)
                + para(runs(caption, C_TD), P_IMAGE)
                + self.spacer())

    @staticmethod
    def spacer(keep: bool = False) -> str:
        return para('<hp:run charPrIDRef="48"/>', KEEP_WITH_NEXT[P_SPACER] if keep else P_SPACER)

    def body(self) -> str:
        out = []
        for item in BODY:
            kind = item[0]
            if kind == "box":
                out += [self.box(item[1], item[2]), self.spacer(keep=True)]
            elif kind == "h":
                out.append(para(runs(" " + item[1], C_SUBHEAD), KEEP_WITH_NEXT[P_SUBHEAD]))
            elif kind == "b":
                out.append(para(runs("◦ " + item[1], C_BULLET), P_BODY))
            elif kind == "d":
                out.append(para(runs("   - " + item[1], C_DASH), P_BODY))
            elif kind == "note":
                out += [para(runs("  ※ " + item[1], C_NOTE), P_NOTE), self.spacer()]
            elif kind == "table":
                out += [self.table(item[1], item[2]), self.spacer()]
            elif kind == "img":
                out.append(self.image(item[1], item[2], *item[3:]))
            elif kind == "gap":
                out.append(self.spacer())
        return "".join(out)


def add_keep_with_next(header: str) -> str:
    """KEEP_WITH_NEXT에 적힌 문단 모양을 복사해 '다음 문단과 함께'를 켠 새 모양으로 추가한다."""
    next_id = max(int(i) for i in re.findall(r'<hh:paraPr id="(\d+)"', header)) + 1
    added = []
    for original in KEEP_WITH_NEXT:
        block = re.search(rf'<hh:paraPr id="{original}".*?</hh:paraPr>', header, re.S).group()
        block = block.replace(f'<hh:paraPr id="{original}"', f'<hh:paraPr id="{next_id}"', 1)
        added.append(block.replace('keepWithNext="0"', 'keepWithNext="1"'))
        KEEP_WITH_NEXT[original] = str(next_id)
        next_id += 1
    count = int(re.search(r'<hh:paraProperties itemCnt="(\d+)">', header).group(1))
    header = header.replace(f'<hh:paraProperties itemCnt="{count}">',
                            f'<hh:paraProperties itemCnt="{count + len(added)}">', 1)
    return header.replace('</hh:paraProperties>', ''.join(added) + '</hh:paraProperties>', 1)


def build(template: Path, output: Path) -> None:
    src = zipfile.ZipFile(template)
    # header.xml은 구역(section) 수를 secCnt로 따로 적어 둔다. 템플릿은 3구역이라 그대로 두면
    # 한글이 없는 section1·2를 찾다가 파일 열기에 실패한다.
    header = re.sub(r'secCnt="\d+"', 'secCnt="1"', src.read("Contents/header.xml").decode("utf-8"), count=1)
    header = add_keep_with_next(header)
    section = src.read("Contents/section0.xml").decode("utf-8")
    first_p = section.index("<hp:p ")
    prefix = section[:first_p]  # XML 선언 + <hs:sec ...> (네임스페이스)

    # 첫 문단: 쪽 설정(secPr, 쪽 번호)은 템플릿 그대로, 제목 상자의 글자만 바꾼다.
    depth, end = 0, None
    for m in re.finditer(r"<hp:p[ >]|</hp:p>", section[first_p:]):
        depth += 1 if m.group().startswith("<hp:p") else -1
        if depth == 0:
            end = first_p + m.end()
            break
    first = section[first_p:end]
    first = re.sub(r'<hp:run charPrIDRef="41"><hp:t>[^<]*</hp:t></hp:run>'
                   r'<hp:run charPrIDRef="42"><hp:t>[^<]*</hp:t></hp:run>',
                   f'<hp:run charPrIDRef="42"><hp:t> {escape(TITLE)}</hp:t></hp:run>', first)
    first = re.sub(r'<hp:sz width="22354"', '<hp:sz width="31354"', first)
    first = re.sub(r'<hp:cellSz width="20093"', '<hp:cellSz width="29093"', first)
    first = re.sub(r"<hp:linesegarray>.*?</hp:linesegarray>", "", first, flags=re.S)

    b = Builder()
    general = b.table([22, 78], [[k, v] for k, v in GENERAL], header_row=False, header_col=True)
    summary = b.table([22, 78], [[k, v] for k, v in SUMMARY], header_row=False, header_col=True)
    parts = [
        first,
        para(runs("  ※ " + NOTE, C_NOTE), P_NOTE),
        b.spacer(),
        para(f'<hp:run charPrIDRef="{C_SQUARE}"><hp:t>□ </hp:t></hp:run>'
             f'<hp:run charPrIDRef="{C_SQUARE_TEXT}"><hp:t>일반현황</hp:t></hp:run>', P_SQUARE),
        general,
        b.spacer(),
        para(f'<hp:run charPrIDRef="{C_SQUARE}"><hp:t>□ </hp:t></hp:run>'
             f'<hp:run charPrIDRef="{C_SQUARE_TEXT}"><hp:t>과제 개요(요약)</hp:t></hp:run>', P_SQUARE),
        summary,
        b.spacer(),
        b.body(),
    ]
    new_section = prefix + "".join(parts) + "</hs:sec>"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    hpf = src.read("Contents/content.hpf").decode("utf-8")
    head = hpf[: hpf.index("<opf:metadata>")]
    # 템플릿의 메타데이터(작성자, 보안 추적 ID 등)는 가져오지 않는다.
    metadata = (f'<opf:metadata><opf:title>키스토(KISTO) AIX 성과 공유회 신청서</opf:title>'
                f'<opf:language>ko</opf:language><opf:meta name="creator" content="text"/>'
                f'<opf:meta name="subject" content="text"/><opf:meta name="description" content="text"/>'
                f'<opf:meta name="lastsaveby" content="text"/><opf:meta name="CreatedDate" content="text">{now}</opf:meta>'
                f'<opf:meta name="ModifiedDate" content="text">{now}</opf:meta><opf:meta name="date" content="text"/>'
                f'<opf:meta name="keyword" content="text"/></opf:metadata>')
    items = ['<opf:item id="header" href="Contents/header.xml" media-type="application/xml"/>']
    items += [f'<opf:item id="{Path(n).stem}" href="BinData/{n}" media-type="image/png" isEmbeded="1"/>'
              for n, _ in b.images]
    items += ['<opf:item id="section0" href="Contents/section0.xml" media-type="application/xml"/>',
              '<opf:item id="settings" href="settings.xml" media-type="application/xml"/>']
    content_hpf = (head + metadata + "<opf:manifest>" + "".join(items) + "</opf:manifest>"
                   '<opf:spine><opf:itemref idref="header" linear="yes"/>'
                   '<opf:itemref idref="section0" linear="yes"/></opf:spine></opf:package>')

    rdf = src.read("META-INF/container.rdf").decode("utf-8")
    for n in (1, 2):  # 템플릿의 section1·2 참조 제거
        rdf = re.sub(rf'<rdf:Description rdf:about=""><ns0:hasPart [^>]*rdf:resource="Contents/section{n}.xml"/>'
                     rf'</rdf:Description><rdf:Description rdf:about="Contents/section{n}.xml">.*?</rdf:Description>',
                     "", rdf, flags=re.S)
    settings = re.sub(r'<ha:CaretPosition [^>]*/>', '<ha:CaretPosition listIDRef="0" paraIDRef="0" pos="0"/>',
                      src.read("settings.xml").decode("utf-8"))
    preview_text = "\r\n".join([TITLE, NOTE] + [f"{k}: {re.sub(r'[\\[\\]]', '', v)}" for k, v in GENERAL])

    # 미리보기 그림은 연구실 화면으로 대신한다 (한글에서 저장하면 첫 쪽 모양으로 다시 만들어진다).
    thumb = (IMAGES / "lab_room.png").read_bytes()

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        # 순서는 한글이 저장하는 순서를 따른다. mimetype은 맨 앞, 압축하지 않는다 (OCF 규칙).
        z.writestr(zipfile.ZipInfo("mimetype"), src.read("mimetype"), compress_type=zipfile.ZIP_STORED)
        z.writestr("version.xml", src.read("version.xml"))
        z.writestr("Contents/header.xml", header.encode("utf-8"))
        for name, data in b.images:
            z.writestr(f"BinData/{name}", data)
        z.writestr("Contents/section0.xml", new_section.encode("utf-8"))
        z.writestr("Preview/PrvText.txt", preview_text.encode("utf-8"))
        z.writestr("settings.xml", settings.encode("utf-8"))
        z.writestr("Preview/PrvImage.png", thumb)
        z.writestr("META-INF/container.rdf", rdf.encode("utf-8"))
        z.writestr("Contents/content.hpf", content_hpf.encode("utf-8"))
        z.writestr("META-INF/container.xml", src.read("META-INF/container.xml"))
        z.writestr("META-INF/manifest.xml", src.read("META-INF/manifest.xml"))
    print(f"작성 완료: {output} (그림 {len(b.images)}개)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", required=True, type=Path, help="서식을 빌려 올 hwpx 파일")
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "KISTO_AIX_신청서.hwpx")
    args = parser.parse_args()
    build(args.template, args.out)
