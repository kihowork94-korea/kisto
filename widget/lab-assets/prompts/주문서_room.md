# 이미지 주문서 — 연구실 방 배경 1장 + 가구 11장

이 파일 하나에 **만들 그림 전부의 순서와 프롬프트**가 들어 있습니다.
배경(room.png)만 불투명이고 나머지는 전부 투명 배경입니다.
**스타일 견본 `style_sheet.png`를 첨부해 두고** 모든 장을 거기에 맞춥니다.

## 진행 규칙 (반드시 지킬 것)

1. **한 번에 딱 한 장만** 만든다. 여러 개를 한 장에 모아 그리지 않는다. 총 12장이다.
2. 답할 때마다 **지금 몇 번째인지 먼저 말한다** (예: `3/12`).
3. 한 장을 만들면 **멈추고 기다린다.** 내가 `다음`이라고 하면 그 다음 번호로 넘어간다.
4. 내가 `다시`라고 하면 같은 번호를 다시 만든다.
5. **글자·숫자·로고·서명을 절대 넣지 않는다.**
6. 배경은 **투명(알파 PNG)**. 투명이 안 되면 아무것도 없는 순수한 흰 배경으로 한다.
   단 `room.png`(1번)만 예외로 불투명 배경이다.
7. 각 단계에 적힌 **파일명 그대로** 알려 준다.
8. 프롬프트는 아래에 적힌 것을 **그대로** 쓴다. 요약하거나 바꾸지 않는다.

**지금 할 일**: 이 파일을 다 읽었으면 `준비됐어`라고만 답하고 기다린다.
내가 `시작`이라고 하면 1번부터 진행한다.

---

## 방과 가구

### 1/12 — `room.png`

**첨부한 `style_sheet.png`와 같은 그림체, 같은 색, 같은 광원으로.**

```
2D game asset, cozy research-lab interior, hand-painted flat vector illustration with
soft cel shading and a subtle paper grain. Clean dark-brown outlines (#5b4027), rounded
corners, slightly chunky friendly proportions, anime-adjacent children's-book warmth.
Straight-on front elevation with a slight (about 10 degrees) top-down tilt — no vanishing
point, no isometric skew, no camera rotation. One soft light source from the upper left;
short warm shadows falling to the lower right. Muted warm palette only: cream wall
paper #fffdf8, violet accent #7c3aed, mint accent #1baf7a, charcoal #1f2937. Must stay
readable when shrunk to 25%. No text, no letters, no numbers, no logos, no watermark,
no signature, no UI frames, no people.

An EMPTY cozy research-lab room seen straight on, like a stage set waiting for its
furniture. Three horizontal bands across the full width:
  - top 61% of the height: cream plaster wall (#f3ead9) with a faint vertical paper grain,
  - a wainscot band (#eadcc4) with a thin darker trim line (#d9c4a3) at its top edge,
  - bottom 26%: sandy wooden plank floor (#d2b48c) with soft plank seams receding gently.
Decoration ONLY in the gaps listed below: a round wall clock with a walnut rim, one small
potted plant in a terracotta pot on the floor, a woven round rug on the floor, a thin
framed blank picture, a power outlet and a trailing cable, a few faint scuff marks.
Warm afternoon light pools on the floor from the upper left.

Leave these rectangles free of any object — furniture will be composited on top:
  x 30  y 110  w 180  h 290   (bookshelf)
  x 250 y 45   w 230 h 160    (whiteboard)
  x 250 y 250  w 220 h 155    (desk + laptop)
  x 520 y 55   w 190 h 135    (cork board)
  x 500 y 250  w 230 h 150    (lab bench)
  x 780 y 150  w 130 h 250    (door)
Usable decoration gaps: the wall strip around x 215-245 and x 715-775, the floor strip
below y 405, and the top strip above y 45. The floor line (wall meets floor) must sit at
y = 400 of 540 (= y 800 of 1080) so the furniture stands on it correctly.

Output: exactly 1920 x 1080 pixels, PNG as one opaque image filling the whole canvas.

Avoid: furniture, bookshelf, desk, table, laptop, whiteboard, cork board, lab bench, door, chairs, people, text, letters, numbers, watermark, signature, logo, UI, photorealistic, 3D render, strong perspective, fisheye, dark or moody lighting, clutter in the center
```

### 2/12 — `bookshelf.png`

**첨부한 `style_sheet.png`와 같은 그림체, 같은 색, 같은 광원으로.**

