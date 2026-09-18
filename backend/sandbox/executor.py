import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TIMEOUT_SEC = 15


def run_python(code: str, data_files: list[str] | None = None) -> tuple[bool, str]:
    """생성된 코드를 임시 디렉터리에서 격리 실행한다.

    data_files는 작업 폴더에 복사해 둔다 — 생성 코드는 파일명만으로 읽으면 되고,
    원본(data/uploads)은 건드리지 못한다.

    주의: 이건 로컬 프로토타입 수준의 격리(subprocess + 임시디렉터리)다.
    실제 배포 전에는 컨테이너 등 더 강한 샌드박싱이 필요하다.
    """
    with tempfile.TemporaryDirectory() as tmp:
        for path in data_files or []:
            shutil.copy(path, tmp)
        script = Path(tmp) / "analysis.py"
        script.write_text(code, encoding="utf-8")
        try:
            result = subprocess.run(
                # PATH의 "python"은 없을 수도, 다른 버전일 수도 있다.
                # 백엔드를 돌리는 인터프리터를 그대로 쓴다.
                [sys.executable, str(script)],
                capture_output=True,
                text=True,
                # 생성된 코드가 한국어를 출력해도 깨지지 않도록 UTF-8 고정.
                encoding="utf-8",
                errors="replace",
                timeout=TIMEOUT_SEC,
                cwd=tmp,
                # 자식 파이썬도 UTF-8로 출력하게 맞춘다. 안 그러면 한국어
                # Windows에서 print()한 한글이 깨진 채로 해석 단계에 넘어간다.
                # PIP_NO_INDEX: 생성된 코드가 pip로 패키지를 받아오지 못하게 막는다.
                # (생성 코드가 백엔드 가상환경에 numpy/scipy를 직접 설치한 적이 있다.)
                env={**os.environ, "PYTHONIOENCODING": "utf-8", "PIP_NO_INDEX": "1"},
            )
        except subprocess.TimeoutExpired:
            return False, f"{TIMEOUT_SEC}초 내에 끝나지 않아 중단했습니다."

        if result.returncode != 0:
            return False, result.stderr.strip()
        return True, result.stdout.strip()
