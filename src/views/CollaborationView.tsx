import React, { useState, useEffect, FC } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import { useToast } from '../components/NotificationSystem';

interface TeamMember {
    id: string;
    name: string;
    avatar: string;
    role: string;
    status: 'online' | 'offline' | 'away';
    lastSeen: string;
}

interface SharedDocument {
    id: string;
    title: string;
    owner: string;
    lastModified: string;
    collaborators: string[];
}

// Team Member Card Component
const TeamMemberCard: FC<{ member: TeamMember; onAction?: (action: string) => void }> = ({ member, onAction }) => {
    const statusColors: Record<string, string> = {
        online: '#10b981',
        away: '#f59e0b',
        offline: '#6b7280'
    };

    return (
        <div className="team-member-card">
            <div className="member-header">
                <div className="member-avatar">
                    {member.avatar}
                    <div className="status-indicator" style={{ background: statusColors[member.status] }}></div>
                </div>
                <div className="member-info">
                    <h4>{member.name}</h4>
                    <p className="member-role">{member.role}</p>
                    <p className="member-status">{member.status === 'online' ? 'Online now' : `Last seen ${new Date(member.lastSeen).toLocaleDateString()}`}</p>
                </div>
            </div>
            <div className="member-actions">
                <button onClick={() => onAction?.('message')} title="Send message">💬</button>
                <button onClick={() => onAction?.('call')} title="Start call">📞</button>
                <button onClick={() => onAction?.('share')} title="Share document">📄</button>
            </div>
        </div>
    );
};

// Shared Documents Component
const SharedDocuments: FC<{ documents: SharedDocument[] }> = ({ documents }) => {
    return (
        <div className="shared-documents">
            <h3>📄 Shared Documents</h3>
            <div className="documents-list">
                {documents.map(doc => (
                    <div key={doc.id} className="document-item">
                        <div className="document-icon">📋</div>
                        <div className="document-info">
                            <h5>{doc.title}</h5>
                            <p>Owner: {doc.owner}</p>
                            <p>Modified: {new Date(doc.lastModified).toLocaleDateString()}</p>
                            <div className="collaborators-avatars">
                                {doc.collaborators.slice(0, 3).map((collab, i) => (
                                    <span key={i} className="collaborator-avatar">{collab.charAt(0)}</span>
                                ))}
                                {doc.collaborators.length > 3 && <span className="more">+{doc.collaborators.length - 3}</span>}
                            </div>
                        </div>
                        <button className="open-btn">Open</button>
                    </div>
                ))}
            </div>
        </div>
    );
};

// Activity Feed Component
const ActivityFeed: FC = () => {
    const activities = [
        { user: 'Alice', action: 'commented on', target: 'Q4 Planning', timestamp: new Date(Date.now() - 3600000) },
        { user: 'Bob', action: 'completed', target: 'Design Review', timestamp: new Date(Date.now() - 7200000) },
        { user: 'Carol', action: 'shared', target: 'Marketing Report', timestamp: new Date(Date.now() - 86400000) }
    ];

    return (
        <div className="activity-feed">
            <h3>🔔 Team Activity</h3>
            <div className="activities-list">
                {activities.map((activity, i) => (
                    <div key={i} className="activity-item">
                        <div className="activity-avatar">{activity.user.charAt(0)}</div>
                        <div className="activity-content">
                            <p><strong>{activity.user}</strong> {activity.action} <strong>{activity.target}</strong></p>
                            <small>{activity.timestamp.toLocaleDateString()}</small>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export const CollaborationView = () => {
    const { info } = useToast();
    const { subscribe, unsubscribe, emit } = useWebSocket({ enabled: true });
    const [teamMembers, setTeamMembers] = useState<TeamMember[]>([
        {
            id: '1',
            name: 'Alice Johnson',
            avatar: '👩‍💼',
            role: 'Project Manager',
            status: 'online',
            lastSeen: new Date().toISOString()
        },
        {
            id: '2',
            name: 'Bob Smith',
            avatar: '👨‍💻',
            role: 'Developer',
            status: 'online',
            lastSeen: new Date().toISOString()
        },
        {
            id: '3',
            name: 'Carol White',
            avatar: '👩‍🎨',
            role: 'Designer',
            status: 'away',
            lastSeen: new Date(Date.now() - 1800000).toISOString()
        }
    ]);

    const [sharedDocuments] = useState<SharedDocument[]>([
        {
            id: '1',
            title: 'Q4 Planning',
            owner: 'Alice Johnson',
            lastModified: new Date(Date.now() - 3600000).toISOString(),
            collaborators: ['Bob', 'Carol', 'Dave']
        },
        {
            id: '2',
            title: 'Design System',
            owner: 'Carol White',
            lastModified: new Date(Date.now() - 86400000).toISOString(),
            collaborators: ['Alice', 'Bob', 'Emma']
        },
        {
            id: '3',
            title: 'Marketing Report',
            owner: 'Bob Smith',
            lastModified: new Date(Date.now() - 172800000).toISOString(),
            collaborators: ['Alice', 'Carol']
        }
    ]);

    useEffect(() => {
        const onMemberStatus = (data: any) => {
            if (data?.userId && data?.status) {
                setTeamMembers(prev =>
                    prev.map(m => m.id === data.userId ? { ...m, status: data.status } : m)
                );
            }
        };

        subscribe('member:status', onMemberStatus);

        return () => {
            unsubscribe('member:status', onMemberStatus);
        };
    }, [subscribe, unsubscribe]);

    const handleMemberAction = (memberId: string, action: string) => {
        const member = teamMembers.find(m => m.id === memberId);
        if (member) {
            if (action === 'message') {
                info('Direct Message', `Opening chat with ${member.name}`);
                emit?.('dm:init', { from: 'You', to: memberId });
            } else if (action === 'call') {
                info('Starting Call', `Calling ${member.name}...`);
                emit?.('call:init', { from: 'You', to: memberId });
            } else if (action === 'share') {
                info('Share Document', `Sharing options with ${member.name}`);
            }
        }
    };

    return (
        <div className="collaboration-view">
            <header className="view-header">
                <h1>Team Collaboration</h1>
                <p>Manage your team and shared projects.</p>
            </header>

            <div className="collaboration-grid">
                <div className="collaboration-section">
                    <div className="section-header">
                        <h2>👥 Team Members ({teamMembers.length})</h2>
                        <button className="add-member-btn">+ Invite Member</button>
                    </div>
                    <div className="team-members-grid">
                        {teamMembers.map(member => (
                            <TeamMemberCard
                                key={member.id}
                                member={member}
                                onAction={(action) => handleMemberAction(member.id, action)}
                            />
                        ))}
                    </div>
                </div>

                <div className="collaboration-section">
                    <SharedDocuments documents={sharedDocuments} />
                </div>

                <div className="collaboration-section">
                    <ActivityFeed />
                </div>

                <div className="collaboration-section">
                    <div className="quick-actions-panel">
                        <h3>⚡ Quick Actions</h3>
                        <button className="action-btn">📅 Schedule Meeting</button>
                        <button className="action-btn">📝 Create Document</button>
                        <button className="action-btn">🔗 Share Link</button>
                        <button className="action-btn">📊 View Reports</button>
                    </div>
                </div>
            </div>
        </div>
    );
};