```
2D game asset, cozy research-lab interior, hand-painted flat vector illustration with
soft cel shading and a subtle paper grain. Clean dark-brown outlines (#5b4027), rounded
corners, slightly chunky friendly proportions, anime-adjacent children's-book warmth.
Straight-on front elevation with a slight (about 10 degrees) top-down tilt - no vanishing
point, no isometric skew, no camera rotation. One soft light source from the upper left;
short warm shadows falling to the lower right. Muted warm palette only: cream wall
paper #fffdf8, violet accent #7c3aed, mint accent #1baf7a, charcoal #1f2937. Must stay
readable when shrunk to 25%. No text, no letters, no numbers, no logos, no watermark,
no signature, no UI frames, no people.

Single object, cut out on a fully transparent background (alpha PNG). No ground plane, no
wall behind it, no scene - only the object and its own soft contact shadow, which must be
semi-transparent so it blends onto the room floor. Trim tight: the object touches all four
edges with at most 2% margin.

A tall narrow walnut bookshelf (#8b5e3c frame, #6d4529 inner back panel) with five
shelves, standing upright on short feet. Mostly EMPTY: only a few books leaning on the
second and fourth shelves, one small stack lying flat, one empty document box. Warm and
tidy but clearly waiting to be filled. Slight wood grain, rounded edges, a soft
semi-transparent contact shadow under the feet.

Output: exactly 360 x 580 pixels, PNG with a fully transparent background (alpha channel).

Avoid: text, letters, numbers, watermark, signature, logo, UI, buttons, people, hands, faces, photorealistic, 3D render, glossy plastic, neon, harsh contrast, white background, opaque background, background scene, wall, floor, room, cropped object, multiple objects, perspective distortion, strong drop shadow
```

### 3/12 — `bookshelf_full.png`

**직전에 만든 `bookshelf.png`를 첨부해 두고, 그 그림을 고치는 방식으로 만든다.**
새로 그리지 말 것 — 같은 물건이 다른 상태로 보여야 한다.

```
방금 만든 bookshelf.png를 그대로 두고 내용만 바꿔 줘.
같은 물건, 같은 각도, 같은 크기, 같은 위치, 같은 색 — 선반이 책과 서류로 가득 찬 버전이야.
구도를 새로 잡지 말고 이 그림을 편집하듯 고쳐 줘. 파일명은 bookshelf_full.png.
```

### 4/12 — `board.png`

**첨부한 `style_sheet.png`와 같은 그림체, 같은 색, 같은 광원으로.**

```
2D game asset, cozy research-lab interior, hand-painted flat vector illustration with
soft cel shading and a subtle paper grain. Clean dark-brown outlines (#5b4027), rounded
corners, slightly chunky friendly proportions, anime-adjacent children's-book warmth.
Straight-on front elevation with a slight (about 10 degrees) top-down tilt - no vanishing
point, no isometric skew, no camera rotation. One soft light source from the upper left;
short warm shadows falling to the lower right. Muted warm palette only: cream wall
paper #fffdf8, violet accent #7c3aed, mint accent #1baf7a, charcoal #1f2937. Must stay
readable when shrunk to 25%. No text, no letters, no numbers, no logos, no watermark,
no signature, no UI frames, no people.

Single object, cut out on a fully transparent background (alpha PNG). No ground plane, no
wall behind it, no scene - only the object and its own soft contact shadow, which must be
semi-transparent so it blends onto the room floor. Trim tight: the object touches all four
edges with at most 2% margin.

A small white magnetic whiteboard in a light grey aluminium frame, hanging flat on a wall,
seen straight on. The surface is nearly BLANK (#fffdf8) with a faint smudge of old eraser
marks. A slim pen tray along the bottom edge holds two markers (violet and mint) and a
felt eraser. Two round magnets rest in a corner. Because it hangs on a wall, give it a
soft semi-transparent shadow hugging its outer edge only - no floor shadow.

Output: exactly 460 x 320 pixels, PNG with a fully transparent background (alpha channel).

Avoid: text, letters, numbers, watermark, signature, logo, UI, buttons, people, hands, faces, photorealistic, 3D render, glossy plastic, neon, harsh contrast, white background, opaque background, background scene, wall, floor, room, cropped object, multiple objects, perspective distortion, strong drop shadow
```

### 5/12 — `board_quests.png`

**직전에 만든 `board.png`를 첨부해 두고, 그 그림을 고치는 방식으로 만든다.**
새로 그리지 말 것 — 같은 물건이 다른 상태로 보여야 한다.

```
방금 만든 board.png를 그대로 두고 내용만 바꿔 줘.
같은 물건, 같은 각도, 같은 크기, 같은 위치, 같은 색 — 화이트보드에 색색 자석과 메모가 붙은 버전이야.
구도를 새로 잡지 말고 이 그림을 편집하듯 고쳐 줘. 파일명은 board_quests.png.
```

### 6/12 — `desk.png`

**첨부한 `style_sheet.png`와 같은 그림체, 같은 색, 같은 광원으로.**

