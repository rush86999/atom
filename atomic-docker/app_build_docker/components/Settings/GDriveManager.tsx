import React, { useState, useEffect, useCallback } from 'react';

// Placeholder for API skill imports - will be updated in a later step
// import {
//   getGDriveConnectionStatus,
//   disconnectGDrive,
//   listGoogleDriveFiles,
//   triggerGoogleDriveFileIngestion
// } from '../../../../src/skills/gdriveSkills'; // Adjust path as needed

// --- Type Definitions (placeholders, ideally from a shared types file) ---
interface GDriveConnectionStatusInfo {
  isConnected: boolean;
  email?: string;
  reason?: string;
}

interface GDriveFile {
  id: string;
  name: string;
  mimeType: string;
}

interface FileListItem extends GDriveFile {
  isIngesting?: boolean;
  ingestionStatus?: 'success' | 'error' | null;
  ingestionMessage?: string;
}

interface PathHistoryItem {
  id?: string;
  name: string;
}

// --- Component Definition ---
const GDriveManager: React.FC = () => {
  // --- State Variables ---
  const [userId, setUserId] = useState<string | null>("test-user-123"); // Placeholder, replace with actual user ID from context/props
  const [connectionStatus, setConnectionStatus] = useState<GDriveConnectionStatusInfo | null>(null);
  const [isLoadingStatus, setIsLoadingStatus] = useState<boolean>(true);

  const [files, setFiles] = useState<FileListItem[]>([]);
  const [currentFolderId, setCurrentFolderId] = useState<string | undefined>(undefined); // undefined for root
  const [nextPageToken, setNextPageToken] = useState<string | undefined>(undefined);
  const [isLoadingFiles, setIsLoadingFiles] = useState<boolean>(false);
  const [pathHistory, setPathHistory] = useState<PathHistoryItem[]>([{ name: "My Drive", id: undefined }]);

  const [errorMessages, setErrorMessages] = useState<{ general?: string; files?: string; status?: string }>({});

  // --- API Calling Logic ---
  // Adjust the import path based on your project structure.
  // This assumes gdriveSkills.ts is correctly updated as per the previous plan.
  // For now, these will be commented out until gdriveSkills.ts is confirmed/updated.
  /*
  import {
    getGDriveConnectionStatus,
    disconnectGDrive,
    listGoogleDriveFiles,
    triggerGoogleDriveFileIngestion,
    // Make sure GDriveFile type is also exported from gdriveSkills or a shared types file
  } from '../../../../src/skills/gdriveSkills'; // Example path
  */

  // Placeholder for actual skill functions - using console logs for now
  const getGDriveConnectionStatus = async (userId: string) => { console.log(`mock: getGDriveConnectionStatus for ${userId}`); return { ok: true, data: { isConnected: false, email: undefined } as GDriveConnectionStatusInfo }; };
  const disconnectGDrive = async (userId: string) => { console.log(`mock: disconnectGDrive for ${userId}`); return { ok: true, data: { message: "Disconnected" } }; };
  const listGoogleDriveFiles = async (userId: string, folderId?: string, pageToken?: string, query?: string, pageSize?: number) => {
    console.log(`mock: listGoogleDriveFiles for ${userId}, folder: ${folderId}, pageToken: ${pageToken}`);
    const mockFilesData: GDriveFile[] = folderId === "folder1" ?
      [{ id: "file3", name: "SubFile.txt", mimeType: "text/plain" }] :
      [
        { id: "file1", name: "Document 1.gdoc", mimeType: "application/vnd.google-apps.document" },
        { id: "folder1", name: "My Test Folder", mimeType: "application/vnd.google-apps.folder" },
        { id: "file2", name: "Spreadsheet.gsheet", mimeType: "application/vnd.google-apps.spreadsheet" },
      ];
    return { ok: true, data: { files: mockFilesData, nextPageToken: folderId === "folder1" ? undefined : "mockNextPageToken" } };
  };
  const triggerGoogleDriveFileIngestion = async (userId: string, fileId: string, metadata: { name: string; mimeType: string; webViewLink?: string }) => {
    console.log(`mock: triggerGoogleDriveFileIngestion for ${userId}, fileId: ${fileId}`);
    return { ok: true, data: { doc_id: "new-doc-id", num_chunks_stored: 5 } };
  };


  const fetchConnectionStatus = useCallback(async () => {
    if (!userId) return;
    setIsLoadingStatus(true);
    setErrorMessages(prev => ({ ...prev, status: undefined }));
    try {
      const response = await getGDriveConnectionStatus(userId);
      if (response.ok && response.data) {
        setConnectionStatus(response.data);
      } else {
        setConnectionStatus({ isConnected: false, reason: response.error?.message || 'Failed to get status' });
        setErrorMessages(prev => ({ ...prev, status: response.error?.message || 'Failed to get status' }));
      }
    } catch (error: any) {
      setConnectionStatus({ isConnected: false, reason: 'Exception while fetching status' });
      setErrorMessages(prev => ({ ...prev, status: error.message || 'Exception while fetching status' }));
    } finally {
      setIsLoadingStatus(false);
    }
  }, [userId]);

  const handleConnectGDrive = () => {
    if (!userId) {
      setErrorMessages(prev => ({ ...prev, general: "User ID is missing. Cannot initiate connection."}));
      return;
    }
    // This will be a redirect to the backend OAuth initiation URL
    // The backend will then redirect to Google, and Google will redirect back to a callback URL.
    // Ensure this callback URL eventually leads the user back to this settings page,
    // perhaps with query params indicating success/failure.
    window.location.href = `/api/auth/gdrive/initiate?user_id=${userId}`;
  };

  const handleDisconnectGDrive = useCallback(async () => {
    if (!userId) return;
    // Optionally, add a confirmation dialog here
    setErrorMessages(prev => ({ ...prev, general: undefined }));
    try {
      const response = await disconnectGDrive(userId);
      if (response.ok) {
        await fetchConnectionStatus(); // Refresh status
        setFiles([]);
        setNextPageToken(undefined);
        setCurrentFolderId(undefined);
        setPathHistory([{ name: "My Drive", id: undefined }]);
      } else {
        setErrorMessages(prev => ({ ...prev, general: response.error?.message || 'Failed to disconnect' }));
      }
    } catch (error: any) {
      setErrorMessages(prev => ({ ...prev, general: error.message || 'Exception during disconnect' }));
    }
  }, [userId, fetchConnectionStatus]);

  const fetchFiles = useCallback(async (targetFolderId?: string, pageToken?: string, isLoadMore = false) => {
    if (!userId || !connectionStatus?.isConnected) return;

    setIsLoadingFiles(true);
    if (!isLoadMore) { // If not loading more, it's a new folder or refresh
        setFiles([]); // Clear previous files for the new folder
        setErrorMessages(prev => ({ ...prev, files: undefined }));
    }

    try {
      const response = await listGoogleDriveFiles(userId, targetFolderId, pageToken, undefined, 20); // pageSize 20 example
      if (response.ok && response.data) {
        const newFiles = response.data.files.map((f: GDriveFile) => ({ ...f, isIngesting: false, ingestionStatus: null, ingestionMessage: undefined }) as FileListItem);
        setFiles(prev => isLoadMore ? [...prev, ...newFiles] : newFiles);
        setNextPageToken(response.data.nextPageToken);
      } else {
        setErrorMessages(prev => ({ ...prev, files: response.error?.message || 'Failed to load files' }));
        if (!isLoadMore) setFiles([]); // Clear files on error if it was a fresh load
      }
    } catch (error: any) {
      setErrorMessages(prev => ({ ...prev, files: error.message || 'Exception while loading files' }));
      if (!isLoadMore) setFiles([]);
    } finally {
      setIsLoadingFiles(false);
    }
  }, [userId, connectionStatus?.isConnected]); // Removed 'files' from dep array to prevent loops on setFiles within

  const handleIngestFile = useCallback(async (file: FileListItem) => {
    if (!userId) return;

    setFiles(prevFiles => prevFiles.map(f => f.id === file.id ? { ...f, isIngesting: true, ingestionStatus: null, ingestionMessage: undefined } : f));
    setErrorMessages(prev => ({ ...prev, general: undefined }));

    try {
      // The webViewLink might not be available from list-files.
      // If it's crucial for ingestion (e.g. as source_uri),
      // it might need to be fetched via getGoogleDriveFileMetadata first,
      // or the backend's /api/ingest-gdrive-document needs to be robust enough
      // to construct a source_uri from just the file ID if webViewLink is missing.
      // For this conceptual step, we assume originalFileMetadata can be constructed adequately.
      const metadataForIngestion = {
        name: file.name,
        mimeType: file.mimeType,
        // webViewLink: file.webViewLink, // This field might not be in GDriveFile from list-files
      };

      const response = await triggerGoogleDriveFileIngestion(userId, file.id, metadataForIngestion);

      if (response.ok) {
        setFiles(prevFiles => prevFiles.map(f => f.id === file.id ? { ...f, isIngesting: false, ingestionStatus: 'success', ingestionMessage: 'Ingestion started.' } : f));
      } else {
        setFiles(prevFiles => prevFiles.map(f => f.id === file.id ? { ...f, isIngesting: false, ingestionStatus: 'error', ingestionMessage: response.error?.message || "Ingestion failed." } : f));
      }
    } catch (error: any) {
      setFiles(prevFiles => prevFiles.map(f => f.id === file.id ? { ...f, isIngesting: false, ingestionStatus: 'error', ingestionMessage: error.message || "Exception during ingestion." } : f));
    }
  }, [userId]);

  // --- Effect Hooks ---
  useEffect(() => {
    // Fetch initial connection status when userId is available
    if (userId) {
      fetchConnectionStatus();
    }
  }, [userId, fetchConnectionStatus]);

  useEffect(() => {
    // Fetch files when connection is established or currentFolderId changes
    if (connectionStatus?.isConnected && userId) {
      fetchFiles(currentFolderId, undefined, false); // false for isLoadMore indicates new folder load
    } else if (!connectionStatus?.isConnected) { // Clear files if connection is lost or not present
      setFiles([]);
      setNextPageToken(undefined);
      setPathHistory([{ name: "My Drive", id: undefined }]);
    }
    // Dependency: fetchFiles is useCallback wrapped.
  }, [connectionStatus?.isConnected, currentFolderId, userId, fetchFiles]);

  // --- Event Handlers ---
  const handleFileClick = (file: FileListItem) => {
    if (file.mimeType === 'application/vnd.google-apps.folder') {
      // Navigate into folder
      // Avoid adding duplicate if path already exists (e.g. user clicks back then forward)
      const existingPathItem = pathHistory.find(p => p.id === file.id);
      if (existingPathItem) {
          const existingIndex = pathHistory.findIndex(p => p.id === file.id);
          setPathHistory(prev => prev.slice(0, existingIndex + 1));
      } else {
          setPathHistory(prev => [...prev, { id: file.id, name: file.name }]);
      }
      setCurrentFolderId(file.id);
      // fetchFiles will be triggered by useEffect watching currentFolderId
    } else {
      // Potentially show file details or context menu for non-folder items
      console.log("Selected file (non-folder):", file.name);
      // Could add logic here to select the file for an action like "view details"
    }
  };

  const handleBreadcrumbClick = (index: number) => {
    const newPath = pathHistory.slice(0, index + 1);
    setPathHistory(newPath);
    setCurrentFolderId(pathHistory[index].id);
    // fetchFiles will be triggered by useEffect watching currentFolderId
  };

  // handleConnectGDrive, handleDisconnectGDrive, handleIngestFile are already defined with API logic.

  // --- Render Logic (Basic Structure with Placeholders and Comments) ---
  return (
    <div style={{ fontFamily: 'Arial, sans-serif', padding: '20px', maxWidth: '800px', margin: 'auto', border: '1px solid #e0e0e0', borderRadius: '8px', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
      <h2 style={{ borderBottom: '1px solid #eee', paddingBottom: '10px', marginBottom: '20px' }}>Google Drive Management</h2>

      {/* General Error Display */}
      {errorMessages.general && <p style={{ color: 'red', backgroundColor: '#ffebee', padding: '10px', borderRadius: '4px' }}>Error: {errorMessages.general}</p>}

      {/* Connection Status Section */}
      <div style={{ marginBottom: '20px', padding: '15px', border: '1px solid #ccc', borderRadius: '5px', backgroundColor: '#f9f9f9' }}>
        <h3 style={{ marginTop: '0' }}>Connection Status</h3>
        {isLoadingStatus ? (
          <p>Loading status...</p>
        ) : connectionStatus?.isConnected ? (
          <div>
            <p style={{ color: 'green', fontWeight: 'bold' }}>Connected as: {connectionStatus.email || 'N/A'}</p>
            <button
              onClick={handleDisconnectGDrive}
              style={{ padding: '8px 12px', backgroundColor: '#f44336', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
            >
              Disconnect Google Drive
            </button>
          </div>
        ) : (
          <div>
            <p style={{ color: 'orange', fontWeight: 'bold' }}>Not Connected.</p>
            {connectionStatus?.reason && <p style={{fontSize: '0.9em', color: '#757575'}}>Reason: {connectionStatus.reason}</p>}
            {errorMessages.status && <p style={{ color: 'red', fontSize: '0.9em' }}>Error fetching status: {errorMessages.status}</p>}
            <button
              onClick={handleConnectGDrive}
              style={{ padding: '8px 12px', backgroundColor: '#4CAF50', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
            >
              Connect Google Drive
            </button>
          </div>
        )}
      </div>

      {/* File Explorer Section - Only show if connected */}
      {connectionStatus?.isConnected && (
        <div style={{ marginTop: '20px', padding: '15px', border: '1px solid #ccc', borderRadius: '5px', backgroundColor: '#f9f9f9' }}>
          <h3 style={{ marginTop: '0' }}>Files and Folders</h3>

          {/* Breadcrumbs */}
          <div style={{ marginBottom: '10px', padding: '8px', backgroundColor: '#f0f0f0', borderRadius: '4px' }}>
            {pathHistory.map((p, index) => (
              <span key={p.id || 'root-breadcrumb'}>
                <button
                  onClick={() => handleBreadcrumbClick(index)}
                  disabled={index === pathHistory.length - 1}
                  style={{
                    background: 'none', border: 'none',
                    color: index === pathHistory.length - 1 ? '#333' : '#007bff',
                    cursor: index === pathHistory.length - 1 ? 'default' : 'pointer',
                    padding: '0', marginRight: '5px', fontWeight: index === pathHistory.length - 1 ? 'bold' : 'normal',
                    textDecoration: index !== pathHistory.length - 1 ? 'underline' : 'none'
                  }}
                >
                  {p.name}
                </button>
                {index < pathHistory.length - 1 && <span style={{ margin: '0 5px', color: '#666' }}>/</span>}
              </span>
            ))}
          </div>

          {errorMessages.files && <p style={{ color: 'red', backgroundColor: '#ffebee', padding: '10px', borderRadius: '4px' }}>Error loading files: {errorMessages.files}</p>}

          {isLoadingFiles && files.length === 0 ? (
            <p>Loading files...</p>
          ) : files.length === 0 && !isLoadingFiles ? (
            <p style={{ fontStyle: 'italic', color: '#757575' }}>No files or folders found in this location.</p>
          ) : (
            <ul style={{ listStyleType: 'none', paddingLeft: '0', margin: '0' }}>
              {files.map(file => (
                <li
                  key={file.id}
                  style={{
                    padding: '10px 5px',
                    borderBottom: '1px solid #eee',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    cursor: file.mimeType === 'application/vnd.google-apps.folder' ? 'pointer' : 'default',
                  }}
                  onClick={() => file.mimeType === 'application/vnd.google-apps.folder' && handleFileClick(file)}
                  title={file.mimeType === 'application/vnd.google-apps.folder' ? `Open folder: ${file.name}` : `File: ${file.name}`}
                >
                  <span style={{ flexGrow: 1 }}>
                    {file.mimeType === 'application/vnd.google-apps.folder' ? '📁' : '📄'} {file.name}
                  </span>
                  {file.mimeType !== 'application/vnd.google-apps.folder' && (
                    <div style={{display: 'flex', alignItems: 'center', flexShrink: 0}}>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleIngestFile(file); }}
                        disabled={file.isIngesting || file.ingestionStatus === 'success'}
                        style={{ padding: '6px 10px', marginLeft: '10px', backgroundColor: file.ingestionStatus === 'success' ? '#a5d6a7' : (file.isIngesting ? '#64b5f6' : '#007bff'), color: 'white', border: 'none', borderRadius: '4px', cursor: (file.isIngesting || file.ingestionStatus === 'success') ? 'default' : 'pointer', fontSize: '0.9em' }}
                      >
                        {file.isIngesting ? 'Ingesting...' : (file.ingestionStatus === 'success' ? 'Ingested' : 'Ingest')}
                      </button>
                      {file.ingestionStatus === 'error' && <small style={{ color: 'red', marginLeft: '8px', fontSize: '0.85em' }}>Error: {file.ingestionMessage}</small>}
                      {file.ingestionStatus === 'success' && !file.isIngesting && <small style={{ color: 'green', marginLeft: '8px', fontSize: '0.85em' }}>{file.ingestionMessage}</small>}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}

          {/* Pagination Button */}
          {nextPageToken && !isLoadingFiles && (
            <button
              onClick={() => fetchFiles(currentFolderId, nextPageToken, true)} // true for isLoadMore
              style={{ marginTop: '15px', padding: '8px 12px', backgroundColor: '#6c757d', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
            >
              Load More
            </button>
          )}
          {isLoadingFiles && files.length > 0 && <p style={{marginTop: '10px', fontStyle: 'italic', color: '#757575'}}>Loading more files...</p>}
        </div>
      )}
    </div>
  );
};

export default GDriveManager;
