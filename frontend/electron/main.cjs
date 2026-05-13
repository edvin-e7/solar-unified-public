const { app, BrowserWindow, ipcMain, session, shell } = require("electron");
const path = require("node:path");
const { URL } = require("node:url");

const CSP = [
  "default-src 'self'",
  "script-src 'self'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https://*.googleapis.com https://*.ggpht.com https://*.openstreetmap.org https://tile.openstreetmap.org",
  "connect-src 'self' http://localhost:8000 https://solar.googleapis.com https://nominatim.openstreetmap.org https://re.jrc.ec.europa.eu https://generativelanguage.googleapis.com",
  "font-src 'self' data: https://fonts.gstatic.com",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
].join("; ");

const ALLOWED_NAV_HOSTS = new Set(["localhost", "127.0.0.1"]);

function createWindow() {
  const win = new BrowserWindow({
    width: 1400,
    height: 900,
    backgroundColor: "#f5f1ea",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      allowRunningInsecureContent: false,
    },
  });

  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  win.webContents.on("will-navigate", (event, url) => {
    const target = new URL(url);
    if (target.protocol === "file:") return;
    if (!ALLOWED_NAV_HOSTS.has(target.hostname)) event.preventDefault();
  });

  const devUrl = process.env.VITE_DEV_SERVER_URL;
  if (devUrl) {
    win.loadURL(devUrl);
    win.webContents.openDevTools({ mode: "detach" });
  } else {
    win.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  }
}

// IPC handlers for the channels exposed in preload.cjs. Until the renderer-side
// scrapers (Phase 3) are implemented, every channel returns a structured
// "not_implemented" payload instead of crashing with "no handler for channel".
// Register before createWindow so renderer never sees the gap.
const NOT_IMPLEMENTED = (channel) => async () => ({
  ok: false,
  error: "not_implemented",
  channel,
  message: `IPC channel '${channel}' is exposed but no handler is wired yet.`,
});

ipcMain.handle("mrkoll:lookup", NOT_IMPLEMENTED("mrkoll:lookup"));
ipcMain.handle("hitta:lookup", NOT_IMPLEMENTED("hitta:lookup"));
ipcMain.handle("birthday:lookup", NOT_IMPLEMENTED("birthday:lookup"));

app.whenReady().then(() => {
  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        "Content-Security-Policy": [CSP],
      },
    });
  });

  app.on("web-contents-created", (_event, contents) => {
    contents.on("will-attach-webview", (e) => e.preventDefault());
  });

  createWindow();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
