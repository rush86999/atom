import { test, expect, _electron as electron } from '@playwright/test';
import { TestHelpers } from '../utils/test-utils';

test.describe('Desktop App Core Functionality', () => {
  let electronApp: any;
  let mainWindow: any;

  test.beforeAll(async () => {
    // Launch Electron app
    electronApp = await electron.launch({
      args: ['./'],
    });

    mainWindow = await electronApp.firstWindow();
    await mainWindow.waitForLoadState('domcontentloaded');
  });

  test.afterAll(async () => {
    await electronApp.close();
  });

  test('app launches successfully', async () => {
    // Verify app window
    await expect(mainWindow).toBeVisible();
    const title = await mainWindow.title();
    expect(title).toContain('Atom AI Assistant');

    // Check main window size
    const bounds = await mainWindow.evaluate(() => {
      return require('@electron/remote')?.getCurrentWindow()?.bounds;
    });
    expect(bounds.width).toBeGreaterThan(800);
    expect(bounds.height).toBeGreaterThan(600);
  });

  test('navigation menu items function correctly', async () => {
    await mainWindow.click('[data-testid="menu-dashboard"]');
    await mainWindow.waitForSelector('[data-testid="dashboard-active"]');

    await mainWindow.click('[data-testid="menu-tasks"]');
    await mainWindow.waitForSelector('[data-testid="tasks-active"]');

    await mainWindow.click('[data-testid="menu-calendar"]');
    await mainWindow.waitForSelector('[data-testid="calendar-active"]');
  });

  test('system tray functionality', async () => {
    // Test system tray icon
    const trayBounds = await electronApp.evaluate(() => {
      return require('electron').Tray.getBounds();
    });

    expect(trayBounds).toBeDefined();

    // Test tray context menu
    await electronApp.evaluate(() => {
      const { Menu } = require('electron');
      const contextMenu = Menu.buildFromTemplate([
+        { label: 'Show Atom', click: () => console.log('Show') }
+      ]);
+      contextMenu.popup();
+    });
+  });
+
+  test('keyboard shortcuts work', async () => {
+    // Cmd/Ctrl + N for new task
+    if (process.platform === 'darwin') {
+      await mainWindow.keyboard.press('Meta+n');
+    } else {
+      await mainWindow.keyboard.press('Control+n');
+    }
+
+    await mainWindow.waitForSelector('[data-testid="new-task-modal"]');
+
+    // Esc to close modal
+    await mainWindow.keyboard.press('Escape');
+    await mainWindow.waitForSelector('[data-testid="new-task-modal"]', { state: 'detached' });
+  });
+
+  test('desktop notifications work', async () => {
+    // Request permission
+    await mainWindow.evaluate(() => {
+      return Notification.requestPermission();
+    });
+
+    // Create notification
+    await mainWindow.evaluate(() => {
+      new Notification('Test Notification', {
+        body: 'Desktop notification test successful'
+      });
+    });
+
+    // Verify notification was created
+    const hasNotification = await mainWindow.evaluate(() => {
+      return global.__lastNotification__;
+    });
+    expect(hasNotification).toBeTruthy();
+  });
+
+  test('file drag and drop works', async () => {
+    // Create a test file
+    const testFilePath = require('path').join(__dirname, 'test-file.txt');
+
+    // Drag file to drop zone
+    await mainWindow.evaluate((filePath) => {
+      const dropZone = document.querySelector('[data-testid="drop-zone"]');
+      const dataTransfer = {
+        files: [new File(['test content'], 'test-file.txt')]
+      };
+      dropZone.dispatchEvent(new DragEvent('drop', { dataTransfer }));
+    });
+
+    await mainWindow.waitForSelector('[data-testid="file-uploaded"]');
+  });
+
+  test('context menus work', async () => {
+    await mainWindow.click('[data-testid="task-item"]', { button: 'right' });
+
+    const contextMenu = await mainWindow.waitForSelector('[data-testid="context-menu"]');
+    expect(contextMenu).toBeDefined();
+
+    const menuItems = await contextMenu.$$('[data-testid="menu-item"]');
+    expect(menuItems.length).toBeGreaterThan(0);
+  });
+
+  test('window state persistence', async () => {
+    // Maximize window
+    await electronApp.evaluate(() => {
+      const window = require('electron').
