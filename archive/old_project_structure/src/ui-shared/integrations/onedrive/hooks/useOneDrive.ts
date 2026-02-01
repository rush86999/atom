/**
 * OneDrive React Hooks
 * Custom React hooks for OneDrive integration
 * State management, API interactions, and data fetching
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { OneDriveAPIClient, OneDriveAPITools } from '../utils/oneDriveAPI';
import {
  OneDriveFile,
  OneDriveFolder,
  OneDriveSearchQuery,
  AtomOneDriveIngestionConfig,
  ONEDRIVE_DEFAULT_CONFIG,
} from '../types';

// Hook types
interface UseOneDriveOptions {
  accessToken: string;
  refreshToken?: string;
  onTokenRefresh?: (newToken: string) => Promise<string>;
  initialConfig?: Partial<AtomOneDriveIngestionConfig>;
}

interface UseOneDriveState {
  client: OneDriveAPIClient | null;
  loading: boolean;
  error: string | null;
  connected: boolean;
  driveInfo: any;
  currentFolder: OneDriveFolder | null;
  files: OneDriveFile[];
  folders: OneDriveFolder[];
  searchResults: OneDriveFile[];
  searchLoading: boolean;
  config: AtomOneDriveIngestionConfig;
}

interface UseFileOperationsState {
  uploading: boolean;
  uploadProgress: { [key: string]: number };
  downloading: boolean;
  creatingFolder: boolean;
  deleting: boolean;
  moving: boolean;
  copying: boolean;
}

/**
 * Main OneDrive hook for managing connection and basic operations
 */
export const useOneDrive = (options: UseOneDriveOptions) => {
  const [state, setState] = useState<UseOneDriveState>({
    client: null,
    loading: false,
    error: null,
    connected: false,
    driveInfo: null,
    currentFolder: null,
    files: [],
    folders: [],
    searchResults: [],
    searchLoading: false,
    config: { ...ONEDRIVE_DEFAULT_CONFIG, ...options.initialConfig },
  });

  // Initialize client
  useEffect(() => {
    if (options.accessToken) {
      try {
        const client = OneDriveAPITools.createClient(
          options.accessToken,
          options.refreshToken,
          options.onTokenRefresh
        );

        setState(prev => ({
          ...prev,
          client,
          connected: OneDriveAPITools.validateAccessToken(options.accessToken),
        }));
      } catch (error) {
        setState(prev => ({
          ...prev,
          error: error instanceof Error ? error.message : 'Failed to initialize OneDrive client',
          connected: false,
        }));
      }
    }
  }, [options.accessToken, options.refreshToken, options.onTokenRefresh]);

  // Initialize drive info
  const initializeDrive = useCallback(async () => {
    if (!state.client) return;

    setState(prev => ({ ...prev, loading: true, error: null }));

    try {
      const driveInfo = await state.client.get('/me/drive');
      const rootContents = await state.client.get('/me/drive/root/children');

      const files = rootContents.value.filter((item: any) => !item.folder);
      const folders = rootContents.value.filter((item: any) => item.folder);

      setState(prev => ({
        ...prev,
        loading: false,
        driveInfo,
        files,
        folders,
        currentFolder: null,
      }));
    } catch (error) {
      setState(prev => ({
        ...prev,
        loading: false,
        error: error instanceof Error ? error.message : 'Failed to load OneDrive',
      }));
    }
  }, [state.client]);

  // Navigate to folder
  const navigateToFolder = useCallback(async (folder: OneDriveFolder) => {
    if (!state.client) return;

    setState(prev => ({ ...prev, loading: true, error: null }));

    try {
      const contents = await state.client.getFolderContents(folder.id);

      setState(prev => ({
        ...prev,
        loading: false,
        currentFolder: folder,
        files: contents.files,
        folders: contents.folders,
        searchResults: [],
      }));
    } catch (error) {
      setState(prev => ({
        ...prev,
        loading: false,
        error: error instanceof Error ? error.message : 'Failed to navigate to folder',
      }));
    }
  }, [state.client]);

  // Navigate back to parent
  const navigateUp = useCallback(async () => {
    if (!state.client || !state.currentFolder) return;

    if (state.currentFolder.parentReference?.id) {
      const parentFolder = {
        id: state.currentFolder.parentReference.id,
        name: state.currentFolder.parentReference.path?.split('/').pop() || 'Parent',
        webUrl: '',
        createdDateTime: '',
        lastModifiedDateTime: '',
        parentReference: {},
        folder: { childCount: 0 },
        size: 0,
      };

      await navigateToFolder(parentFolder);
    } else {
      // Go to root
      await initializeDrive();
    }
  }, [state.client, state.currentFolder, navigateToFolder, initializeDrive]);

  // Search files
  const searchFiles = useCallback(async (query: OneDriveSearchQuery) => {
    if (!state.client) return;

    setState(prev => ({ ...prev, searchLoading: true, error: null }));

    try {
      const results = await state.client.searchFiles(query);
      
      setState(prev => ({
        ...prev,
        searchLoading: false,
        searchResults: results.files,
      }));
    } catch (error) {
      setState(prev => ({
        ...prev,
        searchLoading: false,
        error: error instanceof Error ? error.message : 'Search failed',
      }));
    }
  }, [state.client]);

  // Refresh current view
  const refresh = useCallback(async () => {
    if (state.currentFolder) {
      await navigateToFolder(state.currentFolder);
    } else {
      await initializeDrive();
    }
  }, [state.currentFolder, navigateToFolder, initializeDrive]);

  // Update configuration
  const updateConfig = useCallback((newConfig: Partial<AtomOneDriveIngestionConfig>) => {
    setState(prev => ({
      ...prev,
      config: { ...prev.config, ...newConfig },
    }));
  }, []);

  return {
    ...state,
    initializeDrive,
    navigateToFolder,
    navigateUp,
    searchFiles,
    refresh,
    updateConfig,
  };
};

