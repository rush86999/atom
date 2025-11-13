import React, { useState, useEffect } from 'react';
import { DevProject } from '../types';
import { DEV_PROJECT_DATA } from '../data';
import { useAppStore } from '../store';
import { useToast } from '../components/NotificationSystem';

export const DevStudioView = () => {
    const { devProjects, setDevProjects } = useAppStore();
    const { toast } = useToast();
    const [project, setProject] = useState<DevProject>(devProjects.length > 0 ? devProjects[0] : DEV_PROJECT_DATA);

    useEffect(() => {
        if (devProjects.length === 0) {
            setDevProjects([DEV_PROJECT_DATA]);
        }
    }, [devProjects.length, setDevProjects]);

    return (
        <div className="dev-studio-view">
            <header className="view-header">
                <h1>Dev Studio</h1>
                <p>Monitor your development projects.</p>
            </header>
            <div className="dev-studio-main">
                <div className="dev-studio-left">
                    <div className="build-monitor">
                        <h3>Build Monitor</h3>
                        <div className="progress-bar-container">
                            <div className="progress-bar" style={{ width: `${project.progress}%` }}></div>
                            <span>{project.progress}% Complete</span>
                        </div>
                        <div className="build-links">
                            <p><a href={project.liveUrl} target="_blank" rel="noopener noreferrer">Live Site</a></p>
                            <p><a href={project.previewUrl} target="_blank" rel="noopener noreferrer">Preview</a></p>
                        </div>
                    </div>
                    <div className="metrics-panel">
                        <h3>Performance Metrics</h3>
                        <div className="metrics-grid">
                            <div className="metric-card">
                                <h4>Performance</h4>
                                <p>{project.metrics.performance}</p>
                            </div>
                            <div className="metric-card">
                                <h4>Mobile</h4>
                                <p>{project.metrics.mobile}</p>
                            </div>
                            <div className="metric-card">
                                <h4>SEO</h4>
                                <p>{project.metrics.seo}</p>
                            </div>
                            <div className="metric-card">
                                <h4>Rebuild Time</h4>
                                <p>{project.metrics.rebuildTime}s</p>
                            </div>
                        </div>
                    </div>
                </div>
                <div className="dev-studio-right">
                    <div className="chat-container">
                        <header className="chat-header">
                            <h1>Dev Chat</h1>
                            <p>Discuss your project with the team.</p>
                        </header>
                        <div className="message-list">
                            <div className="message atom-message">
                                <div className="message-bubble">
                                    Welcome to the Dev Studio! How can I help with your project today?
                                </div>
                            </div>
                        </div>
                        <footer className="chat-footer">
                            <form className="input-form">
                                <textarea placeholder="Ask about your project..." rows={1}></textarea>
                                <button type="submit">
                                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
                                        <path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z" />
                                    </svg>
                                </button>
                            </form>
                        </footer>
                    </div>
                </div>
            </div>
        </div>
    );
};
