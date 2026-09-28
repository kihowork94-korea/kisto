"""docs/images/diagrams_source.html의 그림을 하나씩 PNG로 저장한다 (2배 해상도).

    .venv\\Scripts\\python.exe scripts\\render_diagrams.py          # 그림만
    .venv\\Scripts\\python.exe scripts\\render_diagrams.py --doc    # 그림 + 기술 문서 PDF

헤드리스 Edge(없으면 Chrome)로 `diagrams_source.html#<그림 id>`를 그림 크기 그대로 찍는다.
결과: docs/images/diagram_<id>.png  (예: fig-arch → diagram_arch.png)
--doc: 그 그림을 쓰는 docs/tech_doc.html을 docs/KISTO_기술문서.pdf로 인쇄한다.
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "docs" / "images" / "diagrams_source.html"
DOC = ROOT / "docs" / "tech_doc.html"
DOC_PDF = ROOT / "docs" / "KISTO_기술문서.pdf"
OUT = ROOT / "docs" / "images"
BROWSERS = [
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
]


def main() -> None:
    browser = next((b for b in BROWSERS if b.exists()), None)
    if browser is None:
        raise SystemExit("Edge나 Chrome을 찾지 못했습니다.")
    html = SOURCE.read_text(encoding="utf-8")
    figs = re.findall(r'<svg class="fig" id="(fig-[\w-]+)" width="(\d+)" height="(\d+)"', html)
    with tempfile.TemporaryDirectory() as profile:
        for fig_id, width, height in figs:
            out = OUT / f"diagram_{fig_id.removeprefix('fig-')}.png"
            subprocess.run(
                [
                    str(browser), "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    f"--user-data-dir={profile}", "--force-device-scale-factor=2",
                    f"--window-size={width},{height}", f"--screenshot={out}",
                    SOURCE.as_uri() + "#" + fig_id,
                ],
                check=True, capture_output=True,
            )
            print(out.name)
        if "--doc" in sys.argv:
            subprocess.run(
                [
                    str(browser), "--headless=new", "--disable-gpu", f"--user-data-dir={profile}",
                    "--no-pdf-header-footer", f"--print-to-pdf={DOC_PDF}", DOC.as_uri(),
                ],
                check=True, capture_output=True,
            )
            print(DOC_PDF.name)


if __name__ == "__main__":
    main()
