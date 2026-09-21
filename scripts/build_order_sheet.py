# plain/*.txt 프롬프트들을 "한 파일만 올리면 끝까지 진행되는" 주문서 하나로 합친다.
#
#   python scripts\build_order_sheet.py            # 남은 선택 항목 10장 (아이콘+초상)
#   python scripts\build_order_sheet.py room       # 방 가구 12장 (이미 만들었다면 필요 없다)
#
# 왜 필요한가: 프롬프트 폴더를 통째로 올리면 이미지 도구가 한 장만 만들고 끝낸다.
# 파일 하나에 진행 규칙 + 단계별 프롬프트를 순서대로 박아 두면 끝까지 따라오게 할 수 있다.
# 프롬프트를 고치면 이 스크립트를 다시 돌려 주문서를 새로 뽑으면 된다 (베끼지 말 것).
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = ROOT / "widget" / "lab-assets" / "prompts"
PLAIN = PROMPTS / "plain"

if hasattr(sys.stdout, "reconfigure"):  # 한국어 Windows 콘솔(cp949) 대응
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def prompt(name: str) -> dict:
    return {"kind": "prompt", "file": name}


def edit(name: str, base: str, change: str, keep: str = "같은 물건, 같은 각도, 같은 크기, 같은 위치, 같은 색") -> dict:
    """change는 '~한/~ㄴ' 꼴의 관형구로 쓴다 (뒤에 '버전이야'가 붙는다)."""
    return {"kind": "edit", "file": name, "base": base, "change": change, "keep": keep}


# (제목, 머리말, 스타일 기준, 단계들)
#   스타일 기준이 None이면 각 묶음의 첫 장이 그 묶음의 기준이 된다.
#   파일명이면 사용자가 그 이미지를 첨부하고 모든 장이 거기에 맞춘다.
SETS = {
    "extras": (
        "연구실 UI 아이콘 5장 + 연구원 초상 5장",
        "방 가구와 **그림체가 다릅니다.** 방 스타일 견본은 참고하지 마세요.\n"
        "각 세트의 첫 장이 그 세트의 기준이 됩니다.",
        None,
        [
            ("UI 아이콘 (256×256, 투명 배경)", [
                prompt("quest_mark.png"),
                prompt("star_on.png"),
                edit("star_off.png", "star_on.png",
                     "아직 못 받은 빈 별 — 전체를 납작한 연회색 베이지(#d9d3c7)로 칠하고 "
                     "반짝임과 하이라이트를 뺀",
                     keep="같은 별 모양, 같은 크기, 같은 위치, 같은 외곽선"),
                prompt("level_badge.png"),
                prompt("stamp_clear.png"),
            ]),
            ("연구원 초상 (512×512, 투명 배경, 머리와 어깨까지)", [
                prompt("avatar_manager.png"),
                prompt("avatar_literature.png"),
                prompt("avatar_analysis.png"),
                prompt("avatar_writing.png"),
                prompt("avatar_review.png"),
            ]),
        ],
    ),
    "room": (
        "연구실 방 배경 1장 + 가구 11장",
        "배경(room.png)만 불투명이고 나머지는 전부 투명 배경입니다.\n"
        "**스타일 견본 `style_sheet.png`를 첨부해 두고** 모든 장을 거기에 맞춥니다.",
        "style_sheet.png",
        [
            ("방과 가구", [
                prompt("room.png"),
                prompt("bookshelf.png"),
                edit("bookshelf_full.png", "bookshelf.png", "선반이 책과 서류로 가득 찬"),
                prompt("board.png"),
                edit("board_quests.png", "board.png", "화이트보드에 색색 자석과 메모가 붙은"),
                prompt("desk.png"),
                edit("desk_writing.png", "desk.png", "노트북 화면이 켜지고 종이가 흩어진"),
                prompt("review_board.png"),
                edit("review_board_notes.png", "review_board.png", "코르크보드에 메모지가 여러 장 꽂힌"),
                prompt("bench.png"),
                edit("bench_running.png", "bench.png", "시험관과 플라스크에 용액이 차고 불이 켜진"),
                prompt("door.png"),
            ]),
        ],
    ),
}

