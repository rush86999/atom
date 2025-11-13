#!/usr/bin/env node

/**
 * Atom Project - Desktop Application (Electron)
 * Main Process and Desktop Integration

 * CRITICAL IMPLEMENTATION - Week 1
 * Priority: 🔴 HIGH
 * Objective: Create desktop app using shared components
 * Timeline: 32 hours development + 8 hours testing

 * This is the main entry point for the Electron desktop application.
 * It uses the shared React components and adds desktop-specific features
 * like system tray, notifications, and file system access.
 */

import { app, BrowserWindow, Menu, Tray, ipcMain, nativeTheme, shell } from 'electron';
import * as path from 'path';
import * as fs from 'fs';
import * as os from 'os';

// Import shared types
import { AppConfig } from '../types/app';

// Application configuration
const config: AppConfig = {
  appType: 'desktop',
  version: '1.0.0',
  user: {
    id: 'desktop-user',
    name: os.userInfo().username
  },
  websocket: {
    url: process.env.WEBSOCKET_URL || 'ws://localhost:5058'
  },
  aiAgent: {
    id: 'default-ai-agent',
    name: 'Atom AI Assistant'
  },
  desktop: {
    autoStart: true,
    minimizeToTray: true,
    showNotifications: true,
    systemIntegration: true
  },
  status: {
    health: 'Starting...'
  }
};

// Global variables
let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let isQuitting = false;

// App configuration
const isDev = process.env.NODE_ENV === 'development';
const appPath = isDev 
  ? 'http://localhost:3000' 
  : `file://${path.join(__dirname, '../build/index.html')}`;

/**
 * Create Main Window
 */
const createMainWindow = (): BrowserWindow => {
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      enableRemoteModule: false,
      preload: path.join(__dirname, 'preload.js')
    },
    icon: path.join(__dirname, 'assets/icon.png'),
    show: false,
    titleBarStyle: 'hiddenInset',
    titleBarOverlay: {
      color: '#FFFFFF',
      symbolColor: '#000000'
    }
  });

  // Load the app
  win.loadURL(appPath);

  // Show window when ready
  win.once('ready-to-show', () => {
    win.show();
    win.focus();
  });

  // Handle window closed
  win.on('closed', () => {
    mainWindow = null;
  });

  // Handle window minimize to tray
  win.on('minimize', (event) => {
    if (config.desktop?.minimizeToTray) {
      event.preventDefault();
      win.hide();
    }
  });

  // Open dev tools in development
  if (isDev) {
    win.webContents.openDevTools();
  }

  return win;
};

/**
 * Create System Tray
 */
const createTray = (): void => {
  const iconPath = path.join(__dirname, 'assets/tray-icon.png');
  tray = new Tray(iconPath);

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Show Atom AI',
      click: () => {
        mainWindow?.show();
        mainWindow?.focus();
      }
    },
    { type: 'separator' },
    {
      label: 'New Conversation',
      click: () => {
        mainWindow?.webContents.send('new-conversation');
      }
    },
    {
      label: 'Settings',
      click: () => {
        mainWindow?.webContents.send('open-settings');
      }
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => {
        isQuitting = true;
        app.quit();
      }
    }
  ]);

  tray.setToolTip('Atom AI Assistant');
  tray.setContextMenu(contextMenu);

  // Handle tray double click
  tray.on('double-click', () => {
    mainWindow?.show();
    mainWindow?.focus();
  });
};

/**
 * Create Application Menu
 */
