import React, { useState, useEffect } from 'react';
import { DocContent } from '../types';
import { DOCS_DATA } from '../data';
import { useAppStore } from '../store';
import { useToast } from '../components/NotificationSystem';

export const DocsView = () => {
    const { docs, setDocs } = useAppStore();
    const { toast } = useToast();
    const [selectedDocId, setSelectedDocId] = useState<string | null>(null);

    useEffect(() => {
        if (docs.length === 0) {
            setDocs(DOCS_DATA);
        }
        if (docs.length > 0 && !selectedDocId) {
            setSelectedDocId(docs[0].id);
        }
    }, [docs.length, setDocs, selectedDocId]);

    const selectedDoc = docs.find(doc => doc.id === selectedDocId) || null;

    return (
        <div className="docs-view">
            <header className="view-header">
                <h1>Documentation</h1>
                <p>Learn how to use Atom effectively.</p>
            </header>
            <div className="docs-main">
                <aside className="docs-nav">
                    {docs.map(doc => (
                        <button key={doc.id} className={`docs-nav-item ${selectedDocId === doc.id ? 'active' : ''}`} onClick={() => setSelectedDocId(doc.id)}>
                            {doc.title}
                        </button>
                    ))}
                </aside>
                <section className="docs-content">
                    {selectedDoc ? (
                        <div className="doc-content">
                            <h1>{selectedDoc.title}</h1>
                            <div dangerouslySetInnerHTML={{ __html: selectedDoc.content.replace(/\n/g, '<br />') }} />
                        </div>
                    ) : (
                        <div className="doc-placeholder">
                            <p>Select a document to view.</p>
                        </div>
                    )}
                </section>
            </div>
        </div>
    );
};
