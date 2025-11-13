const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
  platform: process.platform,
  versions: process.versions,
  
  // Window controls
  minimizeWindow: () => ipcRenderer.invoke("minimize-window"),
  maximizeWindow: () => ipcRenderer.invoke("maximize-window"),
  closeWindow: () => ipcRenderer.invoke("close-window"),
  
  // App controls
  quitApp: () => ipcRenderer.invoke("quit-app"),
  
  // File operations
  saveFile: (data) => ipcRenderer.invoke("save-file", data),
  openFile: () => ipcRenderer.invoke("open-file"),
});