const createAppMenu = (): void => {
  const template: Electron.MenuItemConstructorOptions[] = [
    // macOS App Menu
    ...(process.platform === 'darwin' ? [{
      label: app.getName(),
      submenu: [
        { role: 'about' },
        { type: 'separator' },
        { role: 'services' },
        { type: 'separator' },
        { role: 'hide' },
        { role: 'hideothers' },
        { role: 'unhide' },
        { type: 'separator' },
        { role: 'quit' }
      ]
    }] : []),

    // File Menu
    {
      label: 'File',
      submenu: [
        {
          label: 'New Conversation',
          accelerator: 'CmdOrCtrl+N',
          click: () => {
            mainWindow?.webContents.send('new-conversation');
          }
        },
        {
          label: 'Save Conversation',
          accelerator: 'CmdOrCtrl+S',
          click: () => {
            mainWindow?.webContents.send('save-conversation');
          }
        },
        {
          label: 'Export Conversation',
          accelerator: 'CmdOrCtrl+E',
          click: () => {
            mainWindow?.webContents.send('export-conversation');
          }
        },
        { type: 'separator' },
        {
          label: 'Import Conversation',
          accelerator: 'CmdOrCtrl+I',
          click: () => {
            mainWindow?.webContents.send('import-conversation');
          }
        },
        { type: 'separator' },
        ...(process.platform === 'darwin' ? [] : [
          {
            label: 'Quit',
            accelerator: 'CmdOrCtrl+Q',
            click: () => {
              isQuitting = true;
              app.quit();
            }
          }
        ])
      ]
    },

    // Edit Menu
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
        { role: 'selectall' }
      ]
    },

    // View Menu
    {
      label: 'View',
      submenu: [
        {
          label: 'Zoom In',
          accelerator: 'CmdOrCtrl+Plus',
          click: () => {
            mainWindow?.webContents.send('zoom-in');
          }
        },
        {
          label: 'Zoom Out',
          accelerator: 'CmdOrCtrl+-',
          click: () => {
            mainWindow?.webContents.send('zoom-out');
          }
        },
        {
          label: 'Actual Size',
          accelerator: 'CmdOrCtrl+0',
          click: () => {
            mainWindow?.webContents.send('actual-size');
          }
        },
        { type: 'separator' },
        {
          label: 'Toggle Developer Tools',
          accelerator: 'F12',
          click: () => {
            mainWindow?.webContents.toggleDevTools();
          }
        }
      ]
    },

    // Window Menu
    {
      label: 'Window',
      submenu: [
        { role: 'minimize' },
        { role: 'close' },
        ...(process.platform === 'darwin' ? [
          { type: 'separator' },
          { role: 'front' },
          { type: 'separator' },
          { role: 'window' }
        ] : [])
      ]
    },

    // Help Menu
    {
      label: 'Help',
      submenu: [
        {
          label: 'About Atom AI',
          click: () => {
            shell.openExternal('https://atom.ai');
          }
        },
        {
          label: 'Documentation',
          click: () => {
            shell.openExternal('https://docs.atom.ai');
          }
        },
        {
          label: 'Support',
          click: () => {
            shell.openExternal('https://support.atom.ai');
          }
        },
        {
          label: 'Report Issue',
          click: () => {
            shell.openExternal('https://github.com/atom/issues');
          }
        },
        { type: 'separator' },
        {
          label: 'Check for Updates',
          click: () => {
            mainWindow?.webContents.send('check-updates');
          }
        }
      ]
    }
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
};

/**
 * Setup IPC Handlers
 */