```
2D game asset, cozy research-lab interior, hand-painted flat vector illustration with
soft cel shading and a subtle paper grain. Clean dark-brown outlines (#5b4027), rounded
corners, slightly chunky friendly proportions, anime-adjacent children's-book warmth.
Straight-on front elevation with a slight (about 10 degrees) top-down tilt - no vanishing
point, no isometric skew, no camera rotation. One soft light source from the upper left;
short warm shadows falling to the lower right. Muted warm palette only: cream wall
paper #fffdf8, violet accent #7c3aed, mint accent #1baf7a, charcoal #1f2937. Must stay
readable when shrunk to 25%. No text, no letters, no numbers, no logos, no watermark,
no signature, no UI frames, no people.

Single object, cut out on a fully transparent background (alpha PNG). No ground plane, no
wall behind it, no scene - only the object and its own soft contact shadow, which must be
semi-transparent so it blends onto the room floor. Trim tight: the object touches all four
edges with at most 2% margin.

A small warm-wood writing desk (#a0714a top, #8b5e3c legs) with one shallow drawer, seen
straight on, standing on its four legs. On the desk: an open laptop whose screen is
switched OFF - a dark charcoal (#374151) panel with a faint reflection - plus a ceramic
mug, a short stack of blank paper and a capped pen. Tidy and quiet. Soft semi-transparent
contact shadow under the legs.

Output: exactly 440 x 310 pixels, PNG with a fully transparent background (alpha channel).

Avoid: text, letters, numbers, watermark, signature, logo, UI, buttons, people, hands, faces, photorealistic, 3D render, glossy plastic, neon, harsh contrast, white background, opaque background, background scene, wall, floor, room, cropped object, multiple objects, perspective distortion, strong drop shadow
```

### 7/12 — `desk_writing.png`

**직전에 만든 `desk.png`를 첨부해 두고, 그 그림을 고치는 방식으로 만든다.**
새로 그리지 말 것 — 같은 물건이 다른 상태로 보여야 한다.

```
방금 만든 desk.png를 그대로 두고 내용만 바꿔 줘.
같은 물건, 같은 각도, 같은 크기, 같은 위치, 같은 색 — 노트북 화면이 켜지고 종이가 흩어진 버전이야.
구도를 새로 잡지 말고 이 그림을 편집하듯 고쳐 줘. 파일명은 desk_writing.png.
```

### 8/12 — `review_board.png`

**첨부한 `style_sheet.png`와 같은 그림체, 같은 색, 같은 광원으로.**

```
2D game asset, cozy research-lab interior, hand-painted flat vector illustration with
soft cel shading and a subtle paper grain. Clean dark-brown outlines (#5b4027), rounded
corners, slightly chunky friendly proportions, anime-adjacent children's-book warmth.
Straight-on front elevation with a slight (about 10 degrees) top-down tilt - no vanishing
point, no isometric skew, no camera rotation. One soft light source from the upper left;
short warm shadows falling to the lower right. Muted warm palette only: cream wall
paper #fffdf8, violet accent #7c3aed, mint accent #1baf7a, charcoal #1f2937. Must stay
readable when shrunk to 25%. No text, no letters, no numbers, no logos, no watermark,
no signature, no UI frames, no people.

Single object, cut out on a fully transparent background (alpha PNG). No ground plane, no
wall behind it, no scene - only the object and its own soft contact shadow, which must be
semi-transparent so it blends onto the room floor. Trim tight: the object touches all four
edges with at most 2% margin.

A cork pin board in a thin walnut frame (#8b5e3c), hanging flat on a wall, seen straight
on. The cork surface (#d2b48c with fine speckles) is EMPTY except for four push pins
parked in the corners and one magnifying glass with a walnut handle hooked on the lower
edge of the frame. Calm and unused. Soft semi-transparent shadow hugging the frame edge
only - no floor shadow.

Output: exactly 380 x 270 pixels, PNG with a fully transparent background (alpha channel).

Avoid: text, letters, numbers, watermark, signature, logo, UI, buttons, people, hands, faces, photorealistic, 3D render, glossy plastic, neon, harsh contrast, white background, opaque background, background scene, wall, floor, room, cropped object, multiple objects, perspective distortion, strong drop shadow
```

### 9/12 — `review_board_notes.png`

**직전에 만든 `review_board.png`를 첨부해 두고, 그 그림을 고치는 방식으로 만든다.**
새로 그리지 말 것 — 같은 물건이 다른 상태로 보여야 한다.

```
방금 만든 review_board.png를 그대로 두고 내용만 바꿔 줘.
같은 물건, 같은 각도, 같은 크기, 같은 위치, 같은 색 — 코르크보드에 메모지가 여러 장 꽂힌 버전이야.
구도를 새로 잡지 말고 이 그림을 편집하듯 고쳐 줘. 파일명은 review_board_notes.png.
```

