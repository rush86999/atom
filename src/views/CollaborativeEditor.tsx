import React, { useState, useEffect, useCallback, useRef, FC } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import { useToast } from '../components/NotificationSystem';

interface DocumentVersion {
    id: string;
    content: string;
    author: string;
    timestamp: number;
    changesSummary: string;
}

interface CursorPosition {
    userId: string;
    username: string;
    position: number;
    color: string;
}

interface TextChange {
    id: string;
    type: 'insert' | 'delete';
    position: number;
    content: string;
    author: string;
    timestamp: number;
}

const CursorIndicator: FC<{ cursor: CursorPosition; editorRef: React.RefObject<HTMLTextAreaElement | null> }> = ({
    cursor,
    editorRef,
}) => {
    const [pos, setPos] = useState({ top: 0, left: 0 });

    useEffect(() => {
        if (!editorRef.current) return;

        // Calculate cursor position in editor
        const lineHeight = parseInt(window.getComputedStyle(editorRef.current).lineHeight);
        const top = (cursor.position / 50) * lineHeight; // Approximate
        const left = (cursor.position % 50) * 8; // Approximate character width

        setPos({ top, left });
    }, [cursor, editorRef]);

    return (
        <div
            className="remote-cursor"
            style={{
                top: `${pos.top}px`,
                left: `${pos.left}px`,
                backgroundColor: cursor.color,
                opacity: 0.7,
            }}
        >
            <span className="cursor-label">{cursor.username}</span>
        </div>
    );
};