const setupIPC = (): void => {
  // Window management
  ipcMain.handle('minimize-window', () => {
    mainWindow?.minimize();
  });

  ipcMain.handle('maximize-window', () => {
    if (mainWindow?.isMaximized()) {
      mainWindow.unmaximize();
    } else {
      mainWindow?.maximize();
    }
  });

  ipcMain.handle('close-window', () => {
    mainWindow?.close();
  });

  // System information
  ipcMain.handle('get-system-info', () => {
    return {
      platform: process.platform,
      version: app.getVersion(),
      arch: process.arch,
      electronVersion: process.versions.electron,
      nodeVersion: process.versions.node,
      chromeVersion: process.versions.chrome
    };
  });

  ipcMain.handle('get-app-config', () => {
    return config;
  });

  // File operations
  ipcMain.handle('save-file', async (event, data: { content: string; filename: string }) => {
    try {
      const result = await saveFileDialog(data.filename, data.content);
      return { success: true, path: result };
    } catch (error) {
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle('open-file', async (event, filters?: Electron.FileFilter[]) => {
    try {
      const result = await openFileDialog(filters);
      return { success: true, path: result };
    } catch (error) {
      return { success: false, error: error.message };
    }
  });

  // Notifications
  ipcMain.handle('show-notification', (event, notification: Electron.NotificationConstructorOptions) => {
    if (config.desktop?.showNotifications) {
      const n = new (require('electron').Notification)(notification);
      n.show();
      return true;
    }
    return false;
  });

  // External URLs
  ipcMain.handle('open-external-url', (event, url: string) => {
    shell.openExternal(url);
  });
};

/**
 * Show Save File Dialog
 */
const saveFileDialog = async (defaultFilename: string, content: string): Promise<string> => {
  const { dialog } = require('electron');
  
  const result = await dialog.showSaveDialog(mainWindow!, {
    defaultPath: defaultFilename,
    filters: [
      { name: 'JSON Files', extensions: ['json'] },
      { name: 'Text Files', extensions: ['txt'] },
      { name: 'All Files', extensions: ['*'] }
    ]
  });

  if (result.canceled || !result.filePath) {
    throw new Error('Dialog canceled');
  }

  fs.writeFileSync(result.filePath, content, 'utf8');
  return result.filePath;
};

/**
 * Show Open File Dialog
 */
const openFileDialog = async (filters?: Electron.FileFilter[]): Promise<string> => {
  const { dialog } = require('electron');
  
  const result = await dialog.showOpenDialog(mainWindow!, {
    filters: filters || [
      { name: 'JSON Files', extensions: ['json'] },
      { name: 'Text Files', extensions: ['txt'] },
      { name: 'All Files', extensions: ['*'] }
    ],
    properties: ['openFile']
  });

  if (result.canceled || result.filePaths.length === 0) {
    throw new Error('Dialog canceled');
  }

  return result.filePaths[0];
};

/**
 * Setup Auto Start
 */
const setupAutoStart = (): void => {
  if (!config.desktop?.autoStart) {
    return;
  }

  const loginItemSettings = app.getLoginItemSettings();
  
  if (!loginItemSettings.openAtLogin) {
    app.setLoginItemSettings({
      openAtLogin: true,
      openAsHidden: config.desktop?.minimizeToTray
    });
  }
};

/**
 * App Event Handlers
 */

// When Electron has finished initialization
app.whenReady().then(() => {
  console.log('Desktop app starting...');
  
  // Set app user model ID (for notifications)
  app.setAppUserModelId('com.atom.ai.desktop');
  
  // Create main window
  mainWindow = createMainWindow();
  
  // Create system tray
  if (config.desktop?.minimizeToTray) {
    createTray();
  }
  
  // Create app menu
  createAppMenu();
  
  // Setup IPC handlers
  setupIPC();
  
  // Setup auto start
  setupAutoStart();
  
  console.log('Desktop app ready');
});

// When all windows are closed
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// Before app quits
app.on('before-quit', () => {
  isQuitting = true;
});

// When app is activated (macOS)
app.on('activate', () => {
  if (BrowserWindow.getAll().length === 0) {
    mainWindow = createMainWindow();
  }
  mainWindow?.show();
});

// Handle deep links (for opening conversations)
app.setAsDefaultProtocolClient('atom-ai');

app.on('open-url', (event, url) => {
  event.preventDefault();
  mainWindow?.webContents.send('open-url', url);
});

// Handle certificate errors (for development)
if (isDev) {
  app.on('certificate-error', (event, webContents, url, error, certificate, callback) => {
    if (url.includes('localhost')) {
      event.preventDefault();
      callback(true);
    }
  });
}

// Handle security warnings in development
if (isDev) {
  app.commandLine.appendSwitch('ignore-certificate-errors', 'true');
}

console.log('Desktop app process started');
console.log('Configuration:', config);