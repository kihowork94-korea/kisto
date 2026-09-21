// 키스토 위젯 렌더러. 사용자에게는 "키스토 한 명"만 보여야 하므로 모듈/모델 같은
// 내부 정보는 절대 표시하지 않는다 (CLAUDE.md 설계 결정 4).

const $ = (id) => document.getElementById(id);
const panel = $("panel");
const log = $("log");
const input = $("input");
const sendButton = $("send");
const thought = $("thought");
const wrap = $("character-wrap");
const video = $("source");

const THINKING_LINES = ["음… 생각 중이에요", "자료를 떠올려 보는 중", "하나씩 정리하는 중", "한 번 더 따져보는 중"];
// 지금 일하는 연구원 (백엔드 GET /progress). 모델 이름은 보여주지 않는다 — 연구실의 연구원으로만.
const AGENT_LINES = {
  "라우터": "🧑‍🔬 누구에게 맡길지 정하는 중",
  "키스토 (대화)": "🧑‍🔬 생각하는 중",
  "문헌 검색": "📚 문헌 연구원이 논문 찾는 중",
  "연구 코치": "📚 문헌 연구원이 논문 읽고 정리하는 중",
  "분석 코드 작성": "🧪 분석 연구원이 코드 짜는 중",
  "코드 실행": "🧪 분석 연구원이 분석 돌리는 중",
  "결과 해석": "🧪 분석 연구원이 결과 해석하는 중",
  "집필 코치": "✍️ 집필 연구원이 쓰는 중",
  "교차검증": "🔍 외부 검토위원이 검토하는 중",
  "페르소나": "🧑‍🔬 답변 다듬는 중",
};
const STORE_KEY = "kisto-widget";

let api = "";
let token = "";

// 백엔드는 토큰이 있는 요청만 받는다 (backend/main.py의 guard 참고).
function apiFetch(path, options = {}) {
  const headers = { ...(options.headers || {}), "X-Kisto-Token": token };
  return fetch(api + path, { ...options, headers });
}
let character = null;
let labIcons = {}; // lab-assets/lab.json의 icons (없으면 ✓·반짝이만 쓴다)
let chroma = null;
let busy = false;
let lastProgress = null; // { threadCount, cleared: number[] } — 단계 클리어 감지용
let thoughtTimer = null;
let liveLine = null; // 지금 일하는 연구원 문구 (있으면 일반 문구 대신 보여준다)

// ── 저장 (세션 ID, 최근 대화). 저장이 막혀 있어도 위젯은 동작해야 한다. ──
function loadStore() {
  try {
    return JSON.parse(localStorage.getItem(STORE_KEY)) || {};
  } catch {
    return {};
  }
}
function saveStore(patch) {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify({ ...loadStore(), ...patch }));
  } catch {
    /* 무시 */
  }
}
function newSessionId() {
  return "widget-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 8);
}
let store = loadStore();
let sessionId = store.sessionId || newSessionId();
let history = store.history || [];
saveStore({ sessionId });

// ── 캐릭터 ──
function setVideo(state) {
  const file = (character.videos && character.videos[state]) || character.videos.idle;
  const src = "character/" + file;
  if (!video.src.endsWith(src)) {
    video.src = src;
    video.play().catch(() => {});
  }
}

function setState(state) {
  document.body.classList.toggle("thinking", state === "thinking");
  setVideo(state);
}

