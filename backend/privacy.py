"""외부 모델로 보내기 전에 개인정보로 보이는 부분을 가린다.

영유아 연구처럼 민감한 데이터를 다룰 때, 연구자가 실수로 붙여넣은 식별정보가
외부 LLM으로 나가지 않게 하는 최소한의 안전장치다 (완전한 비식별화 도구는 아니다).
"""

import re

_PATTERNS = [
    ("주민등록번호", re.compile(r"(?<!\d)\d{6}[-\s]?[1-8]\d{6}(?!\d)")),
    ("전화번호", re.compile(r"(?<!\d)01[016789][-.\s]?\d{3,4}[-.\s]?\d{4}(?!\d)")),
    ("이메일", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
]


def mask(text: str) -> tuple[str, list[str]]:
    """(가린 텍스트, 가린 항목 종류 목록)."""
    found = []
    for label, pattern in _PATTERNS:
        text, count = pattern.subn(f"[{label} 가림]", text)
        if count:
            found.append(label)
    return text, found
