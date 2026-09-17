import subprocess
import tempfile
from pathlib import Path

TIMEOUT_SEC = 15


def run_python(code: str) -> tuple[bool, str]:
    """생성된 코드를 임시 디렉터리에서 격리 실행한다.

    주의: 이건 로컬 프로토타입 수준의 격리(subprocess + 임시디렉터리)다.
    실제 배포 전에는 컨테이너 등 더 강한 샌드박싱이 필요하다.
    """
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "analysis.py"
        script.write_text(code, encoding="utf-8")
        try:
            result = subprocess.run(
                ["python", str(script)],
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SEC,
                cwd=tmp,
            )
        except subprocess.TimeoutExpired:
            return False, f"{TIMEOUT_SEC}초 내에 끝나지 않아 중단했습니다."

        if result.returncode != 0:
            return False, result.stderr.strip()
        return True, result.stdout.strip()
