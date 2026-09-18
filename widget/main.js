// 키스토 바탕화면 위젯 — 투명·최상단 창 하나에 캐릭터와 대화창을 띄운다.
// 캐릭터 영상의 검은 배경은 렌더러에서 WebGL로 투명 처리하고, 투명한 곳은
// 클릭이 바탕화면으로 통과하도록 마우스 무시 모드를 켜고 끈다.
const {
  app,
  BrowserWindow,
  Menu,
  Tray,
  globalShortcut,
  ipcMain,
  screen,
  shell,
} = require("electron");
const fs = require("fs");
const path = require("path");

const WIDTH = 540;
const HEIGHT = 760;
const API = process.env.KISTO_API || "http://127.0.0.1:8420";
const CHARACTER_DIR = path.join(__dirname, "character");

let win = null;
let tray = null;
let drag = null;
let presenter = false; // 발표 모드: 답변마다 어떤 에이전트·모델이 일했는지 보여준다
let labWin = null; // 키스토 연구실 창 (게임 화면)
let sessionId = null; // 위젯이 쓰는 대화 세션 — 연구실 창이 같은 기록을 보여주도록 공유한다

function defaultPosition() {
  const { workArea } = screen.getPrimaryDisplay();
  return {
    x: workArea.x + workArea.width - WIDTH - 16,
    y: workArea.y + workArea.height - HEIGHT,
  };
}

function createWindow() {
  const { x, y } = defaultPosition();
  win = new BrowserWindow({
    x,
    y,
    width: WIDTH,
    height: HEIGHT,
    transparent: true,
    frame: false,
    resizable: false,
    hasShadow: false,
    skipTaskbar: true,
    alwaysOnTop: true,
    icon: path.join(CHARACTER_DIR, "icon.ico"),
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  win.setAlwaysOnTop(true, "floating");
  // 기본은 클릭 통과. 캐릭터나 대화창 위에 마우스가 올라오면 렌더러가 해제한다.
  win.setIgnoreMouseEvents(true, { forward: true });
  win.loadFile("index.html");
  // run.cmd -Chat (바탕화면 바로가기)으로 실행하면 대화창을 펼친 채로 시작한다.
  if (process.argv.includes("--chat")) {
    win.webContents.once("did-finish-load", () => win.webContents.send("kisto:open-chat"));
  }

  // 답변 속 링크는 위젯 안에서 열지 않고 기본 브라우저로 넘긴다.
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//.test(url)) shell.openExternal(url);
    return { action: "deny" };
  });
  win.webContents.on("will-navigate", (event) => event.preventDefault());
}

// 연구실은 투명 위젯과 달리 일반 창이다 — 방 전체를 게임 화면처럼 보여줘야 해서 넓어야 한다.
// Windows는 백그라운드에서 뜬 창이 앞으로 나오는 걸 막는다 — 잠깐 최상단으로 올렸다가 풀어서 확실히 보이게 한다.
function bringToFront(w) {
  if (w.isMinimized()) w.restore();
  w.show();
  w.setAlwaysOnTop(true);
  w.moveTop();
  w.focus();
  setTimeout(() => !w.isDestroyed() && w.setAlwaysOnTop(false), 400);
}

function openLab() {
  if (labWin) {
    bringToFront(labWin);
    return;
  }
  labWin = new BrowserWindow({
    width: 1120,
    height: 720,
    minWidth: 920,
    minHeight: 600,
    show: false,
    title: "키스토 연구실",
    icon: path.join(CHARACTER_DIR, "icon.ico"),
    autoHideMenuBar: true,
    backgroundColor: "#efe6d8",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  labWin.once("ready-to-show", () => bringToFront(labWin));
  labWin.loadFile("lab.html");
  labWin.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//.test(url)) shell.openExternal(url);
    return { action: "deny" };
  });
  labWin.webContents.on("will-navigate", (event) => event.preventDefault());
  labWin.on("closed", () => {
    labWin = null;
  });
}

function toggleVisible() {
  if (!win) return;
  if (win.isVisible()) win.hide();
  else win.showInactive();
}

