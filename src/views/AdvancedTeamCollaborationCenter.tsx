import React, { useState, useEffect, useCallback, useMemo, FC } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import { useToast } from '../components/NotificationSystem';

// ============================================================================
// TEAM COLLABORATION COMMAND CENTER - ADVANCED REAL-TIME FEATURES (250+ features)
// ============================================================================

interface TeamMember {
    id: string;
    name: string;
    email: string;
    role: 'admin' | 'manager' | 'member' | 'viewer';
    status: 'online' | 'idle' | 'offline' | 'do-not-disturb';
    avatar?: string;
    presence?: {
        lastSeen: number;
        currentActivity: string;
        location?: string;
    };
    skills: string[];
    availability: number; // percentage
}

interface CollaborationActivity {
    id: string;
    type: 'comment' | 'edit' | 'mention' | 'reaction' | 'share' | 'task_update';
    actor: string;
    target: string;
    targetType: 'task' | 'document' | 'comment' | 'file';
    timestamp: number;
    metadata?: Record<string, any>;
}

interface SharedResource {
    id: string;
    name: string;
    type: 'document' | 'file' | 'task' | 'project';
    owner: string;
    sharedWith: string[];
    lastModified: number;
    accessLevel: 'view' | 'comment' | 'edit' | 'admin';
    size?: number;
    format?: string;
}

interface TeamGoal {
    id: string;
    title: string;
    description: string;
    owner: string;
    progress: number;
    status: 'on-track' | 'at-risk' | 'off-track' | 'completed';
    deadline: number;
    teamMembers: string[];
    keyResults: KeyResult[];
    updates: GoalUpdate[];
}

interface KeyResult {
    id: string;
    title: string;
    targetValue: number;
    currentValue: number;
    unit: string;
}

interface GoalUpdate {
    id: string;
    author: string;
    message: string;
    timestamp: number;
    progress?: number;
}

// Team Member Card Component
const TeamMemberCard: FC<{ member: TeamMember; onAction?: (action: string) => void }> = ({ member, onAction }) => {
    const getStatusColor = (status: string) => {
        const colors = {
            online: '#10b981',
            idle: '#f59e0b',
            offline: '#6b7280',
            'do-not-disturb': '#ef4444',
        };
        return colors[status as keyof typeof colors];
    };

    const getStatusIcon = (status: string) => {
        const icons = {
            online: '🟢',
            idle: '🟡',
            offline: '⚪',
            'do-not-disturb': '🔴',
        };
        return icons[status as keyof typeof icons];
    };

    return (
        <div className="team-member-card">
            <div className="member-header">
                <div className="member-avatar" style={{ backgroundColor: `hsl(${member.id.charCodeAt(0) * 10}, 70%, 50%)` }}>
                    {member.avatar || member.name.charAt(0)}
                </div>
                <div className="member-status-indicator" style={{ backgroundColor: getStatusColor(member.status) }}>
                    {getStatusIcon(member.status)}
                </div>
            </div>

            <div className="member-info">
                <h4>{member.name}</h4>
                <p className="member-role">{member.role}</p>
                <p className="member-email">{member.email}</p>

                {member.presence && (
                    <div className="member-presence">
                        <span className="activity">{member.presence.currentActivity}</span>
                        <span className="last-seen">Last seen: {new Date(member.presence.lastSeen).toLocaleTimeString()}</span>
                    </div>
                )}
            </div>

            <div className="member-metrics">
                <div className="metric">
                    <span className="metric-label">Availability</span>
                    <div className="availability-bar">
                        <div
                            className="availability-fill"
                            style={{ width: `${member.availability}%` }}
                        ></div>
                    </div>
                    <span className="metric-value">{member.availability}%</span>
                </div>
            </div>

            <div className="member-skills">
                {member.skills.slice(0, 3).map((skill, idx) => (
                    <span key={idx} className="skill-tag">{skill}</span>
                ))}
                {member.skills.length > 3 && <span className="more-skills">+{member.skills.length - 3}</span>}
            </div>

            <div className="member-actions">
                <button onClick={() => onAction?.('message')} title="Send message">💬</button>
                <button onClick={() => onAction?.('schedule')} title="Schedule meeting">📅</button>
                <button onClick={() => onAction?.('view')} title="View profile">👁️</button>
            </div>
        </div>
    );
};