function celebrate(text) {
  const toast = $("toast");
  toast.textContent = text;
  toast.hidden = false;
  toast.style.animation = "none";
  void toast.offsetWidth; // 애니메이션 재시작
  toast.style.animation = "";
  setTimeout(() => (toast.hidden = true), 3200);

  document.body.classList.add("celebrating");
  setTimeout(() => document.body.classList.remove("celebrating"), 1000);
  setVideo(character.videos.happy ? "happy" : "idle");
  setTimeout(() => !busy && setVideo("idle"), 2500);

  const box = $("sparkles");
  if (labIcons.clear) {
    const stamp = document.createElement("img");
    stamp.className = "clear-stamp";
    stamp.src = "lab-assets/" + labIcons.clear;
    stamp.alt = "";
    box.appendChild(stamp);
    setTimeout(() => stamp.remove(), 2400);
  }
  for (let i = 0; i < 14; i++) {
    const s = document.createElement("span");
    s.textContent = ["✦", "✧", "★", "✨"][i % 4];
    s.style.left = 30 + Math.random() * 40 + "%";
    s.style.top = 15 + Math.random() * 30 + "%";
    s.style.color = ["#a78bfa", "#60a5fa", "#fbbf24"][i % 3];
    s.style.setProperty("--dx", (Math.random() - 0.5) * 160 + "px");
    s.style.setProperty("--dy", -40 - Math.random() * 90 + "px");
    s.style.animationDelay = Math.random() * 0.3 + "s";
    box.appendChild(s);
    setTimeout(() => s.remove(), 2000);
  }
}

// ── 머리 위 말풍선 ──
function showThought(text, { thinking = false, onClick = null } = {}) {
  clearInterval(thoughtTimer);
  $("thought-text").textContent = text;
  $("thought-timer").textContent = "";
  thought.hidden = false;
  thought.onclick = onClick;
  thought.style.cursor = onClick ? "pointer" : "default";
  if (thinking) {
    const started = Date.now();
    let line = 0;
    thoughtTimer = setInterval(() => {
      const sec = Math.floor((Date.now() - started) / 1000);
      $("thought-timer").textContent = `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")}`;
      if (liveLine) {
        $("thought-text").textContent = liveLine;
      } else if (sec > 0 && sec % 8 === 0) {
        line = (line + 1) % THINKING_LINES.length;
        $("thought-text").textContent = THINKING_LINES[line];
      }
    }, 1000);
  }
}
function hideThought() {
  clearInterval(thoughtTimer);
  thought.hidden = true;
}

// ── 대화 ──
function renderMarkdown(text) {
  return DOMPurify.sanitize(marked.parse(text, { breaks: true }));
}

// 교차검증 결과. 답변에 섞지 않고 접어 둔 노트로 보여준다 — 누르면 펼쳐진다.
function renderReview(review) {
  const details = document.createElement("details");
  details.className = "review";
  const points = review.split("\n").filter((l) => /^\s*(\d+[.)]|[-*•])\s+/.test(l)).length;
  const summary = document.createElement("summary");
  summary.textContent = `🔍 검토 노트 — 다른 관점에서 다시 따져본 결과${points ? ` · 주의할 점 ${points}` : ""}`;
  const body = document.createElement("div");
  body.className = "review-body";
  body.innerHTML = renderMarkdown(review);
  details.append(summary, body);
  return details;
}

// 발표 모드에서만 보이는 에이전트 협업 흐름: 누가, 어느 회사 모델로, 몇 초.
function renderTrace(trace, seconds) {
  const box = document.createElement("div");
  box.className = "trace";
  trace.forEach((step, i) => {
    if (i) box.insertAdjacentHTML("beforeend", '<span class="arrow">→</span>');
    const chip = document.createElement("span");
    chip.className =
      "chip" + (step.agent === "교차검증" ? " verify" : step.agent === "문헌 검색" ? " search" : "");
    const who = document.createElement("b");
    who.textContent = step.agent;
    const models = step.models.length ? ` · ${step.models.join(", ")}` : "";
    const detail = step.detail && step.agent !== "문헌 검색" ? ` (${step.detail})` : "";
    chip.append(who, `${models}${detail} · ${step.seconds}s`);
    chip.title = step.detail || "";
    box.appendChild(chip);
  });
  if (seconds) box.insertAdjacentHTML("beforeend", `<span class="total">총 ${seconds}s</span>`);
  return box;
}

