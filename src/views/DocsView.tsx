
import React, { useState } from 'react';
import { DocContent } from '../types';
import { DOCS_DATA } from '../data';
import { MarkdownRenderer } from '../components/MarkdownRenderer';

export const DocsView = () => {
    const [docs] = useState<DocContent[]>(DOCS_DATA.filter(d => d.content && d.content.trim() !== ''));
    const [selectedDocId, setSelectedDocId] = useState<string>(docs[0]?.id || '');
    const selectedDoc = docs.find(d => d.id === selectedDocId);
    return (
        <div className="docs-view">
             <header className="view-header"><h1>Documentation</h1><p>Browse project documentation.</p></header>
            <div className="docs-main">
                <aside className="doc-list-pane">{docs.map(doc => (<div key={doc.id} className={`doc-list-item ${doc.id === selectedDocId ? 'active' : ''}`} onClick={() => setSelectedDocId(doc.id)}>{doc.title}</div>))}</aside>
                <main className="doc-content-pane">{selectedDoc ? (<MarkdownRenderer content={selectedDoc.content} />) : (<p>Select a document.</p>)}</main>
            </div>
        </div>
    )
};
