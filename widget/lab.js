// 키스토 연구실 — 진행 중인 연구 프로젝트를 게임 속 연구실처럼 보여준다.
// 모든 연출(책 수, 시험관, 검토 메모, 퀘스트 표시, 레벨)은 백엔드에 저장된 실데이터로만 정한다.

const $ = (id) => document.getElementById(id);
const SVG = "http://www.w3.org/2000/svg";

// 로드맵 단계 → 그 단계의 일을 하는 자리 (퀘스트 ❗가 뜨는 곳)
const STAGE_SPOT = { 1: "library", 2: "bench", 3: "review", 4: "laptop" };
const SPOT_NAME = {
  library: "서재",
  bench: "실험대",
  laptop: "노트북",
  review: "검토 보드",
  board: "퀘스트 보드",
  team: "연구원 명단",
};

let api = "";
let token = "";
let sessionId = null;
let overview = null; // /lab/session
let roles = null; // /lab/roles
let detail = null; // 선택한 프로젝트의 전체 기록
let selected = null; // 프로젝트 index
let view = "board";
let assets = {};

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

// UI 아이콘·연구원 초상 (lab.json의 icons / avatars). 등록돼 있지 않으면 원래 이모지·글자를 쓴다.
function icon(key, fallback, cls = "") {
  const file = assets.icons && assets.icons[key];
  return file ? `<img class="ico ${cls}" src="lab-assets/${esc(file)}" alt="${esc(fallback)}">` : fallback;
}
function avatar(roleKey, fallback, cls = "") {
  const file = assets.avatars && assets.avatars[roleKey];
  return file ? `<img class="avatar ${cls}" src="lab-assets/${esc(file)}" alt="">` : fallback;
}
const starRow = (on, total) => icon("star_on", "★", "star").repeat(on) + icon("star_off", "☆", "star").repeat(total - on);
const md = (text) => DOMPurify.sanitize(marked.parse(text || "", { breaks: true }));

// 백엔드는 토큰이 있는 요청만 받는다 (backend/main.py의 guard 참고).
async function getJSON(path, options = {}) {
  const headers = { ...(options.headers || {}), "X-Kisto-Token": token };
  const res = await fetch(api + path, { ...options, headers });
  if (!res.ok) throw new Error("HTTP " + res.status);
  return res.json();
}

// ── 데이터 불러오기 ──
async function load({ keepDrawer = false } = {}) {
  if (!sessionId) {
    guide("위젯을 먼저 실행해 주세요. 위젯의 대화 기록을 이 연구실에서 보여줘요.");
    return;
  }
  try {
    [overview, roles] = await Promise.all([
      getJSON(`/lab/session/${encodeURIComponent(sessionId)}`),
      getJSON("/lab/roles"),
    ]);
  } catch {
    guide("연구실 서버에 연결하지 못했어요. <b>run.cmd</b>로 키스토를 켜 주세요.");
    return;
  }
  const count = overview.projects.length;
  if (selected === null || selected >= count) selected = count ? count - 1 : null;
  detail = selected === null
    ? null
    : await getJSON(`/threads/${encodeURIComponent(sessionId)}/${selected}/detail`).catch(() => null);
  renderTopbar();
  renderScene();
  // 역할 설정 폼을 쓰는 중에 자동 갱신이 덮어쓰지 않도록, 그 화면에서는 서랍을 다시 그리지 않는다.
  if (!(keepDrawer && view === "team")) renderDrawer();
}

function renderAll() {
  renderTopbar();
  renderScene();
  renderDrawer();
}

// ── 상단 바 ──
function renderTopbar() {
  const pick = $("project");
  pick.innerHTML = overview.projects.length
    ? overview.projects
        .map((p) => `<option value="${p.index}" ${p.index === selected ? "selected" : ""}>${esc(p.topic)} (${p.progress.percent}%)</option>`)
        .join("")
    : "<option>아직 프로젝트가 없어요</option>";
  pick.disabled = !overview.projects.length;

  const lv = overview.level;
  $("level").innerHTML =
    `<span class="lv">${icon("level", "", "lv-badge")}Lv.${lv.level}</span><span>${esc(lv.title)}</span>` +
    `<span class="stars" title="다음 레벨까지 별 ${lv.per_level - lv.into_level}개">${icon("star_on", "★", "star")} ${lv.stars} · ${starRow(lv.into_level, lv.per_level)}</span>` +
    `<span class="bar"><i style="width:${(lv.into_level / lv.per_level) * 100}%"></i></span>`;
}

// ── 연구실 장면 ──
function renderScene() {
  const project = selected === null ? null : overview.projects[selected];
  const counts = project ? project.counts : { papers: 0, analyses: 0, reviews: 0, draft: false };

  drawBooks(counts.papers);
  drawTubes(counts.analyses);
  drawNotes(detail ? detail.reviews : []);
  drawBoard();
  $("laptop-screen").classList.toggle("on", counts.draft);
  $("laptop-lines").setAttribute("opacity", counts.draft ? "0.9" : "0");

  setBadge("library", counts.papers);
  setBadge("bench", counts.analyses);
  setBadge("review", counts.reviews);
  setBadge("laptop", counts.draft ? 1 : 0);

  // 퀘스트 표시: 선택한 프로젝트의 '다음 단계'를 하는 자리 위에만 뜬다.
  document.querySelectorAll(".quest").forEach((q) => q.classList.remove("on"));
  if (project) {
    const done = project.progress.cleared_count === project.progress.total;
    const spot = done ? "board" : STAGE_SPOT[project.progress.current_index];
    if (spot) $("quest-" + spot).classList.add("on");
  }

  document.querySelectorAll(".spot").forEach((s) => s.classList.toggle("active", s.dataset.view === view));
  applyAssets(counts);
  renderGuide(project);
}