function buildTrayMenu() {
  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: "보이기 / 숨기기  (Ctrl+Shift+K)", click: toggleVisible },
      { label: "🏠 연구실 열기", click: openLab },
      {
        label: "발표 모드 (에이전트 협업 과정 보기)",
        type: "checkbox",
        checked: presenter,
        click: (item) => {
          presenter = item.checked;
          win.webContents.send("kisto:presenter", presenter);
        },
      },
      {
        label: "위치 초기화",
        click: () => {
          const { x, y } = defaultPosition();
          win.setPosition(x, y);
          win.showInactive();
        },
      },
      {
        label: "새 대화 세션 시작",
        click: () => win.webContents.send("kisto:new-session"),
      },
      { type: "separator" },
      { label: "종료", click: () => app.quit() },
    ])
  );
}

function createTray() {
  tray = new Tray(path.join(CHARACTER_DIR, "icon.ico"));
  tray.setToolTip("키스토");
  buildTrayMenu();
  tray.on("click", toggleVisible);
}

// 백엔드가 처음 뜰 때 만드는 토큰. 이게 있어야 백엔드가 위젯의 요청으로 인정한다
// (아무 웹사이트나 로컬 백엔드를 부르지 못하게 하려는 것).
function readToken() {
  try {
    return fs.readFileSync(path.join(__dirname, "..", "data", ".kisto_token"), "utf-8").trim();
  } catch {
    return "";
  }
}

ipcMain.handle("kisto:config", () => {
  const character = JSON.parse(
    fs.readFileSync(path.join(CHARACTER_DIR, "character.json"), "utf-8")
  );
  return { api: API, token: readToken(), character };
});

ipcMain.on("kisto:open-lab", openLab);
ipcMain.on("kisto:hide", () => win && win.hide());
ipcMain.on("kisto:quit", () => app.quit());
// 연구실 이미지 에셋 설정 (lab-assets/lab.json). 없거나 깨져 있으면 벡터 그림을 쓴다.
ipcMain.handle("kisto:lab-assets", () => {
  try {
    return JSON.parse(fs.readFileSync(path.join(__dirname, "lab-assets", "lab.json"), "utf-8"));
  } catch {
    return {};
  }
});
ipcMain.on("kisto:set-session", (_event, id) => {
  sessionId = id;
  if (labWin) labWin.webContents.send("kisto:session-changed", id);
});
ipcMain.handle("kisto:get-session", () => sessionId);

// 렌더러가 저장해 둔 발표 모드 설정을 알려주면 트레이 메뉴 체크 상태를 맞춘다.
ipcMain.on("kisto:presenter-state", (_event, value) => {
  presenter = !!value;
  if (tray) buildTrayMenu();
});

// 연구노트는 문서 폴더의 "키스토 연구노트"에 저장하고 탐색기로 보여준다.
ipcMain.handle("kisto:save-note", (_event, { filename, markdown }) => {
  const dir = path.join(app.getPath("documents"), "키스토 연구노트");
  fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, path.basename(filename));
  fs.writeFileSync(file, markdown, "utf-8");
  shell.showItemInFolder(file);
  return file;
});

ipcMain.on("kisto:set-ignore", (_event, ignore) => {
  if (win) win.setIgnoreMouseEvents(ignore, { forward: true });
});

// 캐릭터를 끌면 창 전체가 따라 움직인다. -webkit-app-region: drag는 클릭까지
// 먹어버려서 캐릭터 클릭(대화창 열기)과 같이 쓸 수 없으므로 직접 옮긴다.
ipcMain.on("kisto:drag-start", () => {
  const [wx, wy] = win.getPosition();
  drag = { wx, wy, cursor: screen.getCursorScreenPoint() };
});
ipcMain.on("kisto:drag-move", () => {
  if (!drag) return;
  const now = screen.getCursorScreenPoint();
  win.setPosition(drag.wx + now.x - drag.cursor.x, drag.wy + now.y - drag.cursor.y);
});
ipcMain.on("kisto:drag-end", () => {
  drag = null;
});

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", (_event, argv) => {
    if (win) win.showInactive();
    if (argv.includes("--chat") && win) win.webContents.send("kisto:open-chat");
    if (argv.includes("--lab")) openLab();
  });
  app.whenReady().then(() => {
    createWindow();
    createTray();
    globalShortcut.register("CommandOrControl+Shift+K", toggleVisible);
    // run.cmd -Lab 으로 실행하면 연구실 창도 바로 연다.
    if (process.argv.includes("--lab")) openLab();
  });
  app.on("will-quit", () => globalShortcut.unregisterAll());
  // 트레이에 상주하므로 창이 닫혀도 앱은 유지한다 (종료는 트레이 메뉴에서).
  app.on("window-all-closed", (event) => event.preventDefault());
}
