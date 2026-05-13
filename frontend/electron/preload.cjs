const { contextBridge, ipcRenderer } = require("electron");

// Exposes the Cloudflare-blocked scrapers (mrkoll, hitta, birthday) to the renderer.
// Phase 3 populates the actual handlers in electron/main.cjs ipcMain.handle() calls.
contextBridge.exposeInMainWorld("solprojektApi", {
  mrkollLookup: (address) => ipcRenderer.invoke("mrkoll:lookup", address),
  hittaLookup: (address) => ipcRenderer.invoke("hitta:lookup", address),
  birthdayLookup: (personId) => ipcRenderer.invoke("birthday:lookup", personId),
});
