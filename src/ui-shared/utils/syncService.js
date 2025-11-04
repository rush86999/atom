/**
 * ATOM Sync Service
 * Real-time synchronization for Box files
 * Cross-platform: Next.js & Tauri
 * Production ready: Conflict resolution, batch processing, caching
 */

class SyncService {
  constructor() {
    this.initialized = false;
    this.platform = 'nextjs';
    this.encryptionEnabled = false;
    this.syncInProgress = false;
    this.syncQueue = [];
    this.cache = new Map();
    this.conflictResolver = null;
    this.eventListeners = new Map();
    this.syncInterval = null;
    this.websocketConnection = null;
    this.lastSyncTimestamp = null;
  }

  async initialize(config = {}) {
    if (this.initialized) return true;

    try {
      this.platform = config.platform || 'nextjs';
      this.encryptionEnabled = config.encryptionEnabled || false;
      this.onSyncUpdate = config.onSyncUpdate || null;
      this.conflictResolver = config.conflictResolver || this.defaultConflictResolver;

      // Initialize platform-specific services
      if (this.platform === 'tauri') {
        await this.initializeTauriServices();
      } else {
        await this.initializeWebServices();
      }

      // Start background sync
      this.startBackgroundSync(config.syncInterval || 30000);

      this.initialized = true;
      return true;
    } catch (error) {
      console.error('Sync service initialization failed:', error);
      return false;
    }
  }

  // Initialize Tauri-specific services
  async initializeTauriServices() {
    if (typeof window !== 'undefined' && window.__TAURI__) {
      const { invoke } = window.__TAURI__;
      this.tauri = { invoke };

      // Setup file system watcher for desktop
      this.setupDesktopFileWatcher();
    }
  }

  // Initialize Web-specific services
  async initializeWebServices() {
    // Setup Service Worker for background sync
    if ('serviceWorker' in navigator) {
      await this.setupServiceWorker();
    }

    // Setup IndexedDB for caching
    await this.initializeIndexedDB();
  }

  // Setup desktop file watcher
  async setupDesktopFileWatcher() {
    if (!this.tauri) return;

    try {
      await this.tauri.invoke('setup_file_watcher', {
        path: await this.tauri.invoke('get_atom_sync_directory'),
        onFileChange: (event) => this.handleFileSystemChange(event)
      });
    } catch (error) {
      console.error('File watcher setup failed:', error);
    }
  }

  // Handle file system changes
  async handleFileSystemChange(event) {
    const syncItem = {
      type: 'filesystem',
      action: event.type, // 'created', 'modified', 'deleted'
      path: event.path,
      timestamp: Date.now(),
      platform: this.platform
    };

    await this.addToSyncQueue(syncItem);
    this.emitEvent('fileChanged', syncItem);
  }

  // Setup Service Worker
  async setupServiceWorker() {
    const registration = await navigator.serviceWorker.register('/sw.js');
    
    if (registration.sync) {
      // Register for background sync
      registration.sync.register('box-sync');
    }

    // Listen for messages from Service Worker
    navigator.serviceWorker.addEventListener('message', (event) => {
      if (event.data.type === 'sync-complete') {
        this.handleSyncComplete(event.data.result);
      }
    });
  }