function addMessage(role, text, { persist = true, review = null, trace = null, seconds = null } = {}) {
  const div = document.createElement("div");
  div.className = "msg " + role;
  if (role === "kisto") div.innerHTML = renderMarkdown(text);
  else div.textContent = text;
  log.appendChild(div);
  if (trace && trace.length) log.appendChild(renderTrace(trace, seconds));
  if (review) log.appendChild(renderReview(review));
  // 긴 답변은 끝이 아니라 첫 줄부터 읽히도록 답변 시작 위치로 스크롤한다.
  log.scrollTop = role === "kisto" ? div.offsetTop - log.offsetTop - 8 : log.scrollHeight;
  if (persist && role !== "error") {
    history = [...history, { role, text, review, trace, seconds }].slice(-30);
    saveStore({ history });
  }
}

function openPanel() {
  panel.hidden = false;
  if (!log.childElementCount) {
    addMessage("kisto", "안녕하세요, 키스토예요. 오늘은 어떤 연구 이야기를 해볼까요?", { persist: false });
  }
  if (!busy) hideThought();
  refreshRoadmap();
  input.focus();
}
function togglePanel() {
  if (panel.hidden) openPanel();
  else panel.hidden = true;
}

async function send(text) {
  busy = true;
  input.disabled = sendButton.disabled = $("attach").disabled = true;
  addMessage("user", text);
  setState("thinking");
  showThought(THINKING_LINES[0], { thinking: true });
  liveLine = null;
  const poll = setInterval(async () => {
    try {
      const p = await (await apiFetch(`/progress/${encodeURIComponent(sessionId)}`)).json();
      liveLine = p.agent ? AGENT_LINES[p.agent] || null : liveLine;
    } catch {
      /* 진행 상황은 없어도 된다 */
    }
  }, 1500);

  try {
    const res = await apiFetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message: text }),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || "HTTP " + res.status);
    }
    const data = await res.json();
    if (data.masked && data.masked.length) {
      addMessage("system", `🔒 개인정보로 보이는 부분(${data.masked.join(", ")})은 가리고 보냈어요.`);
    }
    addMessage("kisto", data.reply, { review: data.review, trace: data.trace, seconds: data.seconds });
    if (panel.hidden) {
      showThought("답변이 준비됐어요! 눌러서 확인하기", { onClick: openPanel });
    } else {
      hideThought();
    }
  } catch (err) {
    hideThought();
    addMessage("error", "지금은 답을 못 하겠어요. 키스토 서버가 켜져 있는지 확인해 주세요. (" + err.message + ")");
    if (panel.hidden) openPanel();
  } finally {
    clearInterval(poll);
    liveLine = null;
    busy = false;
    input.disabled = sendButton.disabled = $("attach").disabled = false;
    setState("idle");
    if (!panel.hidden) input.focus();
    refreshRoadmap();
  }
}

// ── 데이터 파일 첨부 (📎 버튼 또는 대화창에 끌어다 놓기) ──
async function attachFile(file) {
  if (!file || busy) return;
  if (!/\.(csv|tsv|txt)$/i.test(file.name)) {
    addMessage("error", "CSV·TSV·TXT 파일만 첨부할 수 있어요. 엑셀은 CSV로 저장해서 올려 주세요.");
    return;
  }
  try {
    const res = await apiFetch("/upload", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, filename: file.name, content: await file.text() }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "HTTP " + res.status);
    const cols = data.columns.slice(0, 6).join(", ") + (data.columns.length > 6 ? " …" : "");
    addMessage("system", `📎 ${data.name} 첨부 — ${data.rows}행, 열: ${cols}. 이제 "이 데이터로 분석해줘"라고 말해 보세요.`);
    if (data.masked.length) {
      addMessage("system", `🔒 파일 안의 개인정보로 보이는 값(${data.masked.join(", ")})은 가려서 저장했어요.`);
    }
    refreshRoadmap();
  } catch (err) {
    addMessage("error", "파일을 첨부하지 못했어요. (" + err.message + ")");
  }
}
$("attach").addEventListener("click", () => $("file").click());
$("file").addEventListener("change", (e) => {
  attachFile(e.target.files[0]);
  e.target.value = "";
});
panel.addEventListener("dragover", (e) => {
  e.preventDefault();
  panel.classList.add("dropping");
});
panel.addEventListener("dragleave", () => panel.classList.remove("dropping"));
panel.addEventListener("drop", (e) => {
  e.preventDefault();
  panel.classList.remove("dropping");
  attachFile(e.dataTransfer.files[0]);
});

