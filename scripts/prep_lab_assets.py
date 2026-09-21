# 생성 AI가 만들어 준 그림을 연구실 에셋 규격으로 다듬는다.
#
#   python scripts\prep_lab_assets.py <받은_이미지_폴더>
#
# 하는 일 (대부분의 이미지 생성 도구가 투명 PNG도, 정확한 크기도 못 주기 때문에 필요하다):
#   1. 바깥쪽 흰 배경을 투명하게 (가장자리에서 번져 들어가는 방식이라 종이·화이트보드 같은
#      물체 안쪽의 흰색은 남는다)
#   2. 투명 여백을 잘라내고
#   3. lab.example.json에 적힌 규격 크기로 맞춰 widget/lab-assets/ 에 저장한다
#
# 파일 이름을 규격 이름(bookshelf.png, desk_writing.png ...)으로 바꿔 두고 돌리면 된다.
# room.png(배경)는 투명 처리 없이 1920x1080으로만 맞춘다.
import json
import sys
from collections import deque
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):  # 한국어 Windows 콘솔(cp949) 대응
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow가 필요하다:  .venv\\Scripts\\python.exe -m pip install pillow")

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "widget" / "lab-assets"
SPEC = ASSETS / "prompts" / "lab.example.json"

# 배경으로 볼 밝기. 완전한 흰색만 지우면 가장자리에 흰 테두리가 남아서 여유를 둔다.
SOLID = 250   # 이보다 밝으면 확실한 배경
FUZZY = 225   # 이 사이는 반투명으로 부드럽게


def target_sizes() -> dict:
    """규격 파일에서 '파일이름 -> (너비, 높이)'를 만든다 (좌표의 2배가 실제 이미지 크기)."""
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    sizes = {spec["background"]: (1920, 1080)}
    for s in spec["spots"].values():
        for field in ("image", "image_active"):
            if s.get(field):
                sizes[s[field]] = (s["width"] * 2, s["height"] * 2)
    sizes["door_open.png"] = sizes["door.png"]  # 규격에는 없지만 같은 크기로 쓴다
    return sizes


def cut_background(img: Image.Image) -> Image.Image:
    """네 변에서 번져 들어가며 밝은 픽셀만 지운다 (물체 안쪽 흰색은 보존)."""
    img = img.convert("RGBA")
    w, h = img.size
    px = img.load()
    seen = bytearray(w * h)
    queue = deque()

    def bright(x, y):
        r, g, b, _a = px[x, y]
        return min(r, g, b)

    for x in range(w):
        for y in (0, h - 1):
            if bright(x, y) >= FUZZY:
                queue.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if bright(x, y) >= FUZZY:
                queue.append((x, y))

    while queue:
        x, y = queue.popleft()
        i = y * w + x
        if seen[i]:
            continue
        v = bright(x, y)
        if v < FUZZY:
            continue
        seen[i] = 1
        r, g, b, a = px[x, y]
        # SOLID 이상이면 완전 투명, FUZZY~SOLID 사이는 비례해서 반투명 (경계가 거칠지 않게)
        alpha = 0 if v >= SOLID else int(a * (SOLID - v) / (SOLID - FUZZY))
        px[x, y] = (r, g, b, alpha)
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and not seen[ny * w + nx]:
                queue.append((nx, ny))
    return img


def fit(img: Image.Image, size, keep_alpha: bool) -> Image.Image:
    """비율을 유지한 채 규격 크기 캔버스 가운데에 놓는다 (찌그러뜨리지 않는다)."""
    tw, th = size
    if not keep_alpha:
        return img.convert("RGB").resize(size, Image.LANCZOS)
    box = img.getbbox()
    if box:
        img = img.crop(box)
    scale = min(tw / img.width, th / img.height)
    resized = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    canvas.paste(resized, ((tw - resized.width) // 2, (th - resized.height) // 2))
    return canvas


def main() -> int:
    if len(sys.argv) < 2:
        return print(__doc__ or "사용법: python scripts\\prep_lab_assets.py <받은_이미지_폴더>") or 1
    src_dir = Path(sys.argv[1])
    if not src_dir.is_dir():
        return print(f"폴더가 없다: {src_dir}") or 1

    sizes = target_sizes()
    done = 0
    for path in sorted(src_dir.iterdir()):
        if path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
            continue
        name = path.stem + ".png"
        if name not in sizes:
            print(f"  건너뜀  {path.name} — 규격에 없는 이름 (lab.example.json의 파일명으로 바꿀 것)")
            continue
        img = Image.open(path)
        is_background = name == "room.png"
        if not is_background:
            img = cut_background(img)
        out = fit(img, sizes[name], keep_alpha=not is_background)
        out.save(ASSETS / name)
        print(f"  저장  {name:26s} {out.width}x{out.height}  <- {path.name} ({img.width}x{img.height})")
        done += 1

    if not done:
        print("처리한 파일이 없다. 파일 이름을 규격 이름으로 맞췄는지 확인할 것.")
        return 1
    print(f"\n{done}장 처리 완료 → widget/lab-assets/")
    print("다음: lab.json 등록(prompts/lab.example.json 참고) 후 python scripts\\check_lab_assets.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
