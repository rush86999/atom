/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import React, { useState, useEffect } from 'react';
import { CommunicationsMessage } from '../types';
import { COMMUNICATIONS_DATA } from '../data';
import { ServiceIcon } from '../components/ServiceIcon';

const timeAgo = (date: string) => {
    const seconds = Math.floor((new Date().getTime() - new Date(date).getTime()) / 1000);
    if (seconds < 60) return "Just now";
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    return `${Math.floor(seconds / 3600)}h ago`;
};

const MessageListItem: React.FC<{ message: CommunicationsMessage; isSelected: boolean; onClick: () => void; }> = ({ message, isSelected, onClick }) => (
    <div className={`message-list-item ${isSelected ? 'selected' : ''}`} onClick={onClick}>
        {message.unread && <div className="unread-dot"></div>}
        <div className="message-item-platform-icon"><ServiceIcon service={message.platform} /></div>
        <div className="message-item-content">
            <div className="message-item-header"><span className="message-sender">{message.from.name}</span><span className="message-time">{timeAgo(message.timestamp)}</span></div>
            <p className="message-subject">{message.subject}</p><p className="message-preview">{message.preview}</p>
        </div>
    </div>
);

const MessageDetailView: React.FC<{ message: CommunicationsMessage | null }> = ({ message }) => {
    if (!message) return <div className="message-detail-view placeholder"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M1.5 8.67v8.58a3 3 0 003 3h15a3 3 0 003-3V8.67l-8.928 5.493a3 3 0 01-3.144 0L1.5 8.67z" /><path d="M22.5 6.908V6.75a3 3 0 00-3-3h-15a3 3 0 00-3 3v.158l9.714 5.978a1.5 1.5 0 001.572 0L22.5 6.908z" /></svg><p>Select a message to view or clear filters.</p></div>;
    return (
        <div className="message-detail-view">
            <header className="message-detail-header"><h2>{message.subject}</h2><div className="message-meta"><div className="message-meta-sender"><strong>{message.from.name}</strong><small>via {message.platform}</small></div><span className="message-meta-time">{new Date(message.timestamp).toLocaleString()}</span></div></header>
            <div className="message-body"><p>{message.body}</p></div>
            <footer className="message-detail-footer"><button className="action-btn">Reply</button><button className="action-btn">Archive</button></footer>
        </div>
    );
};

export const CommunicationsView = () => {
    const [messages, setMessages] = useState<CommunicationsMessage[]>([]);
    const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null);
    
    // New states for filters
    const [senderFilter, setSenderFilter] = useState('');
    const [subjectFilter, setSubjectFilter] = useState('');
    const [startDateFilter, setStartDateFilter] = useState('');
    const [endDateFilter, setEndDateFilter] = useState('');

    useEffect(() => { 
        setMessages(COMMUNICATIONS_DATA);
    }, []);

    const clearFilters = () => {
        setSenderFilter('');
        setSubjectFilter('');
        setStartDateFilter('');
        setEndDateFilter('');
    };

    const filteredMessages = messages.filter(message => {
        const senderMatch = senderFilter ? message.from.name.toLowerCase().includes(senderFilter.toLowerCase()) : true;
        const subjectMatch = subjectFilter ? message.subject.toLowerCase().includes(subjectFilter.toLowerCase()) : true;
        
        const messageDate = new Date(message.timestamp);
        const startDate = startDateFilter ? new Date(startDateFilter) : null;
        if (startDate) startDate.setHours(0, 0, 0, 0); // Start of day
        
        const endDate = endDateFilter ? new Date(endDateFilter) : null;
        if (endDate) endDate.setHours(23, 59, 59, 999); // End of day

        const dateMatch = (!startDate || messageDate >= startDate) && (!endDate || messageDate <= endDate);
        
        return senderMatch && subjectMatch && dateMatch;
    });

    useEffect(() => {
        const currentSelectionExists = filteredMessages.some(m => m.id === selectedMessageId);
        if (!currentSelectionExists) {
            setSelectedMessageId(filteredMessages.length > 0 ? filteredMessages[0].id : null);
        }
    }, [selectedMessageId, filteredMessages]);

    const selectedMessage = messages.find(m => m.id === selectedMessageId) || null;

    return (
        <div className="communications-view">
            <header className="view-header"><h1>Communications Hub</h1><p>A unified inbox for all your messages.</p></header>

            <div className="communications-filter-bar">
                <div className="filter-group">
                    <label>Sender</label>
                    <input type="text" placeholder="Filter by sender..." value={senderFilter} onChange={e => setSenderFilter(e.target.value)} />
                </div>
                <div className="filter-group">
                    <label>Subject</label>
                    <input type="text" placeholder="Filter by subject..." value={subjectFilter} onChange={e => setSubjectFilter(e.target.value)} />
                </div>
                <div className="filter-group">
                    <label>Start Date</label>
                    <input type="date" value={startDateFilter} onChange={e => setStartDateFilter(e.target.value)} />
                </div>
                <div className="filter-group">
                    <label>End Date</label>
                    <input type="date" value={endDateFilter} onChange={e => setEndDateFilter(e.target.value)} />
                </div>
                <button className="clear-filters-btn" onClick={clearFilters}>Clear</button>
            </div>

            <div className="communications-main">
                <aside className="message-list-pane">
                    {filteredMessages.length > 0 ? (
                        filteredMessages.map(msg => (
                            <MessageListItem 
                                key={msg.id} 
                                message={msg} 
                                isSelected={msg.id === selectedMessageId} 
                                onClick={() => setSelectedMessageId(msg.id)} 
                            />
                        ))
                    ) : (
                        <p className="no-messages-found">No messages match your filters.</p>
                    )}
                </aside>
                <section className="message-detail-pane">
                    <MessageDetailView message={selectedMessage} />
                </section>
            </div>
        </div>
    );
};
