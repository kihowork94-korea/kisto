const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("kisto", {
  config: () => ipcRenderer.invoke("kisto:config"),
  setIgnoreMouse: (ignore) => ipcRenderer.send("kisto:set-ignore", ignore),
  dragStart: () => ipcRenderer.send("kisto:drag-start"),
  dragMove: () => ipcRenderer.send("kisto:drag-move"),
  dragEnd: () => ipcRenderer.send("kisto:drag-end"),
  onNewSession: (callback) => ipcRenderer.on("kisto:new-session", () => callback()),
  onPresenter: (callback) => ipcRenderer.on("kisto:presenter", (_e, value) => callback(value)),
  syncPresenter: (value) => ipcRenderer.send("kisto:presenter-state", value),
  saveNote: (note) => ipcRenderer.invoke("kisto:save-note", note),
  openLab: () => ipcRenderer.send("kisto:open-lab"),
  hide: () => ipcRenderer.send("kisto:hide"),
  quit: () => ipcRenderer.send("kisto:quit"),
  labAssets: () => ipcRenderer.invoke("kisto:lab-assets"),
  setSession: (id) => ipcRenderer.send("kisto:set-session", id),
  getSession: () => ipcRenderer.invoke("kisto:get-session"),
  onSessionChanged: (callback) => ipcRenderer.on("kisto:session-changed", (_e, id) => callback(id)),
});