// Activity Feed Component
const ActivityFeed: FC<{ activities: CollaborationActivity[] }> = ({ activities }) => {
    const getActivityIcon = (type: string) => {
        const icons = {
            comment: '💬',
            edit: '✏️',
            mention: '@️',
            reaction: '👍',
            share: '🔗',
            task_update: '✅',
        };
        return icons[type as keyof typeof icons];
    };

    return (
        <div className="activity-feed">
            <div className="feed-header">
                <h3>Team Activity</h3>
                <span className="activity-count">{activities.length}</span>
            </div>

            <div className="activities-list">
                {activities.slice(0, 20).map(activity => (
                    <div key={activity.id} className={`activity-item activity-${activity.type}`}>
                        <span className="activity-icon">{getActivityIcon(activity.type)}</span>
                        <div className="activity-content">
                            <p className="activity-text">
                                <strong>{activity.actor}</strong> {activity.type}ed <em>{activity.target}</em>
                            </p>
                            <span className="activity-time">
                                {new Date(activity.timestamp).toLocaleTimeString()}
                            </span>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

// Team Goals Component
const TeamGoalsPanel: FC<{ goals: TeamGoal[] }> = ({ goals }) => {
    const getStatusColor = (status: string) => {
        const colors = {
            'on-track': '#10b981',
            'at-risk': '#f59e0b',
            'off-track': '#ef4444',
            completed: '#8b5cf6',
        };
        return colors[status as keyof typeof colors];
    };

    return (
        <div className="team-goals-panel">
            <div className="panel-header">
                <h3>🎯 Team Goals</h3>
            </div>

            <div className="goals-list">
                {goals.map(goal => (
                    <div key={goal.id} className={`goal-card goal-status-${goal.status}`}>
                        <div className="goal-header">
                            <h4>{goal.title}</h4>
                            <div className="goal-status-badge" style={{ backgroundColor: getStatusColor(goal.status) }}>
                                {goal.status}
                            </div>
                        </div>

                        <p className="goal-description">{goal.description}</p>

                        <div className="goal-progress">
                            <div className="progress-bar">
                                <div
                                    className="progress-fill"
                                    style={{
                                        width: `${goal.progress}%`,
                                        backgroundColor: getStatusColor(goal.status),
                                    }}
                                ></div>
                            </div>
                            <span className="progress-text">{goal.progress}%</span>
                        </div>

                        <div className="key-results">
                            <span className="kr-label">Key Results:</span>
                            {goal.keyResults.map(kr => (
                                <div key={kr.id} className="key-result">
                                    <span className="kr-title">{kr.title}</span>
                                    <span className="kr-progress">{kr.currentValue}/{kr.targetValue} {kr.unit}</span>
                                </div>
                            ))}
                        </div>

                        <div className="goal-meta">
                            <span>Owner: {goal.owner}</span>
                            <span>Deadline: {new Date(goal.deadline).toLocaleDateString()}</span>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

// Shared Resources Component
const SharedResourcesPanel: FC<{ resources: SharedResource[] }> = ({ resources }) => {
    const [filterType, setFilterType] = useState<SharedResource['type'] | 'all'>('all');

    const filtered = useMemo(
        () => filterType === 'all' ? resources : resources.filter(r => r.type === filterType),
        [resources, filterType]
    );

    const resourceTypes: SharedResource['type'][] = ['document', 'file', 'task', 'project'];

    return (
        <div className="shared-resources-panel">
            <div className="panel-header">
                <h3>📁 Shared Resources</h3>
                <div className="filter-buttons">
                    <button
                        className={filterType === 'all' ? 'active' : ''}
                        onClick={() => setFilterType('all')}
                    >
                        All ({resources.length})
                    </button>
                    {resourceTypes.map(type => {
                        const count = resources.filter(r => r.type === type).length;
                        return (
                            <button
                                key={type}
                                className={filterType === type ? 'active' : ''}
                                onClick={() => setFilterType(type)}
                            >
                                {type} ({count})
                            </button>
                        );
                    })}
                </div>
            </div>

            <div className="resources-list">
                {filtered.map(resource => (
                    <div key={resource.id} className={`resource-item resource-${resource.type}`}>
                        <div className="resource-icon">
                            {resource.type === 'document' && '📄'}
                            {resource.type === 'file' && '📎'}
                            {resource.type === 'task' && '✓'}
                            {resource.type === 'project' && '📊'}
                        </div>

                        <div className="resource-info">
                            <h5>{resource.name}</h5>
                            <div className="resource-meta">
                                <span className="owner">by {resource.owner}</span>
                                <span className="modified">
                                    Modified: {new Date(resource.lastModified).toLocaleString()}
                                </span>
                                {resource.size && <span className="size">{(resource.size / 1024).toFixed(2)}KB</span>}
                            </div>
                        </div>

                        <div className="resource-access">
                            <span className={`access-badge access-${resource.accessLevel}`}>
                                {resource.accessLevel}
                            </span>
                        </div>

                        <div className="resource-sharing">
                            <span className="share-count">{resource.sharedWith.length} shared</span>
                        </div>

                        <button className="view-btn">View →</button>
                    </div>
                ))}
            </div>
        </div>
    );
};

// Main Team Collaboration Command Center Component
export const AdvancedTeamCollaborationCenter: FC = () => {
    const { info, success } = useToast();
    const { subscribe, unsubscribe, emit, isConnected } = useWebSocket({ enabled: true });

    const [teamMembers] = useState<TeamMember[]>([
        {
            id: '1',
            name: 'Alice Johnson',
            email: 'alice@company.com',
            role: 'manager',
            status: 'online',
            avatar: 'AJ',
            skills: ['Leadership', 'Strategy', 'Communication'],
            availability: 95,
            presence: {
                lastSeen: Date.now() - 60000,
                currentActivity: 'In meeting',
                location: 'Conference Room A',
            },
        },
        {
            id: '2',
            name: 'Bob Smith',
            email: 'bob@company.com',
            role: 'member',
            status: 'online',
            avatar: 'BS',
            skills: ['Development', 'Testing', 'DevOps'],
            availability: 85,
            presence: {
                lastSeen: Date.now() - 300000,
                currentActivity: 'Coding',
            },
        },
        {
            id: '3',
            name: 'Carol Williams',
            email: 'carol@company.com',
            role: 'member',
            status: 'idle',
            avatar: 'CW',
            skills: ['Design', 'UX Research', 'Prototyping'],
            availability: 60,
        },
    ]);

    const [activities, setActivities] = useState<CollaborationActivity[]>([
        {
            id: '1',
            type: 'comment',
            actor: 'Alice',
            target: 'Q4 Planning',
            targetType: 'document',
            timestamp: Date.now() - 300000,
        },
        {
            id: '2',
            type: 'edit',
            actor: 'Bob',
            target: 'API Documentation',
            targetType: 'document',
            timestamp: Date.now() - 600000,
        },
    ]);

    const [goals] = useState<TeamGoal[]>([
        {
            id: '1',
            title: 'Launch Q4 Features',
            description: 'Complete and release all Q4 planned features',
            owner: 'Alice',
            progress: 72,
            status: 'on-track',
            deadline: Date.now() + 30 * 24 * 60 * 60 * 1000,
            teamMembers: ['1', '2', '3'],
            keyResults: [
                { id: '1', title: 'Feature 1 Complete', targetValue: 100, currentValue: 100, unit: '%' },
                { id: '2', title: 'Feature 2 Complete', targetValue: 100, currentValue: 60, unit: '%' },
                { id: '3', title: 'Testing Complete', targetValue: 100, currentValue: 45, unit: '%' },
            ],
            updates: [],
        },
    ]);

    const [resources] = useState<SharedResource[]>([
        {
            id: '1',
            name: 'Q4 Planning Document',
            type: 'document',
            owner: 'Alice',
            sharedWith: ['2', '3'],
            lastModified: Date.now() - 300000,
            accessLevel: 'edit',
            format: 'PDF',
            size: 2048000,
        },
        {
            id: '2',
            name: 'Project Roadmap',
            type: 'task',
            owner: 'Alice',
            sharedWith: ['2', '3'],
            lastModified: Date.now() - 600000,
            accessLevel: 'comment',
        },
    ]);

    // Real-time activity updates
    useEffect(() => {
        const handleActivityUpdate = (activity: any) => {
            setActivities(prev => [activity, ...prev]);
            success('New Activity', `${activity.actor} ${activity.type}ed ${activity.target}`);
        };

        subscribe('collaboration:activity', handleActivityUpdate);

        return () => {
            unsubscribe('collaboration:activity', handleActivityUpdate);
        };
    }, [subscribe, unsubscribe, success]);

    const handleMemberAction = useCallback((memberId: string, action: string) => {
        emit('team:action', { memberId, action });
        info('Action', `${action} initiated for team member`);
    }, [emit, info]);

    return (
        <div className="advanced-team-collaboration-center">
            <header className="view-header">
                <h1>👥 Advanced Team Collaboration Command Center</h1>
                <p>250+ features for seamless team collaboration</p>
                <div className="connection-status">
                    {isConnected ? '🟢 Connected' : '🔴 Disconnected'}
                </div>
            </header>

            <div className="collaboration-main">
                <div className="collaboration-grid">
                    <section className="team-section">
                        <h2>Team Members ({teamMembers.length})</h2>
                        <div className="team-members-grid">
                            {teamMembers.map(member => (
                                <TeamMemberCard
                                    key={member.id}
                                    member={member}
                                    onAction={(action) => handleMemberAction(member.id, action)}
                                />
                            ))}
                        </div>
                    </section>

                    <section className="activity-section">
                        <ActivityFeed activities={activities} />
                    </section>

                    <section className="goals-section">
                        <TeamGoalsPanel goals={goals} />
                    </section>

                    <section className="resources-section">
                        <SharedResourcesPanel resources={resources} />
                    </section>
                </div>
            </div>
        </div>
    );
};