function setBadge(spot, n) {
  const badge = $("badge-" + spot);
  badge.querySelector("text").textContent = n;
  badge.classList.toggle("zero", !n);
}

function el(tag, attrs) {
  const node = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  return node;
}

// 책장: 찾은 논문 수만큼 책이 밝게 꽂힌다 (나머지는 빈자리처럼 흐리게)
function drawBooks(papers) {
  const box = $("books");
  box.innerHTML = "";
  const colors = ["#ef4444", "#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899", "#14b8a6", "#f97316"];
  const shelves = [128, 198, 268, 338];
  let n = 0;
  shelves.forEach((top) => {
    let x = 46;
    for (let i = 0; i < 8; i++, n++) {
      const w = 13 + ((n * 7) % 6);
      const h = 44 + ((n * 5) % 12);
      const book = el("rect", {
        x, y: top + (56 - h), width: w, height: h, rx: 2,
        fill: colors[n % colors.length],
        class: "book " + (n < papers ? "lit" : "dim"),
      });
      box.appendChild(book);
      x += w + 5;
    }
  });
}

// 실험대: 분석을 돌린 횟수만큼 시험관에 용액이 찬다
function drawTubes(analyses) {
  const box = $("tubes");
  box.innerHTML = "";
  const liquids = ["#60a5fa", "#f472b6", "#34d399", "#fbbf24", "#a78bfa"];
  for (let i = 0; i < 5; i++) {
    const x = 527 + i * 17;
    box.appendChild(el("rect", { x, y: 250, width: 11, height: 50, rx: 5, fill: "#f0f9ff", stroke: "#94a3b8" }));
    if (i < analyses) {
      box.appendChild(el("rect", { x: x + 1, y: 272, width: 9, height: 27, rx: 4, fill: liquids[i] }));
    }
  }
}

// 검토 보드: 검토 기록마다 메모지가 붙는다 (지적이 있으면 노랑·빨간 핀, 없으면 초록)
function drawNotes(reviews) {
  const box = $("review-notes");
  box.innerHTML = "";
  reviews.slice(-8).forEach((r, i) => {
    const x = 534 + (i % 4) * 42;
    const y = 68 + Math.floor(i / 4) * 52;
    const tilt = ((i * 37) % 11) - 5;
    const g = el("g", { transform: `rotate(${tilt} ${x + 17} ${y + 20})` });
    g.appendChild(el("rect", { x, y, width: 34, height: 40, rx: 2, fill: r.issues ? "#fef08a" : "#bbf7d0" }));
    g.appendChild(el("circle", { cx: x + 17, cy: y + 4, r: 3.5, fill: r.issues ? "#dc2626" : "#16a34a" }));
    for (let l = 0; l < 3; l++) {
      g.appendChild(el("rect", { x: x + 5, y: y + 13 + l * 8, width: 24 - l * 5, height: 3, rx: 1.5, fill: "#a8a29e" }));
    }
    box.appendChild(g);
  });
}

// 퀘스트 보드: 프로젝트마다 한 줄씩 5단계 점이 찍힌다
function drawBoard() {
  const box = $("board-cards");
  box.innerHTML = "";
  const projects = overview.projects.slice(-4);
  if (!projects.length) {
    const t = el("text", { x: 365, y: 130, class: "board-empty" });
    t.textContent = "아직 퀘스트가 없어요";
    box.appendChild(t);
    return;
  }
  projects.forEach((p, row) => {
    const y = 92 + row * 26;
    const label = el("text", { x: 262, y: y + 4, class: "board-topic" });
    label.textContent = p.topic.length > 9 ? p.topic.slice(0, 9) + "…" : p.topic;
    if (p.index === selected) label.setAttribute("fill", "#7c3aed");
    box.appendChild(label);
    p.progress.cleared.forEach((done, i) => {
      box.appendChild(el("circle", {
        cx: 392 + i * 17, cy: y, r: 6,
        fill: done ? "#7c3aed" : "#e5e7eb",
        stroke: i === p.progress.current_index && !done ? "#7c3aed" : "none",
        "stroke-width": 2,
      }));
    });
  });
}

// 이미지 에셋이 있으면 벡터 그림 대신 쓴다 (lab-assets/lab.json)
function applyAssets(counts) {
  const room = $("room-image");
  room.innerHTML = "";
  if (assets.background) {
    room.appendChild(el("image", { href: "lab-assets/" + assets.background, x: 0, y: 0, width: 960, height: 540, preserveAspectRatio: "xMidYMid slice" }));
  }
  $("room-art").style.display = assets.background ? "none" : "";

  const active = {
    library: counts.papers > 0,
    bench: counts.analyses > 0,
    review: counts.reviews > 0,
    laptop: counts.draft,
    board: overview.projects.length > 0,
    team: false,
  };
  document.querySelectorAll(".spot").forEach((spot) => {
    const key = spot.dataset.view;
    const conf = assets.spots && assets.spots[key];
    spot.querySelectorAll(":scope > image.asset").forEach((n) => n.remove());
    const art = [...spot.children].filter((c) => !c.matches(".tag, .badge, .quest, image.asset"));
    art.forEach((c) => (c.style.display = conf ? "none" : ""));
    if (conf && conf.image) {
      const file = active[key] && conf.image_active ? conf.image_active : conf.image;
      const img = el("image", {
        href: "lab-assets/" + file, x: conf.x, y: conf.y, width: conf.width, height: conf.height, class: "asset",
      });
      spot.insertBefore(img, spot.firstChild);
    }
  });
}

