import React, { useState, useEffect } from 'react';
import { UserProfile, IntegrationConfig, AdvancedSettings } from '../types';
import { USER_PROFILE_DATA, LANGUAGES, TIMEZONES, INTEGRATION_CONFIGS_DATA } from '../data';

export const SettingsView = () => {
    const [profile, setProfile] = useState<UserProfile>(USER_PROFILE_DATA);
    const [hasChanges, setHasChanges] = useState(false);
    const [activeTab, setActiveTab] = useState('profile');
    const [integrations, setIntegrations] = useState<IntegrationConfig[]>(INTEGRATION_CONFIGS_DATA);
    const [showExportModal, setShowExportModal] = useState(false);
    const [showPasswordModal, setShowPasswordModal] = useState(false);
    const [newPassword, setNewPassword] = useState('');

    const handleInputChange = (field: string, value: any) => {
        setProfile(prev => ({ ...prev, [field]: value }));
        setHasChanges(true);
    };

    const handleSave = () => {
        // In a real app, you'd save to a backend
        setHasChanges(false);
        alert('Settings saved!');
    };

    const handleThemeChange = (theme: 'light' | 'dark') => {
        setProfile(prev => ({ ...prev, preferences: { ...prev.preferences, theme } }));
        setHasChanges(true);
    };

    const handleNotificationChange = (channel: string, value: boolean) => {
        setProfile(prev => ({
            ...prev,
            preferences: {
                ...prev.preferences,
                notifications: {
                    ...prev.preferences.notifications,
                    channels: {
                        ...prev.preferences.notifications.channels,
                        [channel]: value
                    }
                }
            }
        }));
        setHasChanges(true);
    };

    const handleIntegrationToggle = (id: string) => {
        setIntegrations(integrations.map(int =>
            int.id === id ? { ...int, connected: !int.connected } : int
        ));
    };

    const handleAdvancedChange = (section: keyof AdvancedSettings, field: string, value: any) => {
        setProfile(prev => ({
            ...prev,
            advancedSettings: {
                ...prev.advancedSettings!,
                [section]: {
                    ...prev.advancedSettings![section],
                    [field]: value
                }
            }
        }));
        setHasChanges(true);
    };

    const handleChangePassword = () => {
        // In a real app, this would call an API
        setProfile(prev => ({
            ...prev,
            advancedSettings: {
                ...prev.advancedSettings!,
                security: {
                    ...prev.advancedSettings!.security,
                    passwordLastChanged: new Date().toISOString()
                }
            }
        }));
        setHasChanges(true);
        setShowPasswordModal(false);
        setNewPassword('');
        alert('Password changed successfully!');
    };

    const handleExportSettings = () => {
        const dataStr = JSON.stringify({ profile, integrations }, null, 2);
        const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
        const exportFileDefaultName = 'atom-settings.json';
        const linkElement = document.createElement('a');
        linkElement.setAttribute('href', dataUri);
        linkElement.setAttribute('download', exportFileDefaultName);
        linkElement.click();
        setShowExportModal(false);
    };

    const handleImportSettings = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (e) => {
                try {
                    const imported = JSON.parse(e.target?.result as string);
                    setProfile(imported.profile);
                    setIntegrations(imported.integrations);
                    setHasChanges(true);
                    alert('Settings imported successfully!');
                } catch (error) {
                    alert('Invalid settings file.');
                }
            };
            reader.readAsText(file);
        }
    };

    return (
        <div className="settings-view">
            <header className="view-header">
                <h1>Settings</h1>
                <p>Customize your Atom experience.</p>
            </header>
            <div className="settings-nav">
                <button className={`settings-nav-item ${activeTab === 'profile' ? 'active' : ''}`} onClick={() => setActiveTab('profile')}>Profile</button>
                <button className={`settings-nav-item ${activeTab === 'notifications' ? 'active' : ''}`} onClick={() => setActiveTab('notifications')}>Notifications</button>
                <button className={`settings-nav-item ${activeTab === 'integrations' ? 'active' : ''}`} onClick={() => setActiveTab('integrations')}>Integrations</button>
                <button className={`settings-nav-item ${activeTab === 'advanced' ? 'active' : ''}`} onClick={() => setActiveTab('advanced')}>Advanced</button>
                <button className={`settings-nav-item ${activeTab === 'export' ? 'active' : ''}`} onClick={() => setActiveTab('export')}>Export/Import</button>
            </div>
            <div className="settings-content">
                {activeTab === 'profile' && (
                    <>
                        <div className="settings-section">
                            <h2>Profile Information</h2>
                            <div className="profile-header">
                                <div className="avatar-container">
                                    <div className="avatar">
                                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
                                            <path fillRule="evenodd" d="M7.5 6a4.5 4.5 0 119 0 4.5 4.5 0 01-9 0zM3.751 20.105a8.25 8.25 0 0116.498 0 .75.75 0 01-.437.695A18.683 18.683 0 0112 22.5c-2.786 0-5.433-.608-7.812-1.7a.75.75 0 01-.437-.695z" clipRule="evenodd" />
                                        </svg>
                                    </div>
                                    <button className="avatar-upload-btn">
                                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
                                            <path d="M21.731 2.269a2.625 2.625 0 00-3.712 0l-1.157 1.157 3.712 3.712 1.157-1.157a2.625 2.625 0 000-3.712zM19.513 8.199l-3.712-3.712L7.25 13.927l3.712 3.712 8.551-8.551zM5.25 5.25a3 3 0 00-3 3v10.5a3 3 0 003 3h10.5a3 3 0 003-3V13.5a.75.75 0 00-1.5 0v5.25a1.5 1.5 0 01-1.5 1.5H5.25a1.5 1.5 0 01-1.5-1.5V8.25a1.5 1.5 0 011.5-1.5h5.25a.75.75 0 000-1.5H5.25z" />
                                        </svg>
                                    </button>
                                </div>
                                <div>
                                    <div className="form-group">
                                        <label htmlFor="name">Full Name</label>
                                        <input id="name" type="text" value={profile.name} onChange={e => handleInputChange('name', e.target.value)} />
                                    </div>
                                    <div className="form-group">
                                        <label htmlFor="email">Email</label>
                                        <input id="email" type="email" value={profile.email} onChange={e => handleInputChange('email', e.target.value)} />
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div className="settings-section">
                            <h2>Preferences</h2>
                            <div className="form-group">
                                <label htmlFor="language">Language</label>
                                <select id="language" value={profile.preferences.language} onChange={e => handleInputChange('preferences', { ...profile.preferences, language: e.target.value })}>
                                    {LANGUAGES.map(lang => <option key={lang.code} value={lang.code}>{lang.name}</option>)}
                                </select>
                            </div>
                            <div className="form-group">
                                <label htmlFor="timezone">Timezone</label>
                                <select id="timezone" value={profile.preferences.timezone} onChange={e => handleInputChange('preferences', { ...profile.preferences, timezone: e.target.value })}>
                                    {TIMEZONES.map(tz => <option key={tz} value={tz}>{tz}</option>)}
                                </select>
                            </div>
                            <div className="form-group">
                                <label>Theme</label>
                                <div className="theme-selector">
                                    <button className={profile.preferences.theme === 'light' ? 'active' : ''} onClick={() => handleThemeChange('light')}>Light</button>
                                    <button className={profile.preferences.theme === 'dark' ? 'active' : ''} onClick={() => handleThemeChange('dark')}>Dark</button>
                                </div>
                            </div>
                        </div>
                    </>
                )}
                {activeTab === 'notifications' && (
                    <div className="settings-section">
                        <h2>Notification Settings</h2>
                        <div className="form-group checkbox-group">
                            <input id="email-notifications" type="checkbox" checked={profile.preferences.notifications.email} onChange={e => handleInputChange('preferences', { ...profile.preferences, notifications: { ...profile.preferences.notifications, email: e.target.checked } })} />
                            <label htmlFor="email-notifications">Email notifications</label>
                        </div>
                        <div className="form-group checkbox-group">
                            <input id="push-notifications" type="checkbox" checked={profile.preferences.notifications.push} onChange={e => handleInputChange('preferences', { ...profile.preferences, notifications: { ...profile.preferences.notifications, push: e.target.checked } })} />
                            <label htmlFor="push-notifications">Push notifications</label>
                        </div>
                        <h3>Per-Channel Notifications</h3>
                        <div className="form-group checkbox-group">
                            <input id="tasks-notifications" type="checkbox" checked={profile.preferences.notifications.channels.tasks} onChange={e => handleNotificationChange('tasks', e.target.checked)} />
                            <label htmlFor="tasks-notifications">Tasks</label>
                        </div>
                        <div className="form-group checkbox-group">
                            <input id="calendar-notifications" type="checkbox" checked={profile.preferences.notifications.channels.calendar} onChange={e => handleNotificationChange('calendar', e.target.checked)} />
                            <label htmlFor="calendar-notifications">Calendar</label>
                        </div>
                        <div className="form-group checkbox-group">
                            <input id="communications-notifications" type="checkbox" checked={profile.preferences.notifications.channels.communications} onChange={e => handleNotificationChange('communications', e.target.checked)} />
                            <label htmlFor="communications-notifications">Communications</label>
                        </div>
                    </div>
                )}
                {activeTab === 'integrations' && (
                    <div className="settings-section">
                        <h2>Integrations</h2>
                        <div className="integrations-list">
                            {integrations.map(integration => (
                                <div key={integration.id} className="integration-item">
                                    <div className="integration-info">
                                        <h4>{integration.name}</h4>
                                        <p>Connected: {integration.connected ? 'Yes' : 'No'}</p>
                                    </div>
                                    <button onClick={() => handleIntegrationToggle(integration.id)}>
                                        {integration.connected ? 'Disconnect' : 'Connect'}
                                    </button>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
                {activeTab === 'advanced' && profile.advancedSettings && (
                    <>
                        <div className="settings-section">
                            <h2>Security Settings</h2>
                            <div className="form-group checkbox-group">
                                <input id="two-factor" type="checkbox" checked={profile.advancedSettings.security.twoFactorEnabled} onChange={e => handleAdvancedChange('security', 'twoFactorEnabled', e.target.checked)} />
                                <label htmlFor="two-factor">Enable Two-Factor Authentication</label>
                            </div>
                            <div className="form-group">
                                <label htmlFor="session-timeout">Session Timeout (minutes)</label>
                                <input id="session-timeout" type="number" value={profile.advancedSettings.security.sessionTimeout} onChange={e => handleAdvancedChange('security', 'sessionTimeout', parseInt(e.target.value))} />
                            </div>
                            <div className="form-group">
                                <label>Password</label>
                                <p>Last changed: {new Date(profile.advancedSettings.security.passwordLastChanged).toLocaleDateString()}</p>
                                <button onClick={() => setShowPasswordModal(true)}>Change Password</button>
                            </div>
                        </div>
                        <div className="settings-section">
                            <h2>API Keys</h2>
                            <div className="form-group">
                                <label htmlFor="openai-key">OpenAI API Key</label>
                                <input id="openai-key" type="password" value={profile.advancedSettings.apiKeys.openai} onChange={e => handleAdvancedChange('apiKeys', 'openai', e.target.value)} placeholder="sk-..." />
                            </div>
                            <div className="form-group">
                                <label htmlFor="google-key">Google API Key</label>
                                <input id="google-key" type="password" value={profile.advancedSettings.apiKeys.google} onChange={e => handleAdvancedChange('apiKeys', 'google', e.target.value)} placeholder="AIza..." />
                            </div>
                            <div className="form-group">
                                <label htmlFor="github-key">GitHub Token</label>
                                <input id="github-key" type="password" value={profile.advancedSettings.apiKeys.github} onChange={e => handleAdvancedChange('apiKeys', 'github', e.target.value)} placeholder="ghp_..." />
                            </div>
                        </div>
                        <div className="settings-section">
                            <h2>Privacy Controls</h2>
                            <div className="form-group checkbox-group">
                                <input id="data-sharing" type="checkbox" checked={profile.advancedSettings.privacy.dataSharing} onChange={e => handleAdvancedChange('privacy', 'dataSharing', e.target.checked)} />
                                <label htmlFor="data-sharing">Allow data sharing for improvements</label>
                            </div>
                            <div className="form-group checkbox-group">
                                <input id="analytics" type="checkbox" checked={profile.advancedSettings.privacy.analytics} onChange={e => handleAdvancedChange('privacy', 'analytics', e.target.checked)} />
                                <label htmlFor="analytics">Enable analytics tracking</label>
                            </div>
                            <div className="form-group checkbox-group">
                                <input id="crash-reports" type="checkbox" checked={profile.advancedSettings.privacy.crashReports} onChange={e => handleAdvancedChange('privacy', 'crashReports', e.target.checked)} />
                                <label htmlFor="crash-reports">Send crash reports</label>
                            </div>
                        </div>
                        <div className="settings-section">
                            <h2>Customization</h2>
                            <div className="form-group">
                                <label htmlFor="dashboard-layout">Dashboard Layout</label>
                                <select id="dashboard-layout" value={profile.advancedSettings.customization.dashboardLayout} onChange={e => handleAdvancedChange('customization', 'dashboardLayout', e.target.value)}>
                                    <option value="grid">Grid</option>
                                    <option value="list">List</option>
                                </select>
                            </div>
                        </div>
                    </>
                )}
                {activeTab === 'export' && (
                    <div className="settings-section">
                        <h2>Export/Import Settings</h2>
                        <div className="export-import-actions">
                            <button onClick={() => setShowExportModal(true)}>Export Settings</button>
                            <label className="import-btn">
                                Import Settings
                                <input type="file" accept=".json" onChange={handleImportSettings} style={{ display: 'none' }} />
                            </label>
                        </div>
                    </div>
                )}
                <div className="settings-footer">
                    <button className={`save-btn ${hasChanges ? '' : 'disabled'}`} onClick={handleSave} disabled={!hasChanges}>Save Changes</button>
                </div>
            </div>
            {showExportModal && (
                <div className="modal-overlay" onClick={() => setShowExportModal(false)}>
                    <div className="modal-content" onClick={e => e.stopPropagation()}>
                        <h3>Export Settings</h3>
                        <p>This will download your current settings as a JSON file.</p>
                        <button onClick={handleExportSettings}>Download</button>
                    </div>
                </div>
            )}
            {showPasswordModal && (
                <div className="modal-overlay" onClick={() => setShowPasswordModal(false)}>
                    <div className="modal-content" onClick={e => e.stopPropagation()}>
                        <h3>Change Password</h3>
                        <input type="password" placeholder="New password" value={newPassword} onChange={e => setNewPassword(e.target.value)} />
                        <button onClick={handleChangePassword} disabled={!newPassword}>Change Password</button>
                    </div>
                </div>
            )}
        </div>
    );
};
