import React, { useState, useEffect, useCallback } from 'react';
import { useSession } from 'next-auth/react';

import {
    getGDriveConnectionStatus,
    disconnectGDrive,
    listGoogleDriveFiles,
    triggerGoogleDriveFileIngestion,
    GDriveConnectionStatusInfo,
    GoogleDriveFile as GDriveFileType
} from '../../../src/skills/gdriveSkills';

// Use GDriveFileType for internal FileListItem
interface FileListItem extends GDriveFileType {
    isIngesting?: boolean;
    ingestionStatus?: 'success' | 'error' | null;
    ingestionMessage?: string;
}

interface PathHistoryItem {
    id?: string;
    name: string;
}

const GDriveManager: React.FC = () => {
    const { data: session } = useSession();
    const userId = session?.user?.id;

    const [connectionStatus, setConnectionStatus] = useState<GDriveConnectionStatusInfo | null>(null);
    const [isLoadingStatus, setIsLoadingStatus] = useState<boolean>(true);

    const [files, setFiles] = useState<FileListItem[]>([]);
    const [currentFolderId, setCurrentFolderId] = useState<string | undefined>(undefined);
    const [nextPageToken, setNextPageToken] = useState<string | undefined>(undefined);
    const [isLoadingFiles, setIsLoadingFiles] = useState<boolean>(false);
    const [pathHistory, setPathHistory] = useState<PathHistoryItem[]>([{ name: "My Drive", id: undefined }]);

    const [errorMessages, setErrorMessages] = useState<{ general?: string; files?: string; status?: string }>({});

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
            setErrorMessages(prev => ({ ...prev, general: "User ID is missing. Cannot initiate connection." }));
            return;
        }
        window.location.href = `/api/auth/gdrive/initiate?user_id=${userId}`;
    };

    const handleDisconnectGDrive = useCallback(async () => {
        if (!userId) return;
        setErrorMessages(prev => ({ ...prev, general: undefined }));
        try {
            const response = await disconnectGDrive(userId);
            if (response.ok) {
                await fetchConnectionStatus();
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
        if (!isLoadMore) {
            setFiles([]);
            setErrorMessages(prev => ({ ...prev, files: undefined }));
        }

        try {
            const response = await listGoogleDriveFiles(userId, targetFolderId, pageToken, undefined, 20);
            if (response.ok && response.data) {
                const newFiles = response.data.files.map((f: any) => ({ ...f, isIngesting: false, ingestionStatus: null, ingestionMessage: undefined }) as FileListItem);
                setFiles(prev => isLoadMore ? [...prev, ...newFiles] : newFiles);
                setNextPageToken(response.data.nextPageToken);
            } else {
                setErrorMessages(prev => ({ ...prev, files: response.error?.message || 'Failed to load files' }));
                if (!isLoadMore) setFiles([]);
            }
        } catch (error: any) {
            setErrorMessages(prev => ({ ...prev, files: error.message || 'Exception while loading files' }));
            if (!isLoadMore) setFiles([]);
        } finally {
            setIsLoadingFiles(false);
        }
    }, [userId, connectionStatus?.isConnected]);

    const handleIngestFile = useCallback(async (file: FileListItem) => {
        if (!userId) return;

        setFiles(prevFiles => prevFiles.map(f => f.id === file.id ? { ...f, isIngesting: true, ingestionStatus: null, ingestionMessage: undefined } : f));
        setErrorMessages(prev => ({ ...prev, general: undefined }));

        try {
            const metadataForIngestion = {
                name: file.name,
                mimeType: file.mimeType,
                webViewLink: file.webViewLink || undefined,
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

    useEffect(() => {
        if (userId) {
            fetchConnectionStatus();
        }
    }, [userId, fetchConnectionStatus]);

    useEffect(() => {
        if (connectionStatus?.isConnected && userId) {
            fetchFiles(currentFolderId, undefined, false);
        } else if (!connectionStatus?.isConnected) {
            setFiles([]);
            setNextPageToken(undefined);
            setPathHistory([{ name: "My Drive", id: undefined }]);
        }
    }, [connectionStatus?.isConnected, currentFolderId, userId, fetchFiles]);

    const handleFileClick = (file: FileListItem) => {
        if (file.mimeType === 'application/vnd.google-apps.folder') {
            const existingPathItem = pathHistory.find(p => p.id === file.id);
            if (existingPathItem) {
                const existingIndex = pathHistory.findIndex(p => p.id === file.id);
                setPathHistory(prev => prev.slice(0, existingIndex + 1));
            } else {
                setPathHistory(prev => [...prev, { id: file.id, name: file.name }]);
            }
            setCurrentFolderId(file.id);
        }
    };

    const handleBreadcrumbClick = (index: number) => {
        const newPath = pathHistory.slice(0, index + 1);
        setPathHistory(newPath);
        setCurrentFolderId(pathHistory[index].id);
    };

    return (
        <div style={{ fontFamily: 'Arial, sans-serif', padding: '20px', maxWidth: '800px', margin: 'auto', border: '1px solid #e0e0e0', borderRadius: '8px', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
            <h2 style={{ borderBottom: '1px solid #eee', paddingBottom: '10px', marginBottom: '20px' }}>Google Drive Management</h2>

            {errorMessages.general && (
                <p style={{ color: 'red', backgroundColor: '#ffebee', padding: '10px', borderRadius: '4px', border: '1px solid #e57373', marginBottom: '15px' }}>
                    <strong>Error:</strong> {errorMessages.general}
                </p>
            )}

            <div style={{ marginBottom: '20px', padding: '15px', border: '1px solid #ccc', borderRadius: '5px', backgroundColor: '#f9f9f9' }}>
                <h3 style={{ marginTop: '0', marginBottom: '10px', borderBottom: '1px solid #eee', paddingBottom: '8px' }}>Connection Status</h3>
                {isLoadingStatus ? (
                    <p>Loading status...</p>
                ) : connectionStatus?.isConnected ? (
                    <div>
                        <p style={{ color: 'green', fontWeight: 'bold', marginBottom: '10px' }}>
                            Connected as: {connectionStatus.email || 'N/A'}
                        </p>
                        <button
                            onClick={handleDisconnectGDrive}
                            style={{
                                padding: '8px 15px',
                                backgroundColor: '#f44336',
                                color: 'white',
                                border: 'none',
                                borderRadius: '4px',
                                cursor: 'pointer',
                                fontSize: '0.9em'
                            }}
                        >
                            Disconnect Google Drive
                        </button>
                    </div>
                ) : (
                    <div>
                        <p style={{ color: '#f57c00', fontWeight: 'bold', marginBottom: '5px' }}>
                            Not Connected.
                        </p>
                        {connectionStatus?.reason && (
                            <p style={{ fontSize: '0.9em', color: '#757575', marginTop: '0', marginBottom: '10px' }}>
                                Reason: {connectionStatus.reason}
                            </p>
                        )}
                        {errorMessages.status && (
                            <p style={{ color: 'red', fontSize: '0.9em', marginTop: '0', marginBottom: '10px' }}>
                                Error fetching status: {errorMessages.status}
                            </p>
                        )}
                        <button
                            onClick={handleConnectGDrive}
                            style={{
                                padding: '8px 15px',
                                backgroundColor: '#4CAF50',
                                color: 'white',
                                border: 'none',
                                borderRadius: '4px',
                                cursor: 'pointer',
                                fontSize: '0.9em'
                            }}
                        >
                            Connect Google Drive
                        </button>
                    </div>
                )}
            </div>

            {connectionStatus?.isConnected && (
                <div style={{ marginTop: '20px', padding: '15px', border: '1px solid #ccc', borderRadius: '5px', backgroundColor: '#f9f9f9' }}>
                    <h3 style={{ marginTop: '0', marginBottom: '10px', borderBottom: '1px solid #eee', paddingBottom: '8px' }}>Files and Folders</h3>

                    <div style={{ marginBottom: '10px', padding: '8px', backgroundColor: '#f0f0f0', borderRadius: '4px', display: 'flex', flexWrap: 'wrap', alignItems: 'center' }}>
                        {pathHistory.map((p, index) => (
                            <React.Fragment key={p.id || 'root-breadcrumb'}>
                                <button
                                    onClick={() => handleBreadcrumbClick(index)}
                                    disabled={index === pathHistory.length - 1}
                                    style={{
                                        background: 'none', border: 'none',
                                        color: index === pathHistory.length - 1 ? '#333' : '#007bff',
                                        cursor: index === pathHistory.length - 1 ? 'default' : 'pointer',
                                        padding: '2px 0',
                                        marginRight: '5px',
                                        fontWeight: index === pathHistory.length - 1 ? 'bold' : 'normal',
                                        textDecoration: index !== pathHistory.length - 1 ? 'underline' : 'none',
                                        fontSize: '0.95em'
                                    }}
                                >
                                    {p.name}
                                </button>
                                {index < pathHistory.length - 1 && <span style={{ margin: '0 5px', color: '#666' }}>/</span>}
                            </React.Fragment>
                        ))}
                    </div>

                    {errorMessages.files && (
                        <p style={{ color: 'red', backgroundColor: '#ffebee', padding: '10px', borderRadius: '4px', border: '1px solid #e57373', marginBottom: '10px' }}>
                            <strong>Error loading files:</strong> {errorMessages.files}
                        </p>
                    )}

                    {isLoadingFiles && files.length === 0 ? (
                        <p>Loading files...</p>
                    ) : files.length === 0 && !isLoadingFiles ? (
                        <p style={{ fontStyle: 'italic', color: '#757575', padding: '10px 0' }}>No files or folders found in this location.</p>
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
                                    onClick={() => {
                                        if (file.mimeType === 'application/vnd.google-apps.folder') {
                                            handleFileClick(file);
                                        }
                                    }}
                                    title={file.mimeType === 'application/vnd.google-apps.folder' ? `Open folder: ${file.name}` : `File: ${file.name}`}
                                >
                                    <span style={{ flexGrow: 1, display: 'flex', alignItems: 'center' }}>
                                        <span style={{ marginRight: '8px', fontSize: '1.1em' }}>
                                            {file.mimeType === 'application/vnd.google-apps.folder' ? '📁' : '📄'}
                                        </span>
                                        {file.name}
                                    </span>
                                    {file.mimeType !== 'application/vnd.google-apps.folder' && (
                                        <div style={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
                                            <button
                                                onClick={(e) => { e.stopPropagation(); handleIngestFile(file); }}
                                                disabled={file.isIngesting || file.ingestionStatus === 'success'}
                                                style={{
                                                    padding: '6px 10px',
                                                    marginLeft: '10px',
                                                    backgroundColor: file.ingestionStatus === 'success' ? '#a5d6a7' : (file.isIngesting ? '#64b5f6' : '#007bff'),
                                                    color: 'white',
                                                    border: 'none',
                                                    borderRadius: '4px',
                                                    cursor: (file.isIngesting || file.ingestionStatus === 'success') ? 'default' : 'pointer',
                                                    fontSize: '0.9em'
                                                }}
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

                    {nextPageToken && !isLoadingFiles && (
                        <div style={{ marginTop: '15px', textAlign: 'center' }}>
                            <button
                                onClick={() => fetchFiles(currentFolderId, nextPageToken, true)}
                                style={{
                                    padding: '8px 15px',
                                    backgroundColor: '#6c757d',
                                    color: 'white',
                                    border: 'none',
                                    borderRadius: '4px',
                                    cursor: 'pointer',
                                    fontSize: '0.9em'
                                }}
                            >
                                Load More
                            </button>
                        </div>
                    )}
                    {isLoadingFiles && files.length > 0 && <p style={{ marginTop: '10px', fontStyle: 'italic', color: '#757575', textAlign: 'center' }}>Loading more files...</p>}
                </div>
            )}
        </div>
    );
};

export default GDriveManager;