// 장면의 퀘스트 표시(❗, 완주 🏆)와 안내 말풍선의 키스토 얼굴을 그림으로 바꾼다 (시작할 때 한 번)
function applyStaticIcons() {
  document.querySelectorAll(".quest").forEach((q) => {
    const file = assets.icons && assets.icons[q.classList.contains("trophy") ? "clear" : "quest"];
    if (file) q.replaceChildren(el("image", { href: "lab-assets/" + file, x: -24, y: -24, width: 48, height: 48 }));
  });
  const face = assets.avatars && assets.avatars.manager;
  if (face) document.querySelector("#guide img").src = "lab-assets/" + face;
}

// 매니저 키스토의 안내: 지금 무엇을 하면 되는지 알려준다
function renderGuide(project) {
  if (!project) {
    guide("아직 진행 중인 프로젝트가 없어요. 위젯에서 관심 있는 연구 주제를 이야기해 보세요!");
    return;
  }
  const p = project.progress;
  if (p.cleared_count === p.total) {
    guide(`<b>${esc(project.topic)}</b> 초안까지 완주했어요! ${icon("clear", "🏆", "inline")} <b>노트북</b>에서 연구노트로 내보낼 수 있어요.`);
    return;
  }
  const spot = STAGE_SPOT[p.current_index];
  guide(
    `다음 퀘스트는 <b>${esc(p.current_label)}</b> — ${esc(p.current_hint)}.` +
      (spot ? ` ${icon("quest", "❗", "inline")}가 뜬 <b>${SPOT_NAME[spot]}</b>를 눌러 보세요.` : "")
  );
}

function guide(html) {
  $("guide-text").innerHTML = html;
}

// ── 오른쪽 서랍 ──
function roleOf(key) {
  return roles.roles.find((r) => r.key === key);
}

function providerLabel(key) {
  const p = roles.providers.find((x) => x.key === key);
  return p ? p.label : key;
}

function roleCard(key, extra = "") {
  const r = roleOf(key);
  const work = overview.work[key] ?? 0;
  const model = r.provider ? providerLabel(r.provider) : "자동 배치";
  return `<div class="role-card">
      <div class="emoji">${avatar(key, r.emoji)}</div>
      <div>
        <div class="name">${esc(r.name)}</div>
        <div class="duty">${esc(r.duty)}</div>
        <div class="meta"><span class="pill">모델: ${esc(model)}</span><span class="pill">누적 업무 ${work}건</span>${extra}</div>
      </div>
    </div>`;
}

function track(progress, stages) {
  return `<div class="track">${stages
    .map((s, i) => {
      const done = progress.cleared[i];
      const cls = done ? "node cleared" : i === progress.current_index ? "node current" : "node";
      return `<div class="${cls}"><div class="dot">${done ? icon("clear", "✓", "stamp") : i + 1}</div>${esc(s.label)}</div>`;
    })
    .join("")}</div>`;
}