def build(set_name: str) -> str:
    title, note, set_ref, groups = SETS[set_name]
    steps = [s for _, group in groups for s in group]
    total = len(steps)

    out: list[str] = []
    w = out.append

    w(f"# 이미지 주문서 — {title}")
    w("")
    w("이 파일 하나에 **만들 그림 전부의 순서와 프롬프트**가 들어 있습니다.")
    w(note)
    w("")
    w("## 진행 규칙 (반드시 지킬 것)")
    w("")
    w(f"1. **한 번에 딱 한 장만** 만든다. 여러 개를 한 장에 모아 그리지 않는다. 총 {total}장이다.")
    w("2. 답할 때마다 **지금 몇 번째인지 먼저 말한다** (예: `3/{}`).".format(total))
    w("3. 한 장을 만들면 **멈추고 기다린다.** 내가 `다음`이라고 하면 그 다음 번호로 넘어간다.")
    w("4. 내가 `다시`라고 하면 같은 번호를 다시 만든다.")
    w("5. **글자·숫자·로고·서명을 절대 넣지 않는다.**")
    w("6. 배경은 **투명(알파 PNG)**. 투명이 안 되면 아무것도 없는 순수한 흰 배경으로 한다.")
    if any(s["file"] == "room.png" for s in steps):
        w("   단 `room.png`(1번)만 예외로 불투명 배경이다.")
    w("7. 각 단계에 적힌 **파일명 그대로** 알려 준다.")
    w("8. 프롬프트는 아래에 적힌 것을 **그대로** 쓴다. 요약하거나 바꾸지 않는다.")
    w("")
    w("**지금 할 일**: 이 파일을 다 읽었으면 `준비됐어`라고만 답하고 기다린다.")
    w("내가 `시작`이라고 하면 1번부터 진행한다.")
    w("")
    w("---")
    w("")

    n = 0
    for group_title, group in groups:
        first = group[0]["file"]
        w(f"## {group_title}")
        w("")
        for step in group:
            n += 1
            name = step["file"]
            w(f"### {n}/{total} — `{name}`")
            w("")
            if step["kind"] == "edit":
                w(f"**직전에 만든 `{step['base']}`를 첨부해 두고, 그 그림을 고치는 방식으로 만든다.**")
                w("새로 그리지 말 것 — 같은 물건이 다른 상태로 보여야 한다.")
                w("")
                w("```")
                w(f"방금 만든 {step['base']}를 그대로 두고 내용만 바꿔 줘.")
                w(f"{step['keep']} — {step['change']} 버전이야.")
                w(f"구도를 새로 잡지 말고 이 그림을 편집하듯 고쳐 줘. 파일명은 {name}.")
                w("```")
            else:
                src = PLAIN / f"{name}.txt"
                body = src.read_text(encoding="utf-8").strip()
                if name == "avatar_manager.png":
                    w("**내가 캐릭터 참고 이미지를 첨부한다.** 같은 인물, 같은 머리색과 머리 모양,")
                    w("같은 눈, 같은 분위기로 그린다. 전신 말고 머리와 어깨까지만.")
                elif set_ref:
                    w(f"**첨부한 `{set_ref}`와 같은 그림체, 같은 색, 같은 광원으로.**")
                elif name == first:
                    w("이 그림이 **이 묶음의 기준**이 된다. 다음 장들은 전부 이 그림에 맞춘다.")
                else:
                    w(f"**`{first}`와 같은 그림체, 같은 외곽선 두께, 같은 광원, 같은 여백으로.**")
                    if first == "avatar_manager.png":
                        w("다른 사람이지만 같은 세트로 보여야 한다. 머리 크기와 채색을 맞춘다.")
                w("")
                w("```")
                w(body)
                w("```")
            w("")

    w("---")
    w("")
    w("## 다 만든 뒤")
    w("")
    w(f"{total}장을 **각각 따로** 받을 수 있게 파일로 하나씩 주고, 파일명을 위에 적힌 대로 달아 준다.")
    w("한 장에 모아서 주지 않는다.")
    w("")
    return "\n".join(out)


def main() -> int:
    set_name = sys.argv[1] if len(sys.argv) > 1 else "extras"
    if set_name not in SETS:
        print(f"모르는 세트: {set_name} (가능: {', '.join(SETS)})")
        return 1
    text = build(set_name)
    out = PROMPTS / f"주문서_{set_name}.md"
    out.write_text(text, encoding="utf-8")
    steps = sum(len(g) for _, g in SETS[set_name][3])
    print(f"생성: {out.relative_to(ROOT)}  ({steps}단계, {len(text):,}자)")
    print("이 파일 하나만 ChatGPT에 올리고 '시작'이라고 하면 된다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