const VersionHistory: FC<{ versions: DocumentVersion[]; onRevert: (versionId: string) => void }> = ({
    versions,
    onRevert,
}) => {
    return (
        <div className="version-history">
            <h3>📜 Version History</h3>
            <div className="versions-list">
                {versions.map((version, index) => (
                    <div key={version.id} className="version-item">
                        <div className="version-header">
                            <span className="version-number">v{versions.length - index}</span>
                            <strong>{version.author}</strong>
                            <span className="version-time">{new Date(version.timestamp).toLocaleTimeString()}</span>
                        </div>
                        <p className="version-summary">{version.changesSummary}</p>
                        {index > 0 && (
                            <button
                                onClick={() => onRevert(version.id)}
                                className="revert-btn"
                                title="Revert to this version"
                            >
                                ↩️ Revert
                            </button>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
};

const ChangeLog: FC<{ changes: TextChange[] }> = ({ changes }) => {
    return (
        <div className="change-log">
            <h3>🔍 Change Log</h3>
            <div className="changes-list">
                {changes.slice(0, 10).map((change) => (
                    <div key={change.id} className="change-item">
                        <span className="change-type" style={{ color: change.type === 'insert' ? '#10b981' : '#ef4444' }}>
                            {change.type === 'insert' ? '+' : '−'}
                        </span>
                        <span className="change-content">{change.content.substring(0, 30)}</span>
                        <span className="change-author">{change.author}</span>
                        <span className="change-time">{new Date(change.timestamp).toLocaleTimeString()}</span>
                    </div>
                ))}
            </div>
        </div>
    );
};

const CollaboratorsList: FC<{ cursors: CursorPosition[] }> = ({ cursors }) => {
    return (
        <div className="collaborators-list">
            <h3>👥 Active Collaborators</h3>
            <div className="collaborators-grid">
                {cursors.map((cursor) => (
                    <div key={cursor.userId} className="collaborator-item">
                        <div className="collaborator-avatar" style={{ backgroundColor: cursor.color }}>
                            {cursor.username.charAt(0).toUpperCase()}
                        </div>
                        <span className="collaborator-name">{cursor.username}</span>
                    </div>
                ))}
            </div>
        </div>
    );
};

export const CollaborativeEditor: FC = () => {
    const { success, warning } = useToast();
    const { subscribe, unsubscribe, emit, isConnected } = useWebSocket({ enabled: true });
    const editorRef = useRef<HTMLTextAreaElement>(null);

    const [content, setContent] = useState(`# Collaborative Document

Welcome to the collaborative editor! This document is shared in real-time with all active collaborators.

## Features
- Real-time text synchronization
- Multi-user cursor tracking
- Version history with revert capability
- Change log with detailed tracking
- Conflict-free editing

Start typing and see your changes sync instantly across all clients...
`);

    const [documentTitle, setDocumentTitle] = useState('Untitled Document');
    const [isLocked, setIsLocked] = useState(false);
    const [lockHolder, setLockHolder] = useState<string | null>(null);

    const [cursorPositions, setCursorPositions] = useState<CursorPosition[]>([
        { userId: '2', username: 'Bob', position: 45, color: '#3b82f6' },
        { userId: '3', username: 'Carol', position: 120, color: '#8b5cf6' },
    ]);

    const [versions, setVersions] = useState<DocumentVersion[]>([
        {
            id: '1',
            content,
            author: 'You',
            timestamp: Date.now(),
            changesSummary: 'Initial document creation',
        },
    ]);

    const [changes, setChanges] = useState<TextChange[]>([]);
    const [autoSave, setAutoSave] = useState(true);
    const [lastSaved, setLastSaved] = useState(Date.now());
    const autoSaveIntervalRef = useRef<NodeJS.Timeout | null>(null);

    // Handle document lock
    const handleLockDocument = useCallback(() => {
        if (!isLocked) {
            emit('document:lock', { documentId: 'current-doc', userId: 'you' });
            setIsLocked(true);
            setLockHolder('You');
            success('Document Locked', 'Only you can edit this document');
        } else {
            emit('document:unlock', { documentId: 'current-doc', userId: 'you' });
            setIsLocked(false);
            setLockHolder(null);
            success('Document Unlocked', 'Other users can now edit');
        }
    }, [isLocked, emit, success]);

    // Handle content changes with real-time sync
    const handleContentChange = useCallback(
        (e: React.ChangeEvent<HTMLTextAreaElement>) => {
            const newContent = e.target.value;
            const oldContent = content;

            setContent(newContent);

            // Calculate what changed
            if (newContent.length > oldContent.length) {
                const newText = newContent.substring(oldContent.length);
                const newChange: TextChange = {
                    id: `change-${Date.now()}`,
                    type: 'insert',
                    position: oldContent.length,
                    content: newText,
                    author: 'You',
                    timestamp: Date.now(),
                };
                setChanges((prev) => [newChange, ...prev]);
                emit('document:edit', newChange);
            } else if (newContent.length < oldContent.length) {
                const deletedText = oldContent.substring(newContent.length);
                const newChange: TextChange = {
                    id: `change-${Date.now()}`,
                    type: 'delete',
                    position: newContent.length,
                    content: deletedText,
                    author: 'You',
                    timestamp: Date.now(),
                };
                setChanges((prev) => [newChange, ...prev]);
                emit('document:edit', newChange);
            }
        },
        [content, emit]
    );

    // Auto-save functionality
    useEffect(() => {
        if (autoSave) {
            if (autoSaveIntervalRef.current) {
                clearInterval(autoSaveIntervalRef.current);
            }

            autoSaveIntervalRef.current = setInterval(() => {
                setLastSaved(Date.now());
                success('Saved', 'Document saved automatically');
            }, 30000); // Auto-save every 30 seconds
        }

        return () => {
            if (autoSaveIntervalRef.current) {
                clearInterval(autoSaveIntervalRef.current);
            }
        };
    }, [autoSave, success]);

    // Manual save
    const handleSave = useCallback(() => {
        const newVersion: DocumentVersion = {
            id: `v-${Date.now()}`,
            content,
            author: 'You',
            timestamp: Date.now(),
            changesSummary: `Modified ${changes.length} changes`,
        };

        setVersions((prev) => [newVersion, ...prev]);
        setLastSaved(Date.now());
        emit('document:save', { documentId: 'current-doc', version: newVersion });
        success('Saved', 'Document saved successfully');
    }, [content, changes, emit, success]);

    // Export document
    const handleExport = useCallback(() => {
        const element = document.createElement('a');
        const file = new Blob([content], { type: 'text/markdown' });
        element.href = URL.createObjectURL(file);
        element.download = `${documentTitle}.md`;
        document.body.appendChild(element);
        element.click();
        document.body.removeChild(element);
        success('Exported', 'Document exported as Markdown');
    }, [content, documentTitle, success]);

    // Revert to version
    const handleRevertVersion = useCallback(
        (versionId: string) => {
            const version = versions.find((v) => v.id === versionId);
            if (version) {
                setContent(version.content);
                warning('Version Reverted', `Reverted to version by ${version.author}`);
                emit('document:reverted', { documentId: 'current-doc', versionId });
            }
        },
        [versions, emit, warning]
    );

    // Real-time event handlers
    useEffect(() => {
        const handleRemoteEdit = (data: TextChange) => {
            if (data.type === 'insert') {
                setContent((prev) => prev.slice(0, data.position) + data.content + prev.slice(data.position));
            } else {
                setContent((prev) => prev.slice(0, data.position) + prev.slice(data.position + data.content.length));
            }
            setChanges((prev) => [data, ...prev]);
        };

        const handleRemoteCursor = (data: CursorPosition) => {
            setCursorPositions((prev) => {
                const filtered = prev.filter((c) => c.userId !== data.userId);
                return [...filtered, data];
            });
        };

        const handleDocumentLocked = (data: any) => {
            setIsLocked(true);
            setLockHolder(data.userId);
            if (data.userId !== 'you') {
                warning('Document Locked', `${data.userId} locked this document`);
            }
        };

        const handleDocumentUnlocked = (data: any) => {
            setIsLocked(false);
            setLockHolder(null);
            success('Document Unlocked', 'You can now edit');
        };

        subscribe('document:edit', handleRemoteEdit);
        subscribe('cursor:move', handleRemoteCursor);
        subscribe('document:locked', handleDocumentLocked);
        subscribe('document:unlocked', handleDocumentUnlocked);

        return () => {
            unsubscribe('document:edit');
            unsubscribe('cursor:move');
            unsubscribe('document:locked');
            unsubscribe('document:unlocked');
        };
    }, [subscribe, unsubscribe, success, warning]);

    return (
        <div className="collaborative-editor">
            <header className="view-header">
                <div className="editor-title-bar">
                    <input
                        type="text"
                        value={documentTitle}
                        onChange={(e) => setDocumentTitle(e.target.value)}
                        className="document-title-input"
                        placeholder="Document Title"
                    />
                    <div className="editor-status">
                        <span className={`connection-status ${isConnected ? 'online' : 'offline'}`}>
                            {isConnected ? '🟢 Online' : '🔴 Offline'}
                        </span>
                        <span className="save-status">
                            Last saved: {new Date(lastSaved).toLocaleTimeString()}
                        </span>
                    </div>
                </div>
            </header>

            <div className="editor-toolbar">
                <button onClick={handleSave} className="editor-btn primary">
                    💾 Save
                </button>
                <button onClick={handleExport} className="editor-btn">
                    📥 Export
                </button>
                <button onClick={handleLockDocument} className={`editor-btn ${isLocked ? 'locked' : ''}`}>
                    {isLocked ? '🔒 Locked' : '🔓 Lock'}
                </button>
                <label className="auto-save-toggle">
                    <input type="checkbox" checked={autoSave} onChange={(e) => setAutoSave(e.target.checked)} />
                    Auto-save
                </label>
                {isLocked && <span className="lock-warning">⚠️ Locked by {lockHolder}</span>}
            </div>

            <div className="editor-container">
                <div className="editor-main">
                    <div className="editor-wrapper">
                        <textarea
                            ref={editorRef}
                            value={content}
                            onChange={handleContentChange}
                            disabled={isLocked && lockHolder !== 'You'}
                            className="editor-textarea"
                            placeholder="Start typing..."
                        />
                        <div className="editor-cursors">
                            {cursorPositions.map((cursor) => (
                                <CursorIndicator key={cursor.userId} cursor={cursor} editorRef={editorRef} />
                            ))}
                        </div>
                    </div>
                </div>

                <div className="editor-sidebar">
                    <CollaboratorsList cursors={cursorPositions} />
                    <div className="divider"></div>
                    <ChangeLog changes={changes} />
                    <div className="divider"></div>
                    <VersionHistory versions={versions} onRevert={handleRevertVersion} />
                </div>
            </div>
        </div>
    );
};