  // Initialize IndexedDB for caching
  async initializeIndexedDB() {
    if (typeof indexedDB === 'undefined') return;

    this.idb = await new Promise((resolve, reject) => {
      const request = indexedDB.open('AtomSyncDB', 1);
      
      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve(request.result);
      
      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        
        // Create object stores
        if (!db.objectStoreNames.contains('files')) {
          db.createObjectStore('files', { keyPath: 'id' });
        }
        
        if (!db.objectStoreNames.contains('syncQueue')) {
          db.createObjectStore('syncQueue', { keyPath: 'id', autoIncrement: true });
        }
        
        if (!db.objectStoreNames.contains('conflicts')) {
          db.createObjectStore('conflicts', { keyPath: 'id' });
        }
      };
    });
  }

  // Add item to sync queue
  async addToSyncQueue(syncItem) {
    syncItem.id = Date.now() + Math.random();
    this.syncQueue.push(syncItem);

    // Cache for immediate access
    this.cache.set(syncItem.id, syncItem);

    // Persist to IndexedDB
    if (this.idb) {
      const transaction = this.idb.transaction(['syncQueue'], 'readwrite');
      const store = transaction.objectStore('syncQueue');
      await store.add(syncItem);
    }

    // Trigger immediate sync if not already in progress
    if (!this.syncInProgress) {
      this.processSyncQueue();
    }
  }

  // Process sync queue
  async processSyncQueue() {
    if (this.syncInProgress || this.syncQueue.length === 0) {
      return;
    }

    this.syncInProgress = true;
    this.emitEvent('syncStarted', { queueLength: this.syncQueue.length });

    try {
      // Process items in batches
      const batchSize = 10;
      while (this.syncQueue.length > 0) {
        const batch = this.syncQueue.splice(0, batchSize);
        
        await this.processBatch(batch);
        
        // Emit progress
        this.emitEvent('syncProgress', {
          processed: batch.length,
          remaining: this.syncQueue.length
        });
      }

      this.lastSyncTimestamp = Date.now();
      this.emitEvent('syncComplete', { timestamp: this.lastSyncTimestamp });
    } catch (error) {
      console.error('Sync processing failed:', error);
      this.emitEvent('syncError', { error: error.message });
    } finally {
      this.syncInProgress = false;
    }
  }

  // Process batch of sync items
  async processBatch(batch) {
    const results = [];
    
    for (const item of batch) {
      try {
        const result = await this.processSyncItem(item);
        results.push({ ...item, success: true, result });
      } catch (error) {
        // Handle conflicts
        if (error.type === 'CONFLICT') {
          const resolution = await this.handleConflict(item, error);
          results.push({ ...item, success: true, result: resolution });
        } else {
          console.error('Sync item failed:', item, error);
          results.push({ ...item, success: false, error: error.message });
        }
      }
    }

    // Update cache and persist results
    await this.updateSyncCache(results);
    return results;
  }

  // Process individual sync item
  async processSyncItem(syncItem) {
    switch (syncItem.type) {
      case 'file_upload':
        return await this.syncFileUpload(syncItem);
      case 'file_download':
        return await this.syncFileDownload(syncItem);
      case 'file_delete':
        return await this.syncFileDelete(syncItem);
      case 'folder_create':
        return await this.syncFolderCreate(syncItem);
      case 'folder_delete':
        return await this.syncFolderDelete(syncItem);
      case 'filesystem':
        return await this.syncFileSystemChange(syncItem);
      default:
        throw new Error(`Unknown sync item type: ${syncItem.type}`);
    }
  }

  // Sync file upload
  async syncFileUpload(syncItem) {
    const { file, folderId, metadata } = syncItem;
    
    // Check if file already exists on server
    const existingFiles = await this.searchFiles(file.name);
    const existingFile = existingFiles.find(f => f.name === file.name);
    
    if (existingFile) {
      // Check for conflict
      if (existingFile.size !== file.size || existingFile.modified_at !== file.lastModified) {
        throw {
          type: 'CONFLICT',
          message: 'File conflict detected',
          localFile: file,
          remoteFile: existingFile
        };
      }
      
      // Files are identical, skip upload
      return { action: 'skipped', reason: 'identical', file: existingFile };
    }

    // Perform upload
    const uploadResult = await this.performFileUpload(file, folderId, metadata);
    
    // Cache result
    this.cache.set(`file_${uploadResult.id}`, uploadResult);
    
    return { action: 'uploaded', file: uploadResult };
  }

  // Sync file download
  async syncFileDownload(syncItem) {
    const { fileId, localPath } = syncItem;
    
    // Get remote file info
    const remoteFile = await this.getRemoteFile(fileId);
    
    // Check if local file exists
    const localFile = await this.getLocalFile(localPath);
    
    if (localFile) {
      // Check for conflict
      if (localFile.size !== remoteFile.size || localFile.lastModified !== remoteFile.modified_at) {
        throw {
          type: 'CONFLICT',
          message: 'File download conflict detected',
          localFile: localFile,
          remoteFile: remoteFile
        };
      }
      
      // Files are identical, skip download
      return { action: 'skipped', reason: 'identical', file: remoteFile };
    }

    // Perform download
    const downloadResult = await this.performFileDownload(fileId, localPath);
    
    // Cache result
    this.cache.set(`file_${fileId}`, remoteFile);
    
    return { action: 'downloaded', file: downloadResult };
  }

  // Handle conflicts
  async handleConflict(syncItem, conflict) {
    const resolution = await this.conflictResolver(syncItem, conflict);
    
    if (resolution.action === 'keep_local') {
      // Upload local version (will overwrite remote)
      return await this.performFileUpload(conflict.localFile, syncItem.folderId, { overwrite: true });
    } else if (resolution.action === 'keep_remote') {
      // Download remote version (will overwrite local)
      return await this.performFileDownload(conflict.remoteFile.id, syncItem.localPath, { overwrite: true });
    } else if (resolution.action === 'keep_both') {
      // Keep both versions (rename local file)
      const newLocalName = this.generateConflictName(conflict.localFile.name);
      conflict.localFile.name = newLocalName;
      return await this.performFileUpload(conflict.localFile, syncItem.folderId);
    } else if (resolution.action === 'merge') {
      // Attempt merge (if applicable)
      return await this.mergeFiles(conflict.localFile, conflict.remoteFile);
    }
    
    throw new Error('Conflict resolution failed');
  }

  // Default conflict resolver
  async defaultConflictResolver(syncItem, conflict) {
    // For now, default to keeping remote version
    return {
      action: 'keep_remote',
      reason: 'Default: keep remote version'
    };
  }

  // Generate conflict name
  generateConflictName(originalName) {
    const parts = originalName.split('.');
    const extension = parts.length > 1 ? `.${parts.pop()}` : '';
    const baseName = parts.join('.');
    return `${baseName} (conflict ${Date.now()})${extension}`;
  }

  // Merge files (simplified - would need file-type specific logic)
  async mergeFiles(localFile, remoteFile) {
    // This is a placeholder for file merging logic
    // In reality, this would depend on file type (documents, images, etc.)
    throw new Error('File merging not implemented for this file type');
  }

  // Start background sync
  startBackgroundSync(intervalMs) {
    if (this.syncInterval) {
      clearInterval(this.syncInterval);
    }

    this.syncInterval = setInterval(async () => {
      if (!this.syncInProgress && this.syncQueue.length > 0) {
        await this.processSyncQueue();
      }
    }, intervalMs);
  }

  // Stop background sync
  stopBackgroundSync() {
    if (this.syncInterval) {
      clearInterval(this.syncInterval);
      this.syncInterval = null;
    }
  }

  // Update sync cache
  async updateSyncCache(results) {
    // Update memory cache
    results.forEach(result => {
      if (result.success) {
        this.cache.set(`sync_${result.id}`, result);
      }
    });

    // Update IndexedDB
    if (this.idb) {
      const transaction = this.idb.transaction(['files'], 'readwrite');
      const store = transaction.objectStore('files');
      
      for (const result of results) {
        if (result.success && result.result.file) {
          await store.put(result.result.file);
        }
      }
    }
  }

  // Event emission
  emitEvent(eventType, data) {
    const listeners = this.eventListeners.get(eventType) || [];
    listeners.forEach(listener => {
      try {
        listener(data);
      } catch (error) {
        console.error('Event listener error:', error);
      }
    });

    // Call global callback
    if (this.onSyncUpdate) {
      this.onSyncUpdate({ type: eventType, ...data });
    }
  }

  // Add event listener
  addEventListener(eventType, listener) {
    if (!this.eventListeners.has(eventType)) {
      this.eventListeners.set(eventType, []);
    }
    this.eventListeners.get(eventType).push(listener);
  }

  // Remove event listener
  removeEventListener(eventType, listener) {
    const listeners = this.eventListeners.get(eventType);
    if (listeners) {
      const index = listeners.indexOf(listener);
      if (index > -1) {
        listeners.splice(index, 1);
      }
    }
  }

  // Get sync status
  getSyncStatus() {
    return {
      initialized: this.initialized,
      platform: this.platform,
      syncInProgress: this.syncInProgress,
      queueLength: this.syncQueue.length,
      lastSyncTimestamp: this.lastSyncTimestamp,
      cacheSize: this.cache.size,
      encryptionEnabled: this.encryptionEnabled
    };
  }

  // Clear cache
  clearCache() {
    this.cache.clear();
    if (this.idb) {
      // Clear IndexedDB caches
      const stores = ['files', 'syncQueue', 'conflicts'];
      stores.forEach(storeName => {
        const transaction = this.idb.transaction([storeName], 'readwrite');
        transaction.objectStore(storeName).clear();
      });
    }
  }

  // Cleanup
  async cleanup() {
    this.stopBackgroundSync();
    this.clearCache();
    
    // Close websocket if open
    if (this.websocketConnection) {
      this.websocketConnection.close();
    }
    
    this.initialized = false;
  }
}

// Create singleton instance
const syncService = new SyncService();

export default syncService;