const VIEWS = {
  board() {
    const lv = overview.level;
    let html = `<h2>📋 퀘스트 보드</h2>
      <div class="level-card">
        <div class="big">${icon("level", "", "lv-badge lg")}Lv.${lv.level} ${esc(lv.title)}</div>
        <div class="stars">${starRow(lv.into_level, lv.per_level)}</div>
        <div class="sub">프로젝트에서 단계를 하나 클리어할 때마다 별 1개 · 지금까지 별 ${lv.stars}개</div>
      </div>`;
    if (!overview.projects.length) {
      return html + `<div class="empty">아직 프로젝트가 없어요. 위젯에서 연구 주제를 이야기하면 여기에 퀘스트가 생겨요.</div>`;
    }
    html += `<h3>진행 중인 프로젝트 (눌러서 선택)</h3>`;
    for (const p of [...overview.projects].reverse()) {
      html += `<div class="card pick ${p.index === selected ? "selected" : ""}" data-project="${p.index}">
          <div class="title">${esc(p.topic)}</div>
          <div class="sub">${p.progress.cleared_count}/${p.progress.total} 단계 · 논문 ${p.counts.papers} · 분석 ${p.counts.analyses} · 검토 ${p.counts.reviews}${p.counts.draft ? " · 초안 ✓" : ""}</div>
          ${track(p.progress, overview.stages)}
        </div>`;
    }
    return html;
  },

  library() {
    let html = `<h2>📚 서재</h2>${roleCard("research_coach")}`;
    if (!detail || !detail.references.length) {
      return html + `<div class="empty">아직 찾은 논문이 없어요. 위젯에서 연구 주제를 이야기하면 문헌 연구원이 실제 논문을 찾아 여기 꽂아 둬요.</div>`;
    }
    html += `<div class="hint">PubMed·OpenAlex에서 실제로 검색한 논문이에요. 답변의 [번호] 인용이 이 번호예요.</div>`;
    detail.references.forEach((p, i) => {
      const authors = (p.authors || []).join(", ") + ((p.authors || []).length === 3 ? " 외" : "");
      html += `<div class="card">
          <div class="title">[${i + 1}] ${p.doi ? `<a href="${esc(p.doi)}" target="_blank">${esc(p.title)}</a>` : esc(p.title)}</div>
          <div class="sub">${esc(authors)} · ${esc(p.year ?? "")} · ${esc(p.venue ?? "")}${p.cited_by != null ? ` · 인용 ${p.cited_by}회` : ""}</div>
          ${p.abstract ? `<details><summary>초록 보기</summary><div>${esc(p.abstract)}</div></details>` : ""}
        </div>`;
    });
    if (detail.hypotheses.length) {
      html += `<h3>최근 가설 정리</h3><div class="card md">${md(detail.hypotheses[0])}</div>`;
    }
    return html;
  },

  bench() {
    let html = `<h2>🧪 실험대</h2>${roleCard("analysis_partner")}`;
    if (detail && detail.files.length) {
      html += `<h3>첨부 데이터</h3>` + detail.files
        .map((f) => `<div class="card"><div class="title">📎 ${esc(f.name)}</div><div class="sub">${f.rows}행 · 열: ${esc(f.columns.join(", "))}</div></div>`)
        .join("");
    }
    if (!detail || !detail.analysis.length) {
      return html + `<div class="empty">아직 돌린 분석이 없어요. 위젯에 데이터를 주고 "분석해줘"라고 하면 분석 연구원이 코드를 짜서 돌려요.</div>`;
    }
    detail.analysis.forEach((a, i) => {
      html += `<div class="card">
          <div class="title">분석 ${i + 1}</div>
          <details><summary>실행 코드</summary><pre>${esc(a.code)}</pre></details>
          <details open><summary>실행 결과</summary><pre>${esc(a.output)}</pre></details>
          <details open><summary>해석</summary><div class="md">${md(a.interpretation)}</div></details>
        </div>`;
    });
    return html;
  },

  review() {
    let html = `<h2>🔍 검토 보드</h2>${roleCard("verifier", `<span class="pill ok">결과를 만든 연구원과 다른 회사 모델만 배정</span>`)}`;
    if (!detail || !detail.reviews.length) {
      return html + `<div class="empty">아직 검토 기록이 없어요. 다른 연구원이 결과를 내면 외부 검토위원이 반박해 보고 여기에 메모를 붙여요.</div>`;
    }
    for (const rv of [...detail.reviews].reverse()) {
      const cross = rv.producer !== rv.reviewer;
      html += `<div class="card">
          <div class="title">${rv.issues ? "📌 지적 있음" : "✅ 특이사항 없음"} · ${esc(rv.stage)}</div>
          <div class="sub">${esc(rv.producer)} → 검토 ${esc(rv.reviewer)} ${cross ? `<span class="pill ok">다른 회사 검토</span>` : `<span class="pill warn">같은 회사 (API 키를 넣으면 다른 회사로 배정)</span>`} · ${esc((rv.at ?? "").replace("T", " "))}</div>
          ${rv.issues ? `<div class="md">${md(rv.text)}</div>` : ""}
        </div>`;
    }
    return html;
  },

  laptop() {
    let html = `<h2>💻 노트북</h2>${roleCard("writing_coach", `<span class="pill">대필 금지 — 해석을 먼저 들어요</span>`)}`;
    if (!detail) return html + `<div class="empty">아직 프로젝트가 없어요.</div>`;
    html += `<h3>연구 책임자의 해석</h3>`;
    html += detail.interpretation
      ? `<div class="card">${esc(detail.interpretation)}</div>`
      : `<div class="empty">아직 없어요. 위젯에서 "초안 써줘"라고 하면 집필 연구원이 먼저 해석을 물어봐요.</div>`;
    html += `<h3>초안</h3>`;
    html += detail.draft ? `<div class="card md">${md(detail.draft)}</div>` : `<div class="empty">아직 초안이 없어요.</div>`;
    html += `<p><button class="primary" id="export-note">📓 연구노트로 내보내기</button></p>`;
    return html;
  },

  team() {
    let html = `<h2>🚪 연구원 명단</h2>
      <div class="hint">연구 책임자(나)가 연구원마다 <b>어느 회사 모델</b>에게 일을 맡길지, <b>어떤 지침</b>을 따르게 할지 정해요.
      '자동 배치'는 기본 배치(분석=OpenAI, 검토=Gemini, 나머지=Claude — 키가 없으면 있는 모델로 대신)를 따라요.</div>`;
    const options = (current) =>
      `<option value="">자동 배치</option>` +
      roles.providers.map((p) => `<option value="${esc(p.key)}" ${p.key === current ? "selected" : ""}>${esc(p.label)}</option>`).join("");
    for (const r of roles.roles) {
      html += `<div class="role-form" data-role="${r.key}">
          <div class="head"><span class="head-av">${avatar(r.key, r.emoji, "sm")}</span>${esc(r.name)} <span class="sub">· ${esc(r.place)} · 누적 업무 ${overview.work[r.key] ?? 0}건</span></div>
          <div class="sub">${esc(r.duty)}</div>
          <label>담당 모델<select>${options(r.provider)}</select></label>
          <label>이 연구원에게 주는 지침 (선택)<textarea placeholder="예: 효과 크기와 신뢰구간을 항상 같이 보고해 줘">${esc(r.instructions || "")}</textarea></label>
          ${r.key === "verifier" ? `<div class="hint">검토위원은 결과를 만든 연구원과 같은 회사 모델로 지정해도, 다른 회사 모델이 있으면 그쪽으로 배정돼요 (교차검증 원칙).</div>` : ""}
        </div>`;
    }
    html += `<button class="primary" id="save-roles">저장</button><span class="saved" id="saved"></span>`;
    html += `<div class="hint">지금 쓸 수 있는 모델: ${roles.providers.map((p) => esc(p.label)).join(", ") || "없음"}. OpenAI·Gemini 키를 넣으면 여기서 고를 수 있어요.</div>`;
    return html;
  },
};

