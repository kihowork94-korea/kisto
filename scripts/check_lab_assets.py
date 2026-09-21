# 연구실 이미지 에셋이 규격에 맞는지 점검한다 (넣자마자 확인용).
# 생성 AI가 준 그림은 흰 배경이 같이 붙어 오거나 비율이 어긋나는 일이 잦아서,
# 화면에 띄우기 전에 여기서 먼저 걸러낸다.
#
#   python scripts\check_lab_assets.py
#
# 외부 라이브러리 없이 PNG 헤더(IHDR)만 직접 읽는다 (Pillow 미설치 환경에서도 돌게).
import json
import struct
import sys
from pathlib import Path

# 한국어 Windows 콘솔은 cp949라 한글/기호 출력에서 죽는다 (프로젝트 전반에서 겪은 문제).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "widget" / "lab-assets"

# lab.json의 자리별 기대 비율은 좌표에서 계산한다. 배경만 따로 (960x540 캔버스 전체).
BACKGROUND_RATIO = 960 / 540
TOLERANCE = 0.02  # 비율 오차 2%까지는 눈에 안 띈다


def png_info(path: Path):
    """(너비, 높이, 알파 채널 있음) — PNG가 아니면 None."""
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    width, height, _depth, color = struct.unpack(">IIBB", data[16:26])
    # color type 4(회색+알파), 6(RGBA)만 알파를 가진다. 3(팔레트)은 tRNS 청크로 투명할 수 있다.
    alpha = color in (4, 6) or b"tRNS" in data[:4096]
    return width, height, alpha


def check(name: str, filename: str, ratio: float, need_alpha: bool, out: list):
    before = len(out)
    path = ASSETS / filename
    if not path.exists():
        out.append(f"[없음] {name}: {filename} 파일이 없다")
        return
    info = png_info(path)
    if info is None:
        out.append(f"[형식] {name}: {filename} 은 PNG가 아니다")
        return
    width, height, alpha = info
    got = width / height
    if abs(got - ratio) / ratio > TOLERANCE:
        out.append(
            f"[비율] {name}: {filename} {width}x{height} (비율 {got:.3f}) — "
            f"기대 {ratio:.3f}. 화면에서 찌그러진다"
        )
    if need_alpha and not alpha:
        out.append(f"[투명] {name}: {filename} 에 알파 채널이 없다 — 흰 배경이 같이 보인다")
    if need_alpha and min(width, height) < 200:
        out.append(f"[해상도] {name}: {filename} {width}x{height} — 너무 작아 흐려 보인다")
    if len(out) == before:
        print(f"  OK  {name:20s} {filename:26s} {width}x{height}")


def main() -> int:
    conf_path = ASSETS / "lab.json"
    conf = json.loads(conf_path.read_text(encoding="utf-8"))
    problems: list = []
    used = 0

    background = conf.get("background")
    if background:
        used += 1
        check("background", background, BACKGROUND_RATIO, False, problems)

    for key, spot in (conf.get("spots") or {}).items():
        if not spot or not spot.get("image"):
            continue
        ratio = spot["width"] / spot["height"]
        for field in ("image", "image_active"):
            if spot.get(field):
                used += 1
                check(f"{key}.{field}", spot[field], ratio, True, problems)

    if used == 0:
        print("lab.json에 등록된 이미지가 없다 — 지금은 코드가 그리는 벡터 그림을 쓴다.")
        print("에셋을 만들었다면 widget/lab-assets/prompts/lab.example.json 을 참고해 등록할 것.")
        return 0

    print()
    if problems:
        print("\n".join(problems))
        print(f"\n{len(problems)}건 고칠 것 — 규격은 widget/lab-assets/prompts/README.md")
        return 1
    print(f"이미지 {used}장 모두 규격에 맞는다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
