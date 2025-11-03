import React, { useState, useEffect } from 'react';
import { Note } from '../types';
import { NOTES_DATA } from '../data';

const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
};

const NoteListItem: React.FC<{ note: Note; isSelected: boolean; onClick: () => void; }> = ({ note, isSelected, onClick }) => (
    <div className={`note-list-item ${isSelected ? 'selected' : ''}`} onClick={onClick}>
        <h4 className="note-item-title">{note.title}</h4>
        <p className="note-item-preview">{note.content}</p>
        <p className="note-item-meta">{formatDate(note.createdAt)}</p>
    </div>
);

const NoteDetailView: React.FC<{ note: Note | null }> = ({ note }) => {
    if (!note) {
        return (
            <div className="note-detail-view placeholder">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M5.25 3A2.25 2.25 0 003 5.25v13.5A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V8.25c0-1.242-1.008-2.25-2.25-2.25h-5.691a1.5 1.5 0 01-1.06-.44l-1.72-1.72a.75.75 0 00-.53-.22H5.25z" /></svg>
                <p>Select a note to view its content.</p>
            </div>
        );
    }

    return (
        <div className="note-detail-view">
            <header className="note-detail-header">
                <h2>{note.title}</h2>
                <div className="note-meta">
                    <span className={`note-type-tag ${note.type}`}>{note.type.replace('_', ' ')}</span>
                    <span>{formatDate(note.createdAt)}</span>
                    {note.eventId && <a href="#" onClick={(e) => e.preventDefault()}>View Linked Event</a>}
                </div>
            </header>
            <div className="note-body">
                {note.content}
            </div>
        </div>
    );
};


export const NotesView = () => {
    const [notes, setNotes] = useState<Note[]>([]);
    const [selectedNoteId, setSelectedNoteId] = useState<string | null>(null);
    
    useEffect(() => { 
        setNotes(NOTES_DATA);
        if (NOTES_DATA.length > 0) {
            setSelectedNoteId(NOTES_DATA[0].id);
        }
    }, []);

    const selectedNote = notes.find(n => n.id === selectedNoteId) || null;

    return (
        <div className="notes-view">
            <header className="view-header">
                <h1>Notes</h1>
                <p>Your personal knowledge base.</p>
            </header>
            <div className="notes-main">
                <aside className="note-list-pane">
                    {notes.map(note => (
                        <NoteListItem 
                            key={note.id} 
                            note={note} 
                            isSelected={note.id === selectedNoteId} 
                            onClick={() => setSelectedNoteId(note.id)} 
                        />
                    ))}
                </aside>
                <main className="note-detail-pane">
                    <NoteDetailView note={selectedNote} />
                </main>
            </div>
        </div>
    );
};