function renderDrawer() {
  $("drawer").innerHTML = VIEWS[view]();
  document.querySelectorAll("[data-project]").forEach((card) =>
    card.addEventListener("click", () => selectProject(Number(card.dataset.project)))
  );
  const exportButton = $("export-note");
  if (exportButton) exportButton.addEventListener("click", exportNote);
  const save = $("save-roles");
  if (save) save.addEventListener("click", saveRoles);
}

async function selectProject(index) {
  selected = index;
  detail = await getJSON(`/threads/${encodeURIComponent(sessionId)}/${index}/detail`).catch(() => null);
  renderAll();
}

async function exportNote() {
  try {
    const note = await getJSON(`/threads/${encodeURIComponent(sessionId)}/${selected}/note`);
    const file = await window.kisto.saveNote(note);
    guide(`연구노트 초안을 저장했어요: <b>${esc(file)}</b>`);
  } catch (err) {
    guide("연구노트를 만들지 못했어요. (" + esc(err.message) + ")");
  }
}

async function saveRoles() {
  const body = {};
  document.querySelectorAll(".role-form").forEach((form) => {
    body[form.dataset.role] = {
      provider: form.querySelector("select").value || null,
      instructions: form.querySelector("textarea").value,
    };
  });
  try {
    roles = await getJSON("/lab/roles", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    $("saved").textContent = "저장했어요 — 다음 대화부터 반영돼요";
  } catch (err) {
    $("saved").textContent = "저장하지 못했어요 (" + err.message + ")";
  }
}

// ── 시작 ──
document.querySelectorAll(".spot").forEach((spot) => {
  const open = () => {
    view = spot.dataset.view;
    renderScene();
    renderDrawer();
  };
  spot.addEventListener("click", open);
  spot.addEventListener("keydown", (e) => (e.key === "Enter" || e.key === " ") && open());
});
$("project").addEventListener("change", (e) => selectProject(Number(e.target.value)));

(async function init() {
  const cfg = await window.kisto.config();
  api = cfg.api;
  token = cfg.token;
  assets = (await window.kisto.labAssets()) || {};
  applyStaticIcons();
  sessionId = await window.kisto.getSession();
  window.kisto.onSessionChanged((id) => {
    sessionId = id;
    selected = null;
    load();
  });
  await load();
  // 위젯에서 대화가 진행되면 연구실도 따라 갱신된다.
  window.addEventListener("focus", () => load({ keepDrawer: true }));
  setInterval(() => load({ keepDrawer: true }), 20000);
})();

// ── 대시보드: 연구실 전체(모든 프로젝트)의 진행을 한 화면에 ──
let tab = "lab";
const COMPANY_COLOR = { Anthropic: "var(--series-1)", OpenAI: "var(--series-2)", Google: "var(--series-3)" };

function fmtSeconds(s) {
  if (!s) return "0초";
  const m = Math.floor(s / 60);
  const sec = Math.round(s % 60);
  return m ? `${m}분 ${sec}초` : `${sec}초`;
}
function fmtWhen(at) {
  return (at || "").slice(5, 16).replace("T", " ");
}

function kpi(label, value, note = "", status = null) {
  return `<div class="panel kpi"><div class="label">${esc(label)}</div><div class="value">${value}</div>
    ${note ? `<div class="note">${note}</div>` : ""}
    ${status ? `<div class="status ${status.kind}">${status.kind === "good" ? "✔" : "⚠"} ${esc(status.text)}</div>` : ""}</div>`;
}

// 한 계열 가로 막대 (값 라벨은 막대 옆, 마우스를 올리면 자세한 값)
function bars(rows, { unit = "", format = (v) => v } = {}) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return `<div class="bars">${rows
    .map((r) => `<div class="bar-row" data-tip="${esc(r.tip || `${r.name}: ${format(r.value)}${unit}`)}">
        <span class="name">${esc(r.name)}</span>
        <span class="track"><span class="fill ${r.value ? "" : "zero"}" style="width:${(r.value / max) * 100}%"></span></span>
        <span class="val">${format(r.value)}${unit}</span>
      </div>`)
    .join("")}</div>`;
}

// ── 조직도·업무 흐름: 누가 누구에게 일을 받아 무엇을 넘겼는지, 지금 누가 일하는지 ──
function fmtAgo(at) {
  const t = new Date(at);
  if (isNaN(t)) return "";
  const min = Math.floor((Date.now() - t.getTime()) / 60000);
  if (min < 1) return "방금";
  if (min < 60) return `${min}분 전`;
  if (min < 60 * 24) return `${Math.floor(min / 60)}시간 전`;
  return `${Math.floor(min / 60 / 24)}일 전`;
}