/**
 * Hook for file operations (upload, download, delete, etc.)
 */
export const useFileOperations = (client: OneDriveAPIClient | null) => {
  const [state, setState] = useState<UseFileOperationsState>({
    uploading: false,
    uploadProgress: {},
    downloading: false,
    creatingFolder: false,
    deleting: false,
    moving: false,
    copying: false,
  });

  const uploadProgressCallbacks = useRef<Map<string, (progress: number) => void>>(new Map());

  // Upload file
  const uploadFile = useCallback(async (
    file: File,
    folderId?: string,
    onProgress?: (progress: number) => void
  ) => {
    if (!client) throw new Error('OneDrive client not available');

    setState(prev => ({ ...prev, uploading: true }));

    try {
      const uploadId = Math.random().toString(36).substr(2, 9);
      
      if (onProgress) {
        uploadProgressCallbacks.current.set(uploadId, onProgress);
      }

      const uploadedFile = await client.uploadFile(file, folderId, (progress) => {
        setState(prev => ({
          ...prev,
          uploadProgress: { ...prev.uploadProgress, [uploadId]: progress },
        }));
        
        const callback = uploadProgressCallbacks.current.get(uploadId);
        if (callback) {
          callback(progress);
        }
      });

      uploadProgressCallbacks.current.delete(uploadId);
      
      setState(prev => {
        const newProgress = { ...prev.uploadProgress };
        delete newProgress[uploadId];
        return {
          ...prev,
          uploading: false,
          uploadProgress: newProgress,
        };
      });

      return uploadedFile;
    } catch (error) {
      setState(prev => ({ ...prev, uploading: false }));
      throw error;
    }
  }, [client]);

  // Download file
  const downloadFile = useCallback(async (fileId: string): Promise<Blob> => {
    if (!client) throw new Error('OneDrive client not available');

    setState(prev => ({ ...prev, downloading: true }));

    try {
      const blob = await client.downloadFile(fileId);
      setState(prev => ({ ...prev, downloading: false }));
      return blob;
    } catch (error) {
      setState(prev => ({ ...prev, downloading: false }));
      throw error;
    }
  }, [client]);

  // Create folder
  const createFolder = useCallback(async (
    name: string,
    parentFolderId?: string
  ): Promise<OneDriveFolder> => {
    if (!client) throw new Error('OneDrive client not available');

    setState(prev => ({ ...prev, creatingFolder: true }));

    try {
      const folder = await client.createFolder(name, parentFolderId);
      setState(prev => ({ ...prev, creatingFolder: false }));
      return folder;
    } catch (error) {
      setState(prev => ({ ...prev, creatingFolder: false }));
      throw error;
    }
  }, [client]);

  // Delete item
  const deleteItem = useCallback(async (itemId: string): Promise<void> => {
    if (!client) throw new Error('OneDrive client not available');

    setState(prev => ({ ...prev, deleting: true }));

    try {
      await client.deleteItem(itemId);
      setState(prev => ({ ...prev, deleting: false }));
    } catch (error) {
      setState(prev => ({ ...prev, deleting: false }));
      throw error;
    }
  }, [client]);

  // Move item
  const moveItem = useCallback(async (
    itemId: string,
    parentId: string,
    newName?: string
  ): Promise<OneDriveFile> => {
    if (!client) throw new Error('OneDrive client not available');

    setState(prev => ({ ...prev, moving: true }));

    try {
      const movedItem = await client.moveItem(itemId, parentId, newName);
      setState(prev => ({ ...prev, moving: false }));
      return movedItem;
    } catch (error) {
      setState(prev => ({ ...prev, moving: false }));
      throw error;
    }
  }, [client]);

  // Copy item
  const copyItem = useCallback(async (
    itemId: string,
    parentId: string,
    newName?: string
  ): Promise<OneDriveFile> => {
    if (!client) throw new Error('OneDrive client not available');

    setState(prev => ({ ...prev, copying: true }));

    try {
      const copiedItem = await client.copyItem(itemId, parentId, newName);
      setState(prev => ({ ...prev, copying: false }));
      return copiedItem;
    } catch (error) {
      setState(prev => ({ ...prev, copying: false }));
      throw error;
    }
  }, [client]);

  return {
    ...state,
    uploadFile,
    downloadFile,
    createFolder,
    deleteItem,
    moveItem,
    copyItem,
  };
};

