import React, { useState, useEffect } from 'react';
import { Integration } from '../types';
import { INTEGRATIONS_DATA } from '../data';
import { useAppStore } from '../store';
import { useToast } from '../components/NotificationSystem';

export const IntegrationsView = () => {
    const { integrations, setIntegrations, updateIntegration } = useAppStore();
    const { toast } = useToast();

    useEffect(() => {
        if (integrations.length === 0) {
            setIntegrations(INTEGRATIONS_DATA);
        }
    }, [integrations.length, setIntegrations]);

    const categories = [...new Set(integrations.map(int => int.category))];

    return (
        <div className="integrations-view">
            <header className="view-header">
                <h1>Integrations</h1>
                <p>Connect your favorite services to Atom.</p>
            </header>
            <div className="integrations-content">
                {categories.map(category => (
                    <div key={category} className="integrations-category">
                        <h2 className="integrations-category-title">{category}</h2>
                        <div className="integrations-grid">
                            {integrations.filter(int => int.category === category).map(integration => (
                                <div key={integration.id} className="integration-card">
                                    <div className="integration-card-header">
                                        <div className="integration-icon">
                                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
                                                <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
                                            </svg>
                                        </div>
                                        <div>
                                            <h3>{integration.displayName}</h3>
                                            <div className="integration-status">
                                                <div className={`status-dot ${integration.connected ? 'success' : 'failed'}`}></div>
                                                <span className="status-text">
                                                    <small>{integration.connected ? 'Connected' : 'Not Connected'}</small>
                                                </span>
                                            </div>
                                        </div>
                                        <span className={`dev-status-tag dev-status-${integration.devStatus}`}>
                                            {integration.devStatus}
                                        </span>
                                    </div>
                                    <div className="integration-card-body">
                                        <p>Connect your {integration.displayName} account to enable seamless integration.</p>
                                    </div>
                                    <div className="integration-card-footer">
                                        <button
                                            className={`integration-button ${integration.connected ? 'disconnect' : 'connect'}`}
                                            onClick={() => {
                                                updateIntegration(integration.id, { connected: !integration.connected });
                                                toast.success('Integration Updated', `${integration.displayName} ${!integration.connected ? 'connected' : 'disconnected'}`);
                                            }}
                                        >
                                            {integration.connected ? 'Disconnect' : 'Connect'}
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};
