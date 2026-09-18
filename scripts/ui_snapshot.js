// 연구실 창(lab.html)을 실제 설정으로 띄워 자리별 화면과 대시보드를 PNG로 저장한다 (UI 확인용).
// 바탕화면에 창이 잠깐 떴다 사라진다. 백엔드(8420)가 떠 있어야 한다.
//
//   cd widget
//   node_modules\electron\dist\electron.exe ..\scripts\ui_snapshot.js <세션ID> [저장폴더]
//
// 세션 ID는 data/memory_store.json의 키 (예: scripts/e2e.py가 만든 e2e-YYYYMMDD-HHMMSS).
const { app, BrowserWindow, ipcMain } = require("electron");
const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..");
const WIDGET = path.join(ROOT, "widget");
// electron.exe <이 스크립트> <세션ID> [저장폴더]
const [session, outDir = path.join(ROOT, "data", "snapshots")] = process.argv.slice(2);

if (!session) {
  console.error("사용법: electron scripts/ui_snapshot.js <세션ID> [저장폴더]");
  process.exit(1);
}
fs.mkdirSync(outDir, { recursive: true });

const token = fs.readFileSync(path.join(ROOT, "data", ".kisto_token"), "utf-8").trim();
ipcMain.handle("kisto:config", () => ({ api: "http://127.0.0.1:8420", token, character: {} }));
ipcMain.handle("kisto:lab-assets", () =>
  JSON.parse(fs.readFileSync(path.join(WIDGET, "lab-assets", "lab.json"), "utf-8"))
);
ipcMain.handle("kisto:get-session", () => session);
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

app.whenReady().then(async () => {
  const win = new BrowserWindow({
    width: 1120,
    height: 720,
    backgroundColor: "#efe6d8",
    autoHideMenuBar: true,
    webPreferences: { preload: path.join(WIDGET, "preload.js"), contextIsolation: true, sandbox: true },
  });
  const logs = [];
  win.webContents.on("console-message", (e) => logs.push(`${e.level}: ${e.message}`));
  await win.loadFile(path.join(WIDGET, "lab.html"));
  await wait(2500);
  const js = (code) => win.webContents.executeJavaScript(code);
  const shot = async (name) =>
    fs.writeFileSync(path.join(outDir, name), (await win.webContents.capturePage()).toPNG());

  await shot("lab_board.png");
  for (const view of ["library", "bench", "review", "laptop", "team"]) {
    await js(`document.querySelector('.spot[data-view="${view}"]').dispatchEvent(new MouseEvent('click', {bubbles: true}))`);
    await wait(700);
    await shot(`lab_${view}.png`);
  }
  await js(`switchTab("dashboard")`);
  await wait(1500);
  await shot("lab_dashboard.png");
  console.log(`저장: ${outDir}`);
  if (logs.length) console.log("콘솔:\n" + logs.join("\n"));
  app.quit();
});
