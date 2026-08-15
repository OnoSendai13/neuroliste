const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');
const https = require('https');

let mainWindow = null;
let backendProcess = null;
const BACKEND_PORT = 8000;
const FRONTEND_DEV_PORT = 5173;

function isDev() {
  return process.env.NODE_ENV === 'development' || !app.isPackaged;
}

function getBackendPath() {
  if (isDev()) {
    return path.join(__dirname, '..', 'backend');
  }
  return path.join(process.resourcesPath, 'backend');
}

function getFrontendUrl() {
  if (isDev()) {
    return `http://localhost:${FRONTEND_DEV_PORT}`;
  }
  return `file://${path.join(__dirname, '..', 'frontend', 'dist', 'index.html')}`;
}

// --- Data strategy: userData path per OS ---
function getUserDataPath() {
  // electron.app.getPath('userData') gives:
  // Windows: C:\Users\<user>\AppData\Roaming\Neuroliste
  // macOS: ~/Library/Application Support/Neuroliste
  // Linux: ~/.config/neuroliste
  return app.getPath('userData');
}

function getDbPath() {
  const userDataPath = getUserDataPath();
  return path.join(userDataPath, 'neurologues.db');
}

function getBundledDbPath() {
  // Bundled DB in extraResources (if we include one)
  if (isDev()) {
    return path.join(__dirname, '..', 'backend', 'data', 'neurologues.db');
  }
  return path.join(process.resourcesPath, 'backend', 'data', 'neurologues.db');
}

// --- Corrupt DB handling ---
function isValidSQLite(dbPath) {
  if (!fs.existsSync(dbPath)) return false;
  try {
    const buffer = Buffer.alloc(100);
    const fd = fs.openSync(dbPath, 'r');
    fs.readSync(fd, buffer, 0, 100, 0);
    fs.closeSync(fd);
    return buffer.toString('ascii', 0, 16) === 'SQLite format 3\x00';
  } catch {
    return false;
  }
}

function backupCorruptDb(dbPath) {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const backupPath = `${dbPath}.corrupt.${timestamp}.bak`;
  try {
    fs.copyFileSync(dbPath, backupPath);
    console.log(`Backed up corrupt DB to: ${backupPath}`);
    return backupPath;
  } catch (err) {
    console.error('Failed to backup corrupt DB:', err);
    return null;
  }
}

// --- DB initialization: copy bundled or download ---
async function initializeDatabase() {
  const dbPath = getDbPath();
  const userDataPath = getUserDataPath();
  
  // Ensure userData directory exists
  if (!fs.existsSync(userDataPath)) {
    fs.mkdirSync(userDataPath, { recursive: true });
    console.log(`Created userData directory: ${userDataPath}`);
  }

  // Check if DB already exists and is valid
  if (fs.existsSync(dbPath)) {
    if (isValidSQLite(dbPath)) {
      console.log(`Valid DB found at: ${dbPath}`);
      const isEmpty = await isDatabaseEmpty(dbPath);
      return { dbPath, isFirstLaunch: isEmpty };
    } else {
      console.warn(`Corrupt DB detected at: ${dbPath}`);
      backupCorruptDb(dbPath);
      fs.unlinkSync(dbPath);
    }
  }

  // No valid DB — try to copy bundled DB
  const bundledDbPath = getBundledDbPath();
  if (fs.existsSync(bundledDbPath) && isValidSQLite(bundledDbPath)) {
    console.log(`Copying bundled DB from: ${bundledDbPath}`);
    fs.copyFileSync(bundledDbPath, dbPath);
    console.log(`DB initialized at: ${dbPath}`);
    return { dbPath, isFirstLaunch: true };
  }

  // No bundled DB — will be created by backend on first run
  console.log(`No bundled DB found, backend will create fresh DB at: ${dbPath}`);
  return { dbPath, isFirstLaunch: true };
}

// Check if database has any neurologues (first launch indicator)
async function isDatabaseEmpty(dbPath) {
  return new Promise((resolve) => {
    const sqlite3 = require('better-sqlite3');
    try {
      const db = new sqlite3(dbPath, { readonly: true });
      const row = db.prepare('SELECT COUNT(*) as count FROM neurologues').get();
      db.close();
      resolve(row.count === 0);
    } catch (err) {
      console.error('Error checking DB emptiness:', err);
      resolve(true); // Assume empty on error
    }
  });
}