const ORG_W = 290; // 연구원 카드 크기 (viewBox 좌표)
const ORG_H = 104;
const ORG_POS = {
  manager: [520, 116],
  research_coach: [175, 300],
  analysis_partner: [520, 300],
  writing_coach: [865, 300],
  verifier: [520, 470],
};

function orgModelPills(models) {
  if (!models.length) return `<span class="opill none">아직 모델 호출 없음</span>`;
  return models
    .map((m) => {
      const company = Object.keys(COMPANY_COLOR).find((c) => m.includes(c));
      // 카드 한 줄에 여러 회사가 들어가도록 모델 이름만 보이고, 회사까지 붙은 전체 이름은 마우스를 올리면
      const short = m.split(" · ")[0];
      return `<span class="opill" title="${esc(m)}"><i style="background:${COMPANY_COLOR[company] || "var(--text-muted)"}"></i>${esc(short)}</span>`;
    })
    .join("");
}

function orgNode(n, extra = "", height = ORG_H) {
  const [cx, top] = ORG_POS[n.key];
  const status = n.working
    ? `<b class="live">● 지금 ${esc(n.working.step)} 중 · ${Math.round(n.working.seconds)}초째</b>`
    : n.last
    ? `<span class="ago">${esc(fmtAgo(n.last.at))}</span> ${esc(n.last.text)}`
    : `<span class="ago">아직 일한 기록이 없어요</span>`;
  return `<foreignObject x="${cx - ORG_W / 2}" y="${top}" width="${ORG_W}" height="${height}">
      <div class="onode ${n.working ? "working" : ""}" title="${esc(n.duty)}">
        <div class="av">${avatar(n.key, n.emoji)}</div>
        <div class="body">
          <div class="nm">${esc(n.name)} <span class="place">· ${esc(n.place)}</span></div>
          <div class="st" title="${esc(n.last ? n.last.text : "")}">${status}</div>
          <div class="sm">${esc(n.summary)}${n.seconds ? ` · ${fmtSeconds(n.seconds)}` : ""}</div>
          ${extra}
          <div class="models">${orgModelPills(n.models)}</div>
        </div>
      </div>
    </foreignObject>`;
}

function renderOrg(org) {
  const N = org.nodes;
  const e = org.edges;
  const bottom = (k) => ORG_POS[k][1] + ORG_H;
  const top = (k) => ORG_POS[k][1];
  const x = (k) => ORG_POS[k][0];
  // 검토 선 색: 모두 다른 회사가 검토 → 초록, 하나라도 같은 회사 → 주황, 검토 없음 → 회색
  const reviewKind = (r) => (!r.count ? "none" : r.cross === r.count ? "good" : "warn");
  const flowTo = (k) => (N[k].working ? " flow" : "");
  const label = (lx, ly, text, cls = "") => `<text class="olabel ${cls}" x="${lx}" y="${ly}">${esc(text)}</text>`;

  const producers = ["research_coach", "analysis_partner", "writing_coach"];
  const busY = 258;
  let edges = "";
  // 연구 책임자 → 매니저
  edges += `<path class="oedge req${flowTo("manager")}" d="M520,${62} V${top("manager")}" marker-end="url(#oa-req)"/>`;
  edges += label(530, 94, `대화 ${e.turns}번`);
  // 매니저 → 세 연구원 (요청)
  for (const k of producers) {
    const d = x(k) === 520 ? `M520,${bottom("manager")} V${top(k)}` : `M520,${bottom("manager")} V${busY} H${x(k)} V${top(k)}`;
    edges += `<path class="oedge req${flowTo(k)}" d="${d}" marker-end="url(#oa-req)"/>`;
    edges += label(x(k) + 8, busY + 22, `요청 ${e.requests[k]}회`);
  }
  // 문헌 → 분석 → 집필 (산출물이 넘어간 프로젝트 수)
  const gapL = x("research_coach") + ORG_W / 2;
  const gapR = x("analysis_partner") - ORG_W / 2;
  const handY = top("research_coach") + ORG_H / 2;
  edges += `<path class="oedge hand" d="M${gapL},${handY} H${gapR}" marker-end="url(#oa-hand)"/>`;
  edges += label((gapL + gapR) / 2, handY - 8, "가설", "mid");
  edges += label((gapL + gapR) / 2, handY + 17, `${e.handoffs.research_coach}건`, "mid num");
  const gapL2 = x("analysis_partner") + ORG_W / 2;
  const gapR2 = x("writing_coach") - ORG_W / 2;
  edges += `<path class="oedge hand" d="M${gapL2},${handY} H${gapR2}" marker-end="url(#oa-hand)"/>`;
  edges += label((gapL2 + gapR2) / 2, handY - 8, "결과", "mid");
  edges += label((gapL2 + gapR2) / 2, handY + 17, `${e.handoffs.analysis_partner}건`, "mid num");
  // 세 연구원의 결과 → 외부 검토위원 (점선)
  const vTop = top("verifier");
  const vMid = vTop + ORG_H / 2;
  for (const k of producers) {
    const r = e.reviews[k];
    const kind = reviewKind(r);
    const d = x(k) === 520
      ? `M520,${bottom(k)} V${vTop}`
      : `M${x(k)},${bottom(k)} V${vMid} H${x(k) < 520 ? 520 - ORG_W / 2 : 520 + ORG_W / 2}`;
    edges += `<path class="oedge review ${kind}${flowTo("verifier")}" d="${d}" marker-end="url(#oa-${kind})"/>`;
    const text = r.count ? `검토 ${r.count} · 지적 ${r.issues}` : "검토 없음";
    edges += label(x(k) + 8, bottom(k) + 26, text, kind);
  }

  const totalReviews = producers.reduce((a, k) => a + e.reviews[k].count, 0);
  const cross = producers.reduce((a, k) => a + e.reviews[k].cross, 0);
  const crossNote = totalReviews ? `<div class="sm"><span class="${cross === totalReviews ? "okc" : "warnc"}">다른 회사 모델 검토 ${cross}/${totalReviews}</span></div>` : "";

  const marker = (id) =>
    `<marker id="oa-${id}" viewBox="0 0 10 10" refX="9" refY="5" markerUnits="userSpaceOnUse" markerWidth="13" markerHeight="13" orient="auto-start-reverse">
       <path class="ohead ${id}" d="M0,0 L10,5 L0,10 z"/></marker>`;

  return `<svg class="org" viewBox="0 0 1040 596" role="img" aria-label="연구실 조직도와 업무 흐름">
      <defs>${["req", "hand", "good", "warn", "none"].map(marker).join("")}</defs>
      ${edges}
      <foreignObject x="${520 - 130}" y="0" width="260" height="62">
        <div class="onode pi"><div class="av">🎓</div><div class="body">
          <div class="nm">연구 책임자 (나)</div>
          <div class="st">주제와 해석을 정하고, 결과를 판단</div></div></div>
      </foreignObject>
      ${orgNode(N.manager)}
      ${producers.map((k) => orgNode(N[k])).join("")}
      ${orgNode(N.verifier, crossNote, crossNote ? ORG_H + 18 : ORG_H)}
    </svg>
    <div class="org-legend">
      <span><i class="lg req"></i>일 요청</span>
      <span><i class="lg hand"></i>산출물 전달 (넘어간 프로젝트 수)</span>
      <span><i class="lg good"></i>교차검증 — 다른 회사 모델</span>
      <span><i class="lg warn"></i>교차검증 — 같은 회사 모델</span>
      <span><b class="live">●</b> 지금 일하는 중</span>
    </div>`;
}

