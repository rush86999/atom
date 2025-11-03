
import React, { useState, useEffect } from 'react';
import { Integration } from '../types';
import { INTEGRATIONS_DATA } from '../data';
import { ServiceIcon } from '../components/ServiceIcon';

const IntegrationCard: React.FC<{ integration: Integration }> = ({ integration }) => {
    const timeAgo = (date: string) => {
        const seconds = Math.floor((new Date().getTime() - new Date(date).getTime()) / 1000);
        if (seconds < 60) return "Just now";
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
        if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
        return `${Math.floor(seconds / 86400)}d ago`;
    };
    
    const devStatusMap = {
        'development': <span className="dev-status-tag dev-status-dev">In Dev</span>,
        'planned': <span className="dev-status-tag dev-status-planned">Planned</span>,
    };

    return (
        <div className="integration-card">
            <div className="integration-card-header">
                <div className="integration-icon"><ServiceIcon service={integration.serviceType} /></div>
                <h3>{integration.displayName}</h3>
                {integration.devStatus !== 'implemented' && devStatusMap[integration.devStatus]}
            </div>
            <div className="integration-card-body">
                {integration.connected ? (
                    <div className="integration-status connected"><div className={`status-dot ${integration.syncStatus || 'success'}`}></div><div className="status-text"><p>Connected</p>{integration.lastSync && <small>Last sync: {timeAgo(integration.lastSync)}</small>}</div></div>
                ) : (<div className="integration-status disconnected"><div className="status-dot"></div><p>Not Connected</p></div>)}
            </div>
            <div className="integration-card-footer"><button className={`integration-button ${integration.connected ? 'disconnect' : 'connect'}`}>{integration.connected ? 'Manage' : 'Connect'}</button></div>
        </div>
    );
};

export const IntegrationsView = () => {
    const [integrations, setIntegrations] = useState<Integration[]>([]);
    
    useEffect(() => { setIntegrations(INTEGRATIONS_DATA); }, []);

    const groupedIntegrations = integrations.reduce((acc, int) => {
        (acc[int.category] = acc[int.category] || []).push(int);
        return acc;
    }, {} as Record<string, Integration[]>);

    const categoryOrder = [
        'Communication & Collaboration',
        'Calendar & Scheduling',
        'Task & Project Management',
        'Finance & Accounting',
        'Social Media',
        'Development & Technical',
        'Planned Integrations',
    ];

    return (
        <div className="integrations-view">
            <header className="view-header"><h1>Service Integrations</h1><p>Connect your accounts to unlock Atom's full potential.</p></header>
            <div className="integrations-content">
                {categoryOrder.map(category => groupedIntegrations[category] && (
                    <section key={category} className="integrations-category">
                        <h2 className="integrations-category-title">{category}</h2>
                        <div className="integrations-grid">{groupedIntegrations[category].map(int => <IntegrationCard key={int.id} integration={int} />)}</div>
                    </section>
                ))}
            </div>
        </div>
    );
};