// --- Migration check (placeholder for future schema changes) ---
function checkAndMigrate(dbPath) {
  // Run migrations using the migration system
  try {
    const { runMigrations } = require('./migrations');
    runMigrations();
  } catch (err) {
    console.error('Migration error:', err);
    // Don't crash the app on migration failure, just log
  }
  return true;
}

function startBackend(dbPath) {
  const backendDir = getBackendPath();
  const pythonExe = isDev() ? 'python3' : path.join(backendDir, 'python', 'python');
  const mainPy = path.join(backendDir, 'main.py');
  
  if (!fs.existsSync(mainPy)) {
    console.error('Backend main.py not found at:', mainPy);
    return null;
  }

  const env = {
    ...process.env,
    PYTHONPATH: backendDir,
    PORT: BACKEND_PORT.toString(),
    DATABASE_URL: `sqlite:///${dbPath.replace(/\\/g, '/')}`,
  };

  const args = ['-m', 'uvicorn', 'main:app', '--host', '0.0.0.0', '--port', BACKEND_PORT.toString()];
  
  console.log('Starting backend:', pythonExe, args.join(' '), 'in', backendDir);
  console.log('Using DB:', dbPath);
  
  const proc = spawn(pythonExe, args, {
    cwd: backendDir,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  proc.stdout.on('data', (data) => {
    console.log(`[backend] ${data}`);
  });

  proc.stderr.on('data', (data) => {
    console.error(`[backend:err] ${data}`);
  });

  proc.on('close', (code) => {
    console.log(`Backend exited with code ${code}`);
    backendProcess = null;
  });

  proc.on('error', (err) => {
    console.error('Failed to start backend:', err);
    backendProcess = null;
  });

  return proc;
}

function waitForBackend(url, timeout = 30000) {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const check = () => {
      fetch(url)
        .then(() => resolve())
        .catch(() => {
          if (Date.now() - start > timeout) {
            reject(new Error('Backend did not start in time'));
          } else {
            setTimeout(check, 500);
          }
        });
    };
    check();
  });
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 700,
    title: 'Neuroliste - RPPS Neurologues',
    icon: path.join(__dirname, '..', 'frontend', 'public', 'icon.svg'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
    show: false,
  });

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  if (isDev()) {
    await waitForBackend(`http://localhost:${BACKEND_PORT}/`);
    mainWindow.loadURL(getFrontendUrl());
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadURL(getFrontendUrl());
  }
}

app.whenReady().then(async () => {
  const { dbPath, isFirstLaunch } = await initializeDatabase();
  await checkAndMigrate(dbPath);
  
  backendProcess = startBackend(dbPath);
  
  if (backendProcess) {
    try {
      await waitForBackend(`http://localhost:${BACKEND_PORT}/`);
      console.log('Backend ready');
    } catch (err) {
      console.error('Backend failed to start:', err);
      dialog.showErrorBox('Erreur de démarrage', 'Le backend n\'a pas pu démarrer. Vérifiez l\'installation.');
      app.quit();
      return;
    }
  }
  
  // If first launch, trigger initial data load
  if (isFirstLaunch) {
    console.log('First launch detected, triggering initial data load...');
    // We'll notify the renderer once window is created
    global.isFirstLaunch = true;
  }
  
  await createWindow();
  
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (backendProcess) {
    backendProcess.kill();
    backendProcess = null;
  }
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  if (backendProcess) {
    backendProcess.kill();
    backendProcess = null;
  }
});

ipcMain.handle('get-app-version', () => {
  return app.getVersion();
});

ipcMain.handle('get-backend-status', async () => {
  try {
    const res = await fetch(`http://localhost:${BACKEND_PORT}/`);
    return { running: res.ok };
  } catch {
    return { running: false };
  }
});

// --- Correction workflow IPC handlers ---
const { exec } = require('child_process');
const util = require('util');
const execAsync = util.promisify(exec);

function getCorrectionsDir() {
  if (isDev()) {
    return path.join(__dirname, '..', 'data', 'corrections');
  }
  return path.join(process.resourcesPath, 'data', 'corrections');
}

