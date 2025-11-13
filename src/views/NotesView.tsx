import React, { useState, useEffect } from 'react';
import { Note } from '../types';
import { NOTES_DATA } from '../data';

export const NotesView = () => {
    const [notes, setNotes] = useState<Note[]>([]);
    const [selectedNoteId, setSelectedNoteId] = useState<string | null>(null);

    useEffect(() => {
        setNotes(NOTES_DATA);
    }, []);

    const selectedNote = notes.find(note => note.id === selectedNoteId) || null;

    return (
        <div className="notes-view">
            <header className="view-header">
                <h1>Notes</h1>
                <p>Capture and organize your thoughts.</p>
            </header>
            <div className="notes-main">
                <aside className="note-list-pane">
                    {notes.map(note => (
                        <div key={note.id} className={`note-list-item ${selectedNoteId === note.id ? 'selected' : ''}`} onClick={() => setSelectedNoteId(note.id)}>
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
                                <div className="note-meta">
                                    <span className={`note-type-tag ${selectedNote.type}`}>{selectedNote.type.replace('_', ' ')}</span>
                                    <span>Updated: {new Date(selectedNote.updatedAt).toLocaleDateString()}</span>
                                </div>
                            </header>
                            <div className="note-body">{selectedNote.content}</div>
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