/**
 * Hook for OneDrive search functionality
 */
export const useOneDriveSearch = (client: OneDriveAPIClient | null) => {
  const [searchResults, setSearchResults] = useState<OneDriveFile[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [lastQuery, setLastQuery] = useState<OneDriveSearchQuery | null>(null);

  const search = useCallback(async (query: OneDriveSearchQuery) => {
    if (!client) return;

    setSearchLoading(true);
    setSearchError(null);
    setLastQuery(query);

    try {
      const results = await client.searchFiles(query);
      setSearchResults(results.files);
    } catch (error) {
      setSearchError(error instanceof Error ? error.message : 'Search failed');
      setSearchResults([]);
    } finally {
      setSearchLoading(false);
    }
  }, [client]);

  const clearResults = useCallback(() => {
    setSearchResults([]);
    setSearchError(null);
    setLastQuery(null);
  }, []);

  return {
    searchResults,
    searchLoading,
    searchError,
    lastQuery,
    search,
    clearResults,
  };
};

/**
 * Hook for OneDrive sync operations with ATOM
 */
export const useOneDriveSync = (
  client: OneDriveAPIClient | null,
  atomIngestionPipeline?: any
) => {
  const [syncState, setSyncState] = useState({
    syncing: false,
    progress: {
      total: 0,
      processed: 0,
      percentage: 0,
      currentFile: '',
      errors: 0,
    },
    results: [] as any[],
    error: null as string | null,
  });

  const syncFolder = useCallback(async (
    folderId: string = 'root',
    options: {
      includeSubfolders?: boolean;
      fileTypes?: string[];
      maxFileSize?: number;
      batchSize?: number;
    } = {}
  ) => {
    if (!client || !atomIngestionPipeline) {
      throw new Error('OneDrive client and ATOM ingestion pipeline are required');
    }

    setSyncState({
      syncing: true,
      progress: { total: 0, processed: 0, percentage: 0, currentFile: '', errors: 0 },
      results: [],
      error: null,
    });

    try {
      // Get all files to process
      const allFiles: OneDriveFile[] = [];
      const processFolder = async (id: string) => {
        const contents = await client.getFolderContents(id);
        allFiles.push(...contents.files);

        if (options.includeSubfolders) {
          for (const folder of contents.folders) {
            await processFolder(folder.id);
          }
        }
      };

      await processFolder(folderId);

      // Filter files based on options
      let filesToProcess = allFiles;

      if (options.fileTypes && options.fileTypes.length > 0) {
        filesToProcess = filesToProcess.filter(file => 
          options.fileTypes!.includes(file.mimeType)
        );
      }

      if (options.maxFileSize) {
        filesToProcess = filesToProcess.filter(file => 
          file.size <= options.maxFileSize!
        );
      }

      setSyncState(prev => ({
        ...prev,
        progress: { ...prev.progress, total: filesToProcess.length },
      }));

      // Process files
      const results = [];
      const batchSize = options.batchSize || 50;

      for (let i = 0; i < filesToProcess.length; i++) {
        const file = filesToProcess[i];

        try {
          // Download file content
          const content = await client.downloadFile(file.id);

          // Process through ATOM pipeline
          const result = await atomIngestionPipeline.processDocument({
            content,
            metadata: {
              source: 'onedrive',
              fileId: file.id,
              fileName: file.name,
              mimeType: file.mimeType,
              size: file.size,
              lastModified: file.lastModifiedDateTime,
            },
          });

          results.push(result);
        } catch (error) {
          console.error(`Failed to process file ${file.name}:`, error);
          setSyncState(prev => ({
            ...prev,
            progress: { ...prev.progress, errors: prev.progress.errors + 1 },
          }));
        }

        // Update progress
        const processed = i + 1;
        setSyncState(prev => ({
          ...prev,
          progress: {
            total: filesToProcess.length,
            processed,
            percentage: (processed / filesToProcess.length) * 100,
            currentFile: file.name,
            errors: prev.progress.errors,
          },
        }));
      }

      setSyncState({
        syncing: false,
        progress: {
          total: filesToProcess.length,
          processed: filesToProcess.length,
          percentage: 100,
          currentFile: '',
          errors: syncState.progress.errors,
        },
        results,
        error: null,
      });

      return results;
    } catch (error) {
      setSyncState({
        syncing: false,
        progress: syncState.progress,
        results: [],
        error: error instanceof Error ? error.message : 'Sync failed',
      });
      throw error;
    }
  }, [client, atomIngestionPipeline, syncState.progress.errors]);

  return {
    ...syncState,
    syncFolder,
  };
};

/**
 * Hook for OneDrive permissions and sharing
 */
export const useOneDrivePermissions = (client: OneDriveAPIClient | null) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const getPermissions = useCallback(async (itemId: string) => {
    if (!client) throw new Error('OneDrive client not available');

    setLoading(true);
    setError(null);

    try {
      const permissions = await client.getPermissions(itemId);
      return permissions;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to get permissions');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [client]);

  const shareItem = useCallback(async (
    itemId: string,
    recipients: string[],
    requireSignIn: boolean = true,
    sendInvitation: boolean = true
  ) => {
    if (!client) throw new Error('OneDrive client not available');

    setLoading(true);
    setError(null);

    try {
      const shareResult = await client.shareItem(itemId, recipients, requireSignIn, sendInvitation);
      return shareResult;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to share item');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [client]);

  const createShareLink = useCallback(async (
    itemId: string,
    type: 'view' | 'edit' = 'view',
    scope: 'anonymous' | 'organization' = 'anonymous'
  ) => {
    if (!client) throw new Error('OneDrive client not available');

    setLoading(true);
    setError(null);

    try {
      const link = await client.createShareLink(itemId, type, scope);
      return link;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create share link');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [client]);

  return {
    loading,
    error,
    getPermissions,
    shareItem,
    createShareLink,
  };
};

export default {
  useOneDrive,
  useFileOperations,
  useOneDriveSearch,
  useOneDriveSync,
  useOneDrivePermissions,
};