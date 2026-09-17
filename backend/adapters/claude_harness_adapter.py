import json
import subprocess
import tempfile

from .base import ModelAdapter

TIMEOUT_SEC = 60


class ClaudeHarnessAdapter(ModelAdapter):
    """ANTHROPIC_API_KEY 없이, 이미 로그인된 Claude Code CLI를 그대로 백엔드로 쓴다.

    개발자가 평소 쓰는 Claude Code 로그인(OAuth) 세션을 그대로 재사용하므로
    별도 과금키 발급 없이 키스토를 돌릴 수 있다. `claude` 실행파일이 PATH에
    있고 로그인되어 있어야 동작한다.
    """

    name = "claude_harness"

    def __init__(self, model: str | None = None):
        self.model = model  # None이면 CLI에 설정된 기본 모델을 쓴다.

    def generate(self, system_prompt: str, messages: list[dict]) -> str:
        prompt = self._flatten(messages)
        cmd = [
            "claude",
            "-p",
            prompt,
            "--output-format",
            "json",
            "--system-prompt",
            system_prompt,
            # 이 어댑터는 순수 텍스트 생성 용도이므로 Bash/파일수정 등 도구는
            # 전부 막아서 부작용과 권한 프롬프트를 원천 차단한다.
            "--restricted",
            "--permission-prompts",
            "none",
        ]
        if self.model:
            cmd += ["--model", self.model]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SEC,
            # 현재 프로젝트의 CLAUDE.md 등을 자동으로 끌어오지 않도록
            # 무관한 임시 디렉터리에서 실행한다.
            cwd=tempfile.gettempdir(),
        )

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"claude CLI 출력 파싱 실패: {result.stdout or result.stderr}"
            ) from exc

        if data.get("is_error"):
            raise RuntimeError(f"claude CLI 오류: {data.get('result')}")
        return data.get("result", "")

    @staticmethod
    def _flatten(messages: list[dict]) -> str:
        # 하네스는 매 호출을 독립된 1턴으로 다루므로, 대화 맥락은 프롬프트에
        # 직접 펼쳐 넣는다.
        return "\n\n".join(f"[{m['role']}] {m['content']}" for m in messages)
