/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import React, { useState, useEffect } from 'react';
import { CommunicationsMessage } from '../types';
import { COMMUNICATIONS_DATA } from '../data';
import { ServiceIcon } from '../components/ServiceIcon';
import { CommunicationAnalyzer } from '../autonomous-communication/communicationAnalyzer';

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
    const [searchQuery, setSearchQuery] = useState('');
    const [sortBy, setSortBy] = useState<'date-desc' | 'date-asc' | 'sender' | 'subject'>('date-desc');
    const [showComposeModal, setShowComposeModal] = useState(false);
    const [composeForm, setComposeForm] = useState({ to: '', subject: '', body: '' });
    const [aiSummary, setAiSummary] = useState<string>('');
    const [currentPage, setCurrentPage] = useState(1);
    const messagesPerPage = 10;

    useEffect(() => { 
        setMessages(COMMUNICATIONS_DATA);
    }, []);

    const clearFilters = () => {
        setSenderFilter('');
        setSubjectFilter('');
        setStartDateFilter('');
        setEndDateFilter('');
        setSearchQuery('');
        setCurrentPage(1);
    };

    const markAsRead = (id: string) => {
        setMessages(prev => prev.map(msg => msg.id === id ? { ...msg, read: true, unread: false } : msg));
    };

    const markAsUnread = (id: string) => {
        setMessages(prev => prev.map(msg => msg.id === id ? { ...msg, read: false, unread: true } : msg));
    };

    const generateAISummary = async (message: CommunicationsMessage) => {
        // Simple AI summary using CommunicationAnalyzer
        const analyzer = new CommunicationAnalyzer();
        const context = {
            timestamp: new Date(),
            userId: 'user123',
            recentCommunications: [{
                id: message.id,
                type: 'follow-up' as any,
                senderId: message.from.name,
                recipientId: 'user123',
                channel: message.platform as any,
                timestamp: new Date(message.timestamp),
                message: message.body,
                status: 'sent' as any,
                context: {},
                priority: 'normal' as any,
                sentimentScore: 0.5,
                categories: [],
                tokensUsed: 0,
                performance: {}
            }],
            activeRelationships: [],
            platformStatus: {
                email: true,
                slack: true,
                teams: true,
                discord: false,
                linkedin: false,
                twitter: false,
                sms: false,
                phone: false,
                voicemail: false,
                'in-person': false,
                all: true
            },
            preferences: {
                preferredChannels: {},
                nonWorkingHours: { start: 18, end: 8 },
                responseTimeExpectations: {},
                autoResponseTriggers: [],
                doNotDisturbList: [],
                tonePreferences: {},
                messageLengthPreference: 'medium' as 'medium',
                emojiUsage: false
            },
            emotionalContext: {
                currentMood: 'neutral' as 'neutral',
                recentSentiment: 0,
                factors: [],
                lastUpdated: new Date()
            },
            externalFactors: {
                isWeekend: false,
                timeOfDay: new Date().getHours(),
                scheduleBusy: false,
                weather: 'sunny',
                moodIndicators: {},
                holidays: [],
                events: []
            },
            userAvailability: {
                busy: false,
                nextAvailable: new Date(),
                currentFocus: 'work'
            }
        };
        const analysis = await analyzer.analyzeCommunicationPatterns(context);
        setAiSummary(`Summary: ${message.subject} - Key points: ${analysis.recommendations.join(', ')}`);
    };

    const sendMessage = () => {
        // Placeholder for sending message
        alert(`Message sent to ${composeForm.to}`);
        setShowComposeModal(false);
        setComposeForm({ to: '', subject: '', body: '' });
    };

    const filteredMessages = messages.filter(message => {
        const senderMatch = senderFilter ? message.from.name.toLowerCase().includes(senderFilter.toLowerCase()) : true;
        const subjectMatch = subjectFilter ? message.subject.toLowerCase().includes(subjectFilter.toLowerCase()) : true;
        const searchMatch = searchQuery ? (
            message.from.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            message.subject.toLowerCase().includes(searchQuery.toLowerCase()) ||
            message.body.toLowerCase().includes(searchQuery.toLowerCase())
        ) : true;

        const messageDate = new Date(message.timestamp);
        const startDate = startDateFilter ? new Date(startDateFilter) : null;
        if (startDate) startDate.setHours(0, 0, 0, 0); // Start of day

        const endDate = endDateFilter ? new Date(endDateFilter) : null;
        if (endDate) endDate.setHours(23, 59, 59, 999); // End of day

        const dateMatch = (!startDate || messageDate >= startDate) && (!endDate || messageDate <= endDate);

        return senderMatch && subjectMatch && dateMatch && searchMatch;
    });

    const sortedMessages = [...filteredMessages].sort((a, b) => {
        switch (sortBy) {
            case 'date-asc':
                return new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime();
            case 'date-desc':
                return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
            case 'sender':
                return a.from.name.localeCompare(b.from.name);
            case 'subject':
                return a.subject.localeCompare(b.subject);
            default:
                return 0;
        }
    });

    const paginatedMessages = sortedMessages.slice((currentPage - 1) * messagesPerPage, currentPage * messagesPerPage);
    const totalPages = Math.ceil(sortedMessages.length / messagesPerPage);

    useEffect(() => {
        const currentSelectionExists = paginatedMessages.some(m => m.id === selectedMessageId);
        if (!currentSelectionExists) {
            setSelectedMessageId(paginatedMessages.length > 0 ? paginatedMessages[0].id : null);
        }
    }, [selectedMessageId, paginatedMessages]);

    const selectedMessage = messages.find(m => m.id === selectedMessageId) || null;

    return (
        <div className="communications-view">
            <header className="view-header"><h1>Communications Hub</h1><p>A unified inbox for all your messages.</p></header>

            <div className="communications-filter-bar">
                <div className="filter-group">
                    <label>Search</label>
                    <input type="text" placeholder="Search messages..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)} />
                </div>
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
                <div className="filter-group">
                    <label>Sort By</label>
                    <select value={sortBy} onChange={e => setSortBy(e.target.value as any)}>
                        <option value="date-desc">Date (Newest)</option>
                        <option value="date-asc">Date (Oldest)</option>
                        <option value="sender">Sender</option>
                        <option value="subject">Subject</option>
                    </select>
                </div>
                <button className="clear-filters-btn" onClick={clearFilters}>Clear</button>
                <button className="compose-btn" onClick={() => setShowComposeModal(true)}>Compose</button>
            </div>

            <div className="communications-main">
                <aside className="message-list-pane">
                    {paginatedMessages.length > 0 ? (
                        paginatedMessages.map(msg => (
                            <div key={msg.id} className="message-list-item-wrapper">
                                <MessageListItem
                                    message={msg}
                                    isSelected={msg.id === selectedMessageId}
                                    onClick={() => setSelectedMessageId(msg.id)}
                                />
                                <div className="message-actions">
                                    <input type="checkbox" checked={msg.read} onChange={() => msg.read ? markAsUnread(msg.id) : markAsRead(msg.id)} />
                                    <label>Read</label>
                                </div>
                            </div>
                        ))
                    ) : (
                        <p className="no-messages-found">No messages match your filters.</p>
                    )}
                    {totalPages > 1 && (
                        <div className="pagination">
                            <button disabled={currentPage === 1} onClick={() => setCurrentPage(currentPage - 1)}>Prev</button>
                            <span>Page {currentPage} of {totalPages}</span>
                            <button disabled={currentPage === totalPages} onClick={() => setCurrentPage(currentPage + 1)}>Next</button>
                        </div>
                    )}
                </aside>
                <section className="message-detail-pane">
                    <MessageDetailView message={selectedMessage} />
                    {selectedMessage && (
                        <div className="ai-suggestions">
                            <button onClick={() => generateAISummary(selectedMessage)}>Generate AI Summary</button>
                            {aiSummary && <p>{aiSummary}</p>}
                        </div>
                    )}
                </section>
            </div>
            {showComposeModal && (
                <div className="modal-overlay" onClick={() => setShowComposeModal(false)}>
                    <div className="modal-content" onClick={e => e.stopPropagation()}>
                        <h2>Compose New Message</h2>
                        <form onSubmit={e => { e.preventDefault(); sendMessage(); }}>
                            <div className="form-group">
                                <label>To:</label>
                                <input type="text" value={composeForm.to} onChange={e => setComposeForm({...composeForm, to: e.target.value})} required />
                            </div>
                            <div className="form-group">
                                <label>Subject:</label>
                                <input type="text" value={composeForm.subject} onChange={e => setComposeForm({...composeForm, subject: e.target.value})} required />
                            </div>
                            <div className="form-group">
                                <label>Message:</label>
                                <textarea value={composeForm.body} onChange={e => setComposeForm({...composeForm, body: e.target.value})} required />
                            </div>
                            <div className="modal-actions">
                                <button type="button" onClick={() => setShowComposeModal(false)}>Cancel</button>
                                <button type="submit">Send</button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
};