// ── 발표 모드: 심사·발표 때만 뒤에서 일한 에이전트들을 보여준다 ──
function setPresenter(on) {
  document.body.classList.toggle("presenter", on);
  saveStore({ presenter: on });
}
window.kisto.onPresenter(setPresenter);

$("composer").addEventListener("submit", (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text || busy) return;
  input.value = "";
  send(text);
});
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    $("composer").requestSubmit();
  }
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") panel.hidden = true;
});

// ── 캐릭터 위 버튼 막대 ──
$("dock-chat").addEventListener("click", togglePanel);
$("dock-lab").addEventListener("click", () => window.kisto.openLab());
$("dock-hide").addEventListener("click", () => window.kisto.hide());
$("dock-quit").addEventListener("click", () => {
  if (confirm("키스토를 종료할까요? (대화 기록은 그대로 남아요)")) window.kisto.quit();
});
$("panel-close").addEventListener("click", () => (panel.hidden = true));
// 초기화(설정·대화 기록 복원)가 끝나기 전에 신호가 오면 끝난 뒤에 연다.
let ready = false;
let openChatWhenReady = false;
window.kisto.onOpenChat(() => {
  if (ready) panel.hidden && openPanel();
  else openChatWhenReady = true;
});

// ── 연구 로드맵 (저장된 실데이터 기준, 서버가 판정) ──
function renderRoadmap(stages, threads) {
  const box = $("roadmap");
  if (!threads.length) {
    box.innerHTML = '<div id="roadmap-empty">아직 시작한 연구 주제가 없어요. 관심 분야를 말해 주세요.</div>';
    box.append(roadmapActions(null));
    return;
  }
  const t = threads[threads.length - 1];
  const p = t.progress;
  const nodes = stages
    .map((stage, i) => {
      const cleared = p.cleared[i];
      const cls = cleared ? "node cleared" : i === p.current_index ? "node current" : "node";
      return `<div class="${cls}"><div class="dot">${cleared ? (labIcons.clear ? `<img class="stamp" src="lab-assets/${labIcons.clear}" alt="✓">` : "✓") : i + 1}</div><div class="label">${stage.label}</div></div>`;
    })
    .join("");
  const hint =
    p.cleared_count === p.total ? "초안까지 완주했어요! 🎉" : `다음 목표 — ${p.current_label}: ${p.current_hint}`;
  const others = threads.length > 1 ? `<div class="quest-others">진행 중인 다른 주제 ${threads.length - 1}개</div>` : "";

  box.innerHTML = "";
  const head = document.createElement("div");
  head.className = "quest-head";
  const topic = document.createElement("span");
  topic.className = "quest-topic";
  topic.textContent = t.topic; // 주제명은 모델이 만든 문자열이라 텍스트로만 넣는다
  topic.title = t.topic;
  const pct = document.createElement("span");
  pct.className = "quest-pct";
  pct.textContent = `${p.cleared_count}/${p.total} · ${p.percent}%`;
  head.append(topic, pct);
  box.append(head);
  box.insertAdjacentHTML("beforeend", `<div class="track">${nodes}</div>`);
  const hintEl = document.createElement("div");
  hintEl.className = "quest-hint";
  hintEl.textContent = hint;
  box.append(hintEl);
  if (others) box.insertAdjacentHTML("beforeend", others);

  box.append(roadmapActions(threads.length - 1));
}

