const { app, BrowserWindow, dialog, shell } = require('electron');
const { autoUpdater } = require('electron-updater');
const { spawn } = require('child_process');
const fs = require('fs');
const http = require('http');
const net = require('net');
const path = require('path');

const PORT = 8731;   // fixed port: saved settings stay tied to the same address
const URL = `http://127.0.0.1:${PORT}`;
let backend = null;
let win = null;

function log(file, msg) {
  try { fs.appendFileSync(path.join(app.getPath('userData'), file), `[${new Date().toISOString()}] ${msg}\n`); } catch (e) { /* ignore */ }
}

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) app.quit();
app.on('second-instance', () => {
  if (win) { if (win.isMinimized()) win.restore(); win.focus(); }
});

function portBusy() {
  return new Promise((resolve) => {
    const s = net.createServer();
    s.once('error', () => resolve(true));
    s.once('listening', () => s.close(() => resolve(false)));
    s.listen(PORT, '127.0.0.1');
  });
}

function startBackend() {
  const ext = process.platform === 'win32' ? '.exe' : '';
  const binDir = app.isPackaged ? path.join(process.resourcesPath, 'bin') : path.join(__dirname, '..', 'bin');
  const env = { ...process.env, PYTHONUTF8: '1' };
  const pathKey = Object.keys(process.env).find((k) => k.toLowerCase() === 'path') || 'PATH';
  env[pathKey] = binDir + path.delimiter + (process.env[pathKey] || '');
  let cmd, args;
  if (app.isPackaged) {
    cmd = path.join(process.resourcesPath, 'backend', 'kh-server' + ext);
    args = ['--port', String(PORT), '--no-browser'];
  } else {
    cmd = process.env.PYTHON_BIN || (process.platform === 'win32' ? 'python' : 'python3');
    args = [path.join(__dirname, '..', 'launcher.py'), '--port', String(PORT), '--no-browser'];
  }
  backend = spawn(cmd, args, { env, windowsHide: true, cwd: app.getPath('userData'), stdio: ['ignore', 'pipe', 'pipe'] });
  backend.stdout.on('data', (d) => log('backend.log', String(d).trimEnd()));
  backend.stderr.on('data', (d) => log('backend.log', String(d).trimEnd()));
  backend.on('error', (err) => dialog.showErrorBox('KH Drama Studio', 'Backend failed to start: ' + String(err)));
  backend.on('exit', (code) => log('backend.log', 'backend exited with code ' + code));
}

function waitForServer(tries = 120) {
  return new Promise((resolve, reject) => {
    const retry = (n) => (n <= 0 ? reject(new Error('Server did not start')) : setTimeout(() => attempt(n - 1), 500));
    const attempt = (n) => {
      http.get(URL + '/api/version', (r) => { r.resume(); if (r.statusCode === 200) resolve(); else retry(n); })
        .on('error', () => retry(n));
    };
    attempt(tries);
  });
}

function createWindow() {
  win = new BrowserWindow({ width: 1280, height: 820, minWidth: 900, minHeight: 600, title: 'KH Drama Studio', autoHideMenuBar: true });
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (!url.startsWith(URL)) { shell.openExternal(url); return { action: 'deny' }; }
    return { action: 'allow' };
  });
  win.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(
    '<body style="margin:0;display:flex;align-items:center;justify-content:center;height:100vh;font-family:sans-serif;background:#12081f;color:#fff">Loading KH Drama Studio…</body>'));
  win.on('closed', () => { win = null; });
}

function setupUpdates() {
  if (!app.isPackaged || process.platform !== 'win32') return;   // Mac needs a signed app for auto-update
  autoUpdater.on('error', (e) => log('update.log', 'error: ' + ((e && e.stack) || e)));
  autoUpdater.on('update-available', (i) => log('update.log', 'available ' + i.version));
  autoUpdater.on('update-downloaded', (i) => {
    log('update.log', 'downloaded ' + i.version);
    dialog.showMessageBox(win, {
      type: 'info', buttons: ['Restart now', 'Later'], defaultId: 0, cancelId: 1,
      title: 'Update ready', message: `Version ${i.version} is ready.`,
      detail: 'Restart to finish the update. It also installs when you close the app.'
    }).then((r) => { if (r.response === 0) autoUpdater.quitAndInstall(); });
  });
  const check = () => autoUpdater.checkForUpdates().catch((e) => log('update.log', 'check failed: ' + e));
  check();
  setInterval(check, 4 * 60 * 60 * 1000);
}

async function start() {
  createWindow();
  if (await portBusy()) {
    dialog.showErrorBox('KH Drama Studio', `Port ${PORT} is already in use. Close the other copy of the app (or any program using that port) and try again.`);
    return app.quit();
  }
  startBackend();
  try { await waitForServer(); } catch (e) {
    dialog.showErrorBox('KH Drama Studio', 'The server did not start. See: ' + path.join(app.getPath('userData'), 'backend.log'));
    return app.quit();
  }
  if (win) win.loadURL(URL);
  setupUpdates();
}

app.on('window-all-closed', () => app.quit());
app.on('before-quit', () => { if (backend) backend.kill(); });
app.on('quit', () => { if (backend) backend.kill(); });
if (gotLock) app.whenReady().then(start);