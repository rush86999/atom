import React, { useState, useEffect, useMemo, FC } from 'react';
import { Note } from '../types';
import { NOTES_DATA } from '../data';
import { useAppStore } from '../store';
import { useToast } from '../components/NotificationSystem';

interface NoteVersion {
    id: string;
    content: string;
    timestamp: string;
    author: string;
}

// Rich Text Editor Component
const RichTextEditor: FC<{ 
    content: string; 
    onChange: (content: string) => void; 
    onSave: () => void;
}> = ({ content, onChange, onSave }) => {
    const [isBold, setIsBold] = useState(false);
    const [isItalic, setIsItalic] = useState(false);

    const handleFormat = (format: string) => {
        let formatted = content;
        if (format === 'bold') {
            formatted = `**${content}**`;
            setIsBold(!isBold);
        } else if (format === 'italic') {
            formatted = `*${content}*`;
            setIsItalic(!isItalic);
        } else if (format === 'heading') {
            formatted = `# ${content}`;
        }
        onChange(formatted);
    };

    return (
        <div className="rich-text-editor">
            <div className="editor-toolbar">
                <button onClick={() => handleFormat('bold')} title="Bold" className={isBold ? 'active' : ''}>
                    <strong>B</strong>
                </button>
                <button onClick={() => handleFormat('italic')} title="Italic" className={isItalic ? 'active' : ''}>
                    <em>I</em>
                </button>
                <button onClick={() => handleFormat('heading')} title="Heading">H</button>
                <div className="divider"></div>
                <button onClick={onSave} title="Save" className="save-btn">💾 Save</button>
            </div>
            <textarea
                className="editor-content"
                value={content}
                onChange={(e) => onChange(e.target.value)}
                placeholder="Start typing..."
            />
        </div>
    );
};

export const NotesView = () => {
    const { notes, setNotes, addNote, updateNote, deleteNote } = useAppStore();
    const { toast } = useToast();
    const [selectedNoteId, setSelectedNoteId] = useState<string | null>(null);
    const [searchQuery, setSearchQuery] = useState('');
    const [editingContent, setEditingContent] = useState('');
    const [showVersionHistory, setShowVersionHistory] = useState(false);
    const [versions, setVersions] = useState<NoteVersion[]>([]);
    const [selectedTag, setSelectedTag] = useState<string | null>(null);

    useEffect(() => {
        if (notes.length === 0) {
            NOTES_DATA.forEach(note => addNote(note));
        }
    }, [notes.length, addNote]);

    const selectedNote = notes.find(note => note.id === selectedNoteId) || null;

    const filteredNotes = useMemo(() => {
        return notes.filter(note => {
            const matchesSearch = note.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
                                 note.content.toLowerCase().includes(searchQuery.toLowerCase());
            return matchesSearch;
        });
    }, [notes, searchQuery]);

    const allTags = useMemo(() => {
        const tags = new Set<string>();
        notes.forEach(note => {
            // Assuming notes might have tags in content or type
            tags.add(note.type.replace('_', ' '));
        });
        return Array.from(tags);
    }, [notes]);

    const handleSaveNote = () => {
        if (selectedNote) {
            const newVersion: NoteVersion = {
                id: `v-${Date.now()}`,
                content: editingContent,
                timestamp: new Date().toISOString(),
                author: 'You'
            };
            
            setVersions(prev => [newVersion, ...prev]);
            updateNote(selectedNote.id, { content: editingContent, updatedAt: new Date().toISOString() });
            toast.success('Note Saved', 'Your note has been updated');
        }
    };

    const handleNoteSelect = (noteId: string) => {
        setSelectedNoteId(noteId);
        const note = notes.find(n => n.id === noteId);
        if (note) {
            setEditingContent(note.content);
            setVersions([]);
        }
    };

    const handleExportNote = () => {
        if (selectedNote) {
            const content = `# ${selectedNote.title}\n\n${selectedNote.content}`;
            const blob = new Blob([content], { type: 'text/markdown' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${selectedNote.title}.md`;
            a.click();
            toast.success('Note Exported', `${selectedNote.title} exported as markdown`);
        }
    };

    return (
        <div className="notes-view">
            <header className="view-header">
                <h1>Notes</h1>
                <p>Capture and organize your thoughts.</p>
            </header>
            <div className="notes-main">
                <aside className="note-list-pane">
                    <div className="notes-search">
                        <input 
                            type="text"
                            placeholder="Search notes..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="search-input"
                        />
                    </div>
                    <div className="tags-filter">
                        {allTags.map(tag => (
                            <button 
                                key={tag}
                                className={`tag-filter ${selectedTag === tag ? 'active' : ''}`}
                                onClick={() => setSelectedTag(selectedTag === tag ? null : tag)}
                            >
                                {tag}
                            </button>
                        ))}
                    </div>
                    {filteredNotes.map(note => (
                        <div key={note.id} className={`note-list-item ${selectedNoteId === note.id ? 'selected' : ''}`} onClick={() => handleNoteSelect(note.id)}>
                            <div className="note-item-title">{note.title}</div>
                            <div className="note-item-preview">{note.content.substring(0, 100)}...</div>
                            <div className="note-item-meta">
                                <span className={`note-type-tag ${note.type}`}>{note.type.replace('_', ' ')}</span>
                                <span>{new Date(note.updatedAt).toLocaleDateString()}</span>
                            </div>
                        </div>
                    ))}
                </aside>
                <section className="note-detail-pane">
                    {selectedNote ? (
                        <div className="note-detail-view">
                            <header className="note-detail-header">
                                <h2>{selectedNote.title}</h2>
                                <div className="note-actions">
                                    <button onClick={() => setShowVersionHistory(!showVersionHistory)} title="Version History">📋</button>
                                    <button onClick={handleExportNote} title="Export as Markdown">⬇️</button>
                                    <button onClick={() => deleteNote(selectedNote.id)} title="Delete note">🗑️</button>
                                </div>
                                <div className="note-meta">
                                    <span className={`note-type-tag ${selectedNote.type}`}>{selectedNote.type.replace('_', ' ')}</span>
                                    <span>Updated: {new Date(selectedNote.updatedAt).toLocaleDateString()}</span>
                                </div>
                            </header>
                            {showVersionHistory ? (
                                <div className="version-history">
                                    <h3>Version History</h3>
                                    <div className="versions-list">
                                        {versions.length > 0 ? (
                                            versions.map(v => (
                                                <div key={v.id} className="version-item">
                                                    <small>{new Date(v.timestamp).toLocaleString()} by {v.author}</small>
                                                    <p>{v.content.substring(0, 100)}...</p>
                                                </div>
                                            ))
                                        ) : (
                                            <p>No version history yet</p>
                                        )}
                                    </div>
                                </div>
                            ) : (
                                <RichTextEditor 
                                    content={editingContent}
                                    onChange={setEditingContent}
                                    onSave={handleSaveNote}
                                />
                            )}
                        </div>
                    ) : (
                        <div className="note-detail-view placeholder">
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
                                <path d="M9 11H7v2h2v-2zm4 0h-2v2h2v-2zm4 0h-2v2h2v-2zm2-7h-1V2h-2v2H8V2H6v2H5c-1.1 0-1.99.9-1.99 2L3 20c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V9h14v11z"/>
                            </svg>
                            <p>Select a note to view or create a new one.</p>
                        </div>
                    )}
                </section>
            </div>
        </div>
    );
};