function renderDashboard(d) {
  const t = d.totals;
  const crossRate = t.reviews ? Math.round((t.cross_vendor_reviews / t.reviews) * 100) : 0;
  const crossStatus = !t.reviews
    ? null
    : crossRate === 100
    ? { kind: "good", text: "모든 검토가 다른 회사 모델" }
    : { kind: "warning", text: "API 키를 넣으면 다른 회사 모델이 검토해요" };

  const kpis = [
    kpi("진행 중인 프로젝트", t.projects, `연구실 Lv.${d.level.level} · ${esc(d.level.title)}`),
    kpi("클리어한 단계", `★ ${t.stars}<span class="note"> / ${t.stages_total}</span>`, "프로젝트 × 5단계 중"),
    kpi("찾은 실제 논문", t.papers, "PubMed·OpenAlex 검색"),
    kpi("돌린 분석", t.analyses, t.analyses ? `성공 ${t.analyses_ok}건` : ""),
    kpi("교차검증", t.reviews, t.reviews ? `지적 있음 ${t.review_issues}건` : "아직 없음"),
    kpi("다른 회사 모델 검토 비율", `${crossRate}%`, `${t.cross_vendor_reviews} / ${t.reviews}건`, crossStatus),
    kpi("완성한 초안", t.drafts, "연구자 해석을 반영한 초안"),
    kpi("연구원들이 일한 시간", fmtSeconds(t.agent_seconds), `대화 ${t.turns}번 합계`),
  ].join("");

  const funnel = bars(
    d.funnel.map((f) => ({ name: f.label, value: f.count, tip: `${f.label}까지 클리어한 프로젝트 ${f.count}개` })),
    { unit: "개" }
  );
  const work = bars(d.researchers.map((r) => ({ name: `${r.emoji} ${r.name.replace("연구실 매니저 ", "")}`, value: r.work })), { unit: "건" });
  const time = bars(
    d.researchers.map((r) => ({ name: `${r.emoji} ${r.name.replace("연구실 매니저 ", "")}`, value: r.seconds, tip: `${r.name}: ${fmtSeconds(r.seconds)}` })),
    { format: (v) => fmtSeconds(v) }
  );

  const totalCalls = d.companies.reduce((a, c) => a + c.calls, 0);
  const stack = totalCalls
    ? `<div class="stack">${d.companies
        .filter((c) => c.calls)
        .map((c) => `<span style="flex:${c.calls};background:${COMPANY_COLOR[c.company]}" data-tip="${c.company}: ${c.calls}회 (${Math.round((c.calls / totalCalls) * 100)}%)"></span>`)
        .join("")}</div>`
    : `<div class="stack empty"></div>`;
  const legend = `<table class="legend">${d.companies
    .map((c) => `<tr><td><span class="sw" style="background:${COMPANY_COLOR[c.company]}"></span>${c.company}</td>
        <td class="num">${c.calls}회</td><td class="num">${totalCalls ? Math.round((c.calls / totalCalls) * 100) : 0}%</td></tr>`)
    .join("")}</table>`;

  const projectRows = d.projects.length
    ? [...d.projects].reverse().map((p) => `<tr>
        <td>${esc(p.topic)}</td>
        <td><div class="dots" data-tip="${p.progress.cleared_count}/5 단계 · 다음: ${esc(p.progress.cleared_count === 5 ? "완주" : p.progress.current_label)}">${p.progress.cleared.map((c) => `<i class="${c ? "on" : ""}"></i>`).join("")}</div></td>
        <td class="num">${p.counts.papers}</td><td class="num">${p.counts.analyses}</td><td class="num">${p.counts.reviews}</td>
        <td>${p.counts.draft ? "✓" : ""}</td><td>${esc(fmtWhen(p.created_at))}</td></tr>`).join("")
    : `<tr><td colspan="7" class="empty">아직 프로젝트가 없어요.</td></tr>`;

  const timeline = d.timeline.length
    ? d.timeline.map((e) => `<li><span>${e.icon}</span>
        <span>${esc(e.text)}<div class="proj">${esc(e.project)}${e.seconds ? ` · ${fmtSeconds(e.seconds)}` : ""}</div></span>
        <span class="when">${esc(fmtWhen(e.at))}</span></li>`).join("")
    : `<li><span></span><span class="empty">아직 활동이 없어요. 위젯에서 대화를 시작해 보세요.</span><span></span></li>`;

  $("dashboard").innerHTML = `
    <div class="dash-grid kpis">${kpis}</div>
    <div class="panel org-panel">
      <h3>연구실 조직도 · 업무 흐름</h3>
      <p class="desc">연구원마다 누구에게 일을 받아 무엇을 넘겼는지, 지금 누가 일하는지 — 선 위의 숫자는 전부 저장된 기록에서 셌어요</p>
      <div id="org-body">${renderOrg(d.org)}</div>
    </div>
    <div class="dash-grid two">
      <div class="panel"><h3>단계별 진행 (퍼널)</h3><p class="desc">각 단계까지 클리어한 프로젝트 수</p>${funnel}</div>
      <div class="panel"><h3>회사별 모델 호출</h3><p class="desc">연구원들이 어느 회사 모델을 몇 번 불렀는지 — 교차검증이 여러 회사에 걸쳐 일어나는지 보여줘요</p>${stack}${legend}</div>
    </div>
    <div class="dash-grid two">
      <div class="panel"><h3>연구원별 업무량</h3><p class="desc">찾은 논문·돌린 분석·검토·초안·대화 건수</p>${work}</div>
      <div class="panel"><h3>연구원별 작업 시간</h3><p class="desc">각 연구원이 모델을 불러 일한 시간의 합</p>${time}</div>
    </div>
    <div class="dash-grid two">
      <div class="panel"><h3>프로젝트 현황</h3>
        <table class="proj-table"><thead><tr><th>프로젝트</th><th>5단계</th><th>논문</th><th>분석</th><th>검토</th><th>초안</th><th>시작</th></tr></thead>
        <tbody>${projectRows}</tbody></table></div>
      <div class="panel"><h3>최근 활동</h3><ul class="timeline">${timeline}</ul></div>
    </div>`;
}