ipcMain.handle('corrections:list-pending', async () => {
  const correctionsDir = getCorrectionsDir();
  const pendingPath = path.join(correctionsDir, 'adresse_corrections_pending_review.csv');
  
  if (!fs.existsSync(pendingPath)) {
    return { entries: [], error: 'No pending review file found' };
  }
  
  try {
    const content = fs.readFileSync(pendingPath, 'utf-8');
    const lines = content.trim().split('\n');
    if (lines.length < 2) return { entries: [] };
    
    const headers = lines[0].split(',').map(h => h.replace(/\"/g, ''));
    const entries = lines.slice(1).map(line => {
      const values = line.split(',').map(v => v.replace(/\"/g, ''));
      const entry = {};
      headers.forEach((h, i) => entry[h] = values[i] || '');
      return entry;
    });
    return { entries };
  } catch (err) {
    return { entries: [], error: err.message };
  }
});

ipcMain.handle('corrections:promote-to-confirmed', async (event, id_ppss) => {
  const correctionsDir = getCorrectionsDir();
  const pendingPath = path.join(correctionsDir, 'adresse_corrections_pending_review.csv');
  
  if (!fs.existsSync(pendingPath)) {
    return { success: false, error: 'No pending review file found' };
  }
  
  try {
    const content = fs.readFileSync(pendingPath, 'utf-8');
    const lines = content.trim().split('\n');
    const headers = lines[0];
    const dataLines = lines.slice(1);
    
    // Find and update the entry
    const updatedLines = dataLines.map(line => {
      const values = line.split(',');
      if (values[0] && values[0].replace(/\"/g, '') === id_ppss) {
        // Update status to confirmed and apply_allowed to true
        const statusIdx = headers.split(',').findIndex(h => h.replace(/\"/g, '') === 'status');
        const applyIdx = headers.split(',').findIndex(h => h.replace(/\"/g, '') === 'apply_allowed');
        if (statusIdx >= 0) values[statusIdx] = '"confirmed"';
        if (applyIdx >= 0) values[applyIdx] = '"true"';
      }
      return values.join(',');
    });
    
    const newContent = headers + '\n' + updatedLines.join('\n');
    fs.writeFileSync(pendingPath, newContent, 'utf-8');
    return { success: true };
  } catch (err) {
    return { success: false, error: err.message };
  }
});

ipcMain.handle('corrections:apply-confirmed', async () => {
  const correctionsDir = getCorrectionsDir();
  const pendingPath = path.join(correctionsDir, 'adresse_corrections_pending_review.csv');
  const scriptPath = path.join(__dirname, '..', 'scripts', 'apply_adresse_corrections.py');
  const dbPath = getDbPath();
  
  if (!fs.existsSync(scriptPath)) {
    return { success: false, error: 'Apply script not found' };
  }
  
  try {
    // Run the apply script in dry-run first
    const dryRunCmd = `python3 "${scriptPath}" --db "${dbPath}" --corrections "${pendingPath}" --dry-run`;
    const { stdout: dryOut, stderr: dryErr } = await execAsync(dryRunCmd, { timeout: 120000 });
    
    // Then apply for real
    const applyCmd = `python3 "${scriptPath}" --db "${dbPath}" --corrections "${pendingPath}" --apply --yes-apply`;
    const { stdout: applyOut, stderr: applyErr } = await execAsync(applyCmd, { timeout: 120000 });
    
    return { 
      success: true, 
      dryRun: dryOut,
      apply: applyOut,
      dryRunErrors: dryErr,
      applyErrors: applyErr
    };
  } catch (err) {
    return { success: false, error: err.message, stdout: err.stdout, stderr: err.stderr };
  }
});

ipcMain.handle('corrections:check-updates', async () => {
  const apiUrl = isDev() ? 'http://127.0.0.1:50000' : `http://localhost:${BACKEND_PORT}`;
  try {
    const res = await fetch(`${apiUrl}/api/check-updates`);
    return await res.json();
  } catch (err) {
    return { update_available: false, error: err.message };
  }
});

ipcMain.handle('corrections:trigger-load-data', async () => {
  const apiUrl = isDev() ? 'http://127.0.0.1:50000' : `http://localhost:${BACKEND_PORT}`;
  try {
    const res = await fetch(`${apiUrl}/api/load-data`, { method: 'POST' });
    return await res.json();
  } catch (err) {
    return { success: false, error: err.message };
  }
});

// --- Initial data load with progress ---
ipcMain.handle('initial-load:start', async () => {
  const apiUrl = isDev() ? 'http://127.0.0.1:50000' : `http://localhost:${BACKEND_PORT}`;
  try {
    const res = await fetch(`${apiUrl}/api/load-data`, { method: 'POST' });
    return await res.json();
  } catch (err) {
    return { success: false, error: err.message };
  }
});

ipcMain.handle('initial-load:check-db-empty', async () => {
  const dbPath = getDbPath();
  return { isEmpty: await isDatabaseEmpty(dbPath) };
});