function roadmapActions(lastIndex) {
  const actions = document.createElement("div");
  actions.className = "quest-actions";
  const home = document.createElement("button");
  home.className = "note-btn";
  home.textContent = "🏠 연구실";
  home.title = "연구원들이 일하는 연구실 보기";
  home.onclick = () => window.kisto.openLab();
  actions.append(home);
  if (lastIndex !== null) {
    const noteButton = document.createElement("button");
    noteButton.className = "note-btn";
    noteButton.textContent = "📓 연구노트로 내보내기";
    noteButton.onclick = () => exportNote(lastIndex);
    actions.append(noteButton);
  }
  return actions;
}

async function exportNote(index) {
  try {
    const res = await apiFetch(`/threads/${encodeURIComponent(sessionId)}/${index}/note`);
    if (!res.ok) throw new Error("HTTP " + res.status);
    const file = await window.kisto.saveNote(await res.json());
    addMessage("system", `📓 연구노트 초안을 저장했어요: ${file}`);
  } catch (err) {
    addMessage("error", "연구노트를 만들지 못했어요. (" + err.message + ")");
  }
}

async function refreshRoadmap() {
  try {
    const res = await apiFetch(`/threads/${encodeURIComponent(sessionId)}`);
    const { stages, threads } = await res.json();
    renderRoadmap(stages, threads);

    const current = {
      threadCount: threads.length,
      cleared: threads.length ? threads[threads.length - 1].progress.cleared : [],
    };
    if (lastProgress) {
      const isNewTopic = current.threadCount > lastProgress.threadCount;
      const before = isNewTopic ? [] : lastProgress.cleared;
      const newly = current.cleared.findLastIndex((done, i) => done && !before[i]);
      if (newly >= 0) {
        const stage = `${newly + 1}단계 ${stages[newly].label}`;
        celebrate(isNewTopic ? `새 연구 주제! ${stage}까지 클리어` : `${stage} 클리어!`);
      }
    }
    lastProgress = current;
  } catch {
    /* 서버가 꺼져 있으면 로드맵만 비워 둔다 */
  }
}

// ── 클릭 통과 · 드래그 ──
// 창 전체가 투명하므로, 마우스가 캐릭터의 불투명한 부분이나 대화창 위에 있을 때만
// 클릭을 받고 나머지는 바탕화면으로 통과시킨다.
let ignoring = true;
let pointer = null; // 캐릭터를 누르고 있는 동안의 상태
let pendingMove = null;

function updateHitTest(x, y) {
  const overSolid = !!document.elementFromPoint(x, y)?.closest(".solid");
  const overChar = !overSolid && chroma && chroma.isOpaqueAt(x, y);
  document.body.classList.toggle("hovering-char", !!overChar);
  const shouldIgnore = !(overSolid || overChar || pointer);
  if (shouldIgnore !== ignoring) {
    ignoring = shouldIgnore;
    window.kisto.setIgnoreMouse(ignoring);
  }
}

window.addEventListener("mousemove", (e) => {
  if (pendingMove) return;
  pendingMove = requestAnimationFrame(() => {
    pendingMove = null;
    updateHitTest(e.clientX, e.clientY);
  });
});
document.addEventListener("mouseleave", () => {
  if (!pointer && !ignoring) {
    ignoring = true;
    window.kisto.setIgnoreMouse(true);
  }
});

wrap.addEventListener("pointerdown", (e) => {
  if (e.button !== 0 || !chroma.isOpaqueAt(e.clientX, e.clientY)) return;
  wrap.setPointerCapture(e.pointerId);
  pointer = { x: e.screenX, y: e.screenY, dragging: false };
});
wrap.addEventListener("pointermove", (e) => {
  if (!pointer) return;
  if (!pointer.dragging && Math.hypot(e.screenX - pointer.x, e.screenY - pointer.y) > 4) {
    pointer.dragging = true;
    document.body.classList.add("dragging");
    window.kisto.dragStart();
  }
  if (pointer.dragging) window.kisto.dragMove();
});
wrap.addEventListener("pointerup", (e) => {
  if (!pointer) return;
  wrap.releasePointerCapture(e.pointerId);
  if (pointer.dragging) {
    window.kisto.dragEnd();
    document.body.classList.remove("dragging");
  } else {
    togglePanel();
  }
  pointer = null;
});