// 누군가 일하는 중이면 조직도만 몇 초마다 다시 그린다 (나머지 패널은 20초 주기 그대로 — 스크롤이 튀지 않게)
let orgTimer = null;
async function loadDashboard({ orgOnly = false } = {}) {
  if (!sessionId) return;
  clearTimeout(orgTimer);
  try {
    const d = await getJSON(`/lab/session/${encodeURIComponent(sessionId)}/dashboard`);
    if (orgOnly && $("org-body")) $("org-body").innerHTML = renderOrg(d.org);
    else renderDashboard(d);
    if (d.org.live && tab === "dashboard") orgTimer = setTimeout(() => loadDashboard({ orgOnly: true }), 2500);
  } catch {
    $("dashboard").innerHTML = `<div class="panel empty">대시보드를 불러오지 못했어요. 키스토 서버가 켜져 있는지 확인해 주세요.</div>`;
  }
}

function switchTab(next) {
  tab = next;
  document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  document.querySelector("main").hidden = tab !== "lab";
  $("dashboard").hidden = tab !== "dashboard";
  document.querySelector(".project-pick").style.visibility = tab === "lab" ? "visible" : "hidden";
  if (tab === "dashboard") loadDashboard();
}
document.querySelectorAll(".tab").forEach((b) => b.addEventListener("click", () => switchTab(b.dataset.tab)));

// 막대·점 위에 마우스를 올리면 정확한 값 (data-tip)
document.addEventListener("mousemove", (e) => {
  const target = e.target.closest("[data-tip]");
  const tip = $("tooltip");
  if (!target) {
    tip.hidden = true;
    return;
  }
  tip.textContent = target.dataset.tip;
  tip.hidden = false;
  tip.style.left = Math.min(e.clientX + 14, window.innerWidth - tip.offsetWidth - 8) + "px";
  tip.style.top = e.clientY + 16 + "px";
});
setInterval(() => tab === "dashboard" && loadDashboard(), 20000);
