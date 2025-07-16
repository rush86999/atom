import React, { useState, useEffect, useCallback } from 'react';
import {
  getDropboxConnectionStatus,
  disconnectDropbox,
  listDropboxFiles,
  triggerDropboxFileIngestion, // Import the new skill
  DropboxConnectionStatusInfo,
  DropboxFile
} from '../../../../src/skills/dropboxSkills'; // Adjust path as needed

interface FileListItem extends DropboxFile {
  isIngesting?: boolean;
  ingestionStatus?: 'success' | 'error' | null;
  ingestionMessage?: string;
}

interface PathHistoryItem {
  path: string;
  name: string;
}

const DropboxManager: React.FC = () => {
  const [userId] = useState<string | null>("test-user-123"); // Placeholder
  const [connectionStatus, setConnectionStatus] = useState<DropboxConnectionStatusInfo | null>(null);
  const [isLoadingStatus, setIsLoadingStatus] = useState<boolean>(true);

  const [files, setFiles] = useState<FileListItem[]>([]);
  const [currentPath, setCurrentPath] = useState<string>(''); // Root is an empty string
  const [isLoadingFiles, setIsLoadingFiles] = useState<boolean>(false);
  const [pathHistory, setPathHistory] = useState<PathHistoryItem[]>([{ name: "Dropbox", path: '' }]);

  const [errorMessages, setErrorMessages] = useState<{ general?: string; files?: string; status?: string }>({});

  const fetchConnectionStatus = useCallback(async () => {
    if (!userId) return;
    setIsLoadingStatus(true);
    setErrorMessages(prev => ({ ...prev, status: undefined }));
    try {
      const response = await getDropboxConnectionStatus(userId);
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

  const handleConnectDropbox = () => {
    if (!userId) {
      setErrorMessages(prev => ({ ...prev, general: "User ID is missing."}));
      return;
    }
    // Redirect to the backend OAuth initiation URL for Dropbox
    window.location.href = `/api/auth/dropbox/initiate?user_id=${userId}`;
  };

  const handleDisconnectDropbox = useCallback(async () => {
    if (!userId) return;
    setErrorMessages(prev => ({ ...prev, general: undefined }));
    try {
      const response = await disconnectDropbox(userId);
      if (response.ok) {
        await fetchConnectionStatus();
        setFiles([]);
        setCurrentPath('');
        setPathHistory([{ name: "Dropbox", path: '' }]);
      } else {
        setErrorMessages(prev => ({ ...prev, general: response.error?.message || 'Failed to disconnect' }));
      }
    } catch (error: any) {
      setErrorMessages(prev => ({ ...prev, general: error.message || 'Exception during disconnect' }));
    }
  }, [userId, fetchConnectionStatus]);

  const fetchFiles = useCallback(async (path: string) => {
    if (!userId || !connectionStatus?.isConnected) return;

    setIsLoadingFiles(true);
    setFiles([]);
    setErrorMessages(prev => ({ ...prev, files: undefined }));

    try {
      const response = await listDropboxFiles(userId, path);
      if (response.ok && response.data?.entries) {
        setFiles(response.data.entries);
      } else {
        setErrorMessages(prev => ({ ...prev, files: response.error?.message || 'Failed to load files' }));
      }
    } catch (error: any) {
      setErrorMessages(prev => ({ ...prev, files: error.message || 'Exception while loading files' }));
    } finally {
      setIsLoadingFiles(false);
    }
  }, [userId, connectionStatus?.isConnected]);

  const handleIngestFile = useCallback(async (file: FileListItem) => {
    if (!userId || !file.path_lower) return;

    setFiles(prevFiles => prevFiles.map(f => f.id === file.id ? { ...f, isIngesting: true, ingestionStatus: null } : f));

    try {
      const response = await triggerDropboxFileIngestion(userId, file.path_lower);
      if (response.ok) {
        setFiles(prevFiles => prevFiles.map(f => f.id === file.id ? { ...f, isIngesting: false, ingestionStatus: 'success', ingestionMessage: 'Ingestion started.' } : f));
      } else {
        setFiles(prevFiles => prevFiles.map(f => f.id === file.id ? { ...f, isIngesting: false, ingestionStatus: 'error', ingestionMessage: response.error?.message || "Ingestion failed." } : f));
      }
    } catch (error: any) {
      setFiles(prevFiles => prevFiles.map(f => f.id === file.id ? { ...f, isIngesting: false, ingestionStatus: 'error', ingestionMessage: error.message || "Exception during ingestion." } : f));
    }
  }, [userId]);

  useEffect(() => {
    if (userId) fetchConnectionStatus();
  }, [userId, fetchConnectionStatus]);

  useEffect(() => {
    if (connectionStatus?.isConnected && userId) {
      fetchFiles(currentPath);
    } else if (!connectionStatus?.isConnected) {
      setFiles([]);
      setPathHistory([{ name: "Dropbox", path: '' }]);
    }
  }, [connectionStatus?.isConnected, currentPath, userId, fetchFiles]);

  const handleFileClick = (file: FileListItem) => {
    if (file.type === 'folder') {
      const newPathItem = { name: file.name, path: file.path_lower || '' };
      setPathHistory(prev => [...prev, newPathItem]);
      setCurrentPath(newPathItem.path);
    } else {
      console.log("Selected file:", file.name);
    }
  };

  const handleBreadcrumbClick = (index: number) => {
    const newPath = pathHistory.slice(0, index + 1);
    setPathHistory(newPath);
    setCurrentPath(pathHistory[index].path);
  };

  return (
    <div style={{ fontFamily: 'Arial, sans-serif', padding: '20px', maxWidth: '800px', margin: 'auto', border: '1px solid #e0e0e0', borderRadius: '8px', boxShadow: '0 2px 4px rgba(0,0,0,0.1)', marginTop: '20px' }}>
      <h2 style={{ borderBottom: '1px solid #eee', paddingBottom: '10px', marginBottom: '20px' }}>Dropbox Management</h2>

      {errorMessages.general && <p style={{ color: 'red' }}>Error: {errorMessages.general}</p>}

      <div style={{ marginBottom: '20px' }}>
        <h3>Connection Status</h3>
        {isLoadingStatus ? <p>Loading status...</p> : connectionStatus?.isConnected ? (
          <div>
            <p style={{ color: 'green' }}>Connected as: {connectionStatus.email || 'N/A'}</p>
            <button onClick={handleDisconnectDropbox}>Disconnect Dropbox</button>
          </div>
        ) : (
          <div>
            <p style={{ color: 'orange' }}>Not Connected.</p>
            {errorMessages.status && <p style={{ color: 'red' }}>{errorMessages.status}</p>}
            <button onClick={handleConnectDropbox}>Connect Dropbox</button>
          </div>
        )}
      </div>

      {connectionStatus?.isConnected && (
        <div>
          <h3>Files and Folders</h3>
          <div>
            {pathHistory.map((p, index) => (
              <React.Fragment key={p.path}>
                <button onClick={() => handleBreadcrumbClick(index)} disabled={index === pathHistory.length - 1}>
                  {p.name}
                </button>
                {index < pathHistory.length - 1 && <span> / </span>}
              </React.Fragment>
            ))}
          </div>

          {errorMessages.files && <p style={{ color: 'red' }}>{errorMessages.files}</p>}

          {isLoadingFiles ? <p>Loading files...</p> : (
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
                  }}
                >
                  <span
                    onClick={() => handleFileClick(file)}
                    style={{ cursor: file.type === 'folder' ? 'pointer' : 'default', flexGrow: 1, display: 'flex', alignItems: 'center' }}
                  >
                    <span style={{ marginRight: '8px', fontSize: '1.1em' }}>{file.type === 'folder' ? '📁' : '📄'}</span>
                    {file.name}
                  </span>

                  {file.type === 'file' && (
                    <div style={{display: 'flex', alignItems: 'center', flexShrink: 0}}>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleIngestFile(file); }}
                        disabled={file.isIngesting || file.ingestionStatus === 'success'}
                        style={{
                          padding: '6px 10px', marginLeft: '10px', backgroundColor: file.isIngesting ? '#64b5f6' : '#007bff',
                          color: 'white', border: 'none', borderRadius: '4px',
                          cursor: (file.isIngesting || file.ingestionStatus === 'success') ? 'default' : 'pointer'
                        }}
                      >
                        {file.isIngesting ? 'Ingesting...' : (file.ingestionStatus === 'success' ? 'Ingested' : 'Ingest')}
                      </button>
                      {file.ingestionStatus === 'error' && <small style={{ color: 'red', marginLeft: '8px' }}>Error: {file.ingestionMessage}</small>}
                      {file.ingestionStatus === 'success' && !file.isIngesting && <small style={{ color: 'green', marginLeft: '8px' }}>{file.ingestionMessage}</small>}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
};

export default DropboxManager;