// ── 시작 ──
window.kisto.onNewSession(() => {
  sessionId = newSessionId();
  window.kisto.setSession(sessionId);
  history = [];
  saveStore({ sessionId, history });
  log.innerHTML = "";
  lastProgress = null;
  refreshRoadmap();
  openPanel();
});

// 트레이의 '저장된 연구 불러오기' — 그 세션으로 바꾸고 대화창을 백엔드 기록으로 복원한다.
// 로드맵·연구실·대시보드는 세션 ID를 따라가므로 같이 바뀐다.
window.kisto.onLoadSession(async (id) => {
  if (busy) {
    showThought("답을 기다리는 중이라 지금은 바꿀 수 없어요");
    setTimeout(hideThought, 4000);
    return;
  }
  let messages = [];
  try {
    messages = (await (await apiFetch(`/sessions/${encodeURIComponent(id)}/chat`)).json()).messages || [];
  } catch {
    showThought("저장된 연구를 불러오지 못했어요. 키스토 서버가 켜져 있는지 확인해 주세요");
    setTimeout(hideThought, 6000);
    return;
  }
  sessionId = id;
  window.kisto.setSession(sessionId);
  history = messages.slice(-30);
  saveStore({ sessionId, history });
  log.innerHTML = "";
  for (const m of history) addMessage(m.role, m.text, { ...m, persist: false });
  lastProgress = null; // 불러온 기록을 '방금 클리어'로 착각해 축하 연출을 띄우지 않게
  await refreshRoadmap();
  openPanel();
});

(async function init() {
  window.kisto.setSession(sessionId);
  setPresenter(!!store.presenter);
  window.kisto.syncPresenter(!!store.presenter);
  const cfg = await window.kisto.config();
  api = cfg.api;
  token = cfg.token;
  character = cfg.character;
  labIcons = ((await window.kisto.labAssets().catch(() => null)) || {}).icons || {};
  const crop = character.crop || { top: 0, bottom: 0 };
  document.documentElement.style.setProperty("--char-width", character.displayWidth + "px");

  const canvas = $("character");
  video.addEventListener(
    "loadedmetadata",
    () => {
      chroma = chroma || new ChromaCharacter(canvas, video, { key: character.key, crop });
      // 캔버스는 영상 원본 해상도로 그리고 CSS로 줄인다. 작은 캔버스에 바로 그리면
      // 텍스처 샘플링이 듬성듬성해져 머리카락·날개 가장자리가 계단처럼 깨진다.
      const height = Math.round(character.displayWidth * chroma.aspect());
      canvas.width = video.videoWidth;
      canvas.height = Math.round(video.videoWidth * chroma.aspect());
      document.documentElement.style.setProperty("--char-height", height + "px");
    },
    { once: true }
  );
  setVideo("idle");

  for (const m of history) addMessage(m.role, m.text, { ...m, persist: false });
  ready = true;
  if (openChatWhenReady) openPanel();

  try {
    await apiFetch("/health");
    await refreshRoadmap();
    // 처음 켰을 때(대화 기록이 없을 때)는 어떻게 말을 거는지 알려준다.
    if (!history.length) {
      showThought("안녕하세요! 저를 누르거나 💬를 누르면 대화할 수 있어요", { onClick: openPanel });
      setTimeout(() => panel.hidden && !busy && hideThought(), 10000);
    }
  } catch {
    showThought("키스토 서버가 꺼져 있어요. run.ps1로 켜 주세요");
    setTimeout(hideThought, 8000);
  }
})();