### 10/12 — `bench.png`

**첨부한 `style_sheet.png`와 같은 그림체, 같은 색, 같은 광원으로.**

```
2D game asset, cozy research-lab interior, hand-painted flat vector illustration with
soft cel shading and a subtle paper grain. Clean dark-brown outlines (#5b4027), rounded
corners, slightly chunky friendly proportions, anime-adjacent children's-book warmth.
Straight-on front elevation with a slight (about 10 degrees) top-down tilt - no vanishing
point, no isometric skew, no camera rotation. One soft light source from the upper left;
short warm shadows falling to the lower right. Muted warm palette only: cream wall
paper #fffdf8, violet accent #7c3aed, mint accent #1baf7a, charcoal #1f2937. Must stay
readable when shrunk to 25%. No text, no letters, no numbers, no logos, no watermark,
no signature, no UI frames, no people.

Single object, cut out on a fully transparent background (alpha PNG). No ground plane, no
wall behind it, no scene - only the object and its own soft contact shadow, which must be
semi-transparent so it blends onto the room floor. Trim tight: the object touches all four
edges with at most 2% margin.

A small laboratory bench with a pale grey-green worktop and a walnut base cabinet with two
doors, seen straight on. On the worktop: a wooden rack holding four EMPTY glass test tubes,
one empty conical flask, a small closed notebook, and a compact grey analysis device with a
dark inactive display. The glass is drawn with simple flat highlights, clean and unused.
Soft semi-transparent contact shadow along the base.

Output: exactly 460 x 300 pixels, PNG with a fully transparent background (alpha channel).

Avoid: text, letters, numbers, watermark, signature, logo, UI, buttons, people, hands, faces, photorealistic, 3D render, glossy plastic, neon, harsh contrast, white background, opaque background, background scene, wall, floor, room, cropped object, multiple objects, perspective distortion, strong drop shadow
```

### 11/12 — `bench_running.png`

**직전에 만든 `bench.png`를 첨부해 두고, 그 그림을 고치는 방식으로 만든다.**
새로 그리지 말 것 — 같은 물건이 다른 상태로 보여야 한다.

```
방금 만든 bench.png를 그대로 두고 내용만 바꿔 줘.
같은 물건, 같은 각도, 같은 크기, 같은 위치, 같은 색 — 시험관과 플라스크에 용액이 차고 불이 켜진 버전이야.
구도를 새로 잡지 말고 이 그림을 편집하듯 고쳐 줘. 파일명은 bench_running.png.
```

### 12/12 — `door.png`

**첨부한 `style_sheet.png`와 같은 그림체, 같은 색, 같은 광원으로.**

```
2D game asset, cozy research-lab interior, hand-painted flat vector illustration with
soft cel shading and a subtle paper grain. Clean dark-brown outlines (#5b4027), rounded
corners, slightly chunky friendly proportions, anime-adjacent children's-book warmth.
Straight-on front elevation with a slight (about 10 degrees) top-down tilt - no vanishing
point, no isometric skew, no camera rotation. One soft light source from the upper left;
short warm shadows falling to the lower right. Muted warm palette only: cream wall
paper #fffdf8, violet accent #7c3aed, mint accent #1baf7a, charcoal #1f2937. Must stay
readable when shrunk to 25%. No text, no letters, no numbers, no logos, no watermark,
no signature, no UI frames, no people.

Single object, cut out on a fully transparent background (alpha PNG). No ground plane, no
wall behind it, no scene - only the object and its own soft contact shadow, which must be
semi-transparent so it blends onto the room floor. Trim tight: the object touches all four
edges with at most 2% margin.

A closed walnut office door (#8b5e3c panels, #6d4529 recessed inserts) in a slightly
lighter frame, seen straight on. A small brass round handle on the right, a narrow frosted
glass window in the upper third glowing faint warm cream, and a BLANK rectangular name
plate mounted at eye height - the plate must be empty, with no writing at all. A small
empty paper holder beside the frame. Soft semi-transparent shadow at the threshold where
the door meets the floor.

Output: exactly 260 x 500 pixels, PNG with a fully transparent background (alpha channel).

Avoid: text, letters, numbers, watermark, signature, logo, UI, buttons, people, hands, faces, photorealistic, 3D render, glossy plastic, neon, harsh contrast, white background, opaque background, background scene, wall, floor, room, cropped object, multiple objects, perspective distortion, strong drop shadow
```

---

## 다 만든 뒤

12장을 **각각 따로** 받을 수 있게 파일로 하나씩 주고, 파일명을 위에 적힌 대로 달아 준다.
한 장에 모아서 주지 않는다.
