/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import React, { useState, useEffect } from 'react';
import { UserProfile } from '../types';
import { USER_PROFILE_DATA, LANGUAGES, TIMEZONES } from '../data';

const VoiceSettings: React.FC = () => {
    const [ttsProvider, setTtsProvider] = useState<'default' | 'elevenlabs' | 'deepgram'>('default');
    const [elevenLabsKey, setElevenLabsKey] = useState('');
    const [deepgramKey, setDeepgramKey] = useState('');
    const [saveStatus, setSaveStatus] = useState('');

    const handleSave = () => {
        if (ttsProvider === 'elevenlabs' && !elevenLabsKey.trim()) {
            setSaveStatus('Please enter an ElevenLabs API key.');
            return;
        }
        if (ttsProvider === 'deepgram' && !deepgramKey.trim()) {
            setSaveStatus('Please enter a Deepgram API key.');
            return;
        }
        
        console.log('Saving Voice Settings:', {
            provider: ttsProvider,
            keys: {
                elevenlabs: elevenLabsKey,
                deepgram: deepgramKey,
            }
        });

        setSaveStatus('Voice settings saved successfully!');
        setTimeout(() => setSaveStatus(''), 3000);
    };

    return (
        <section className="settings-section">
            <h2>Voice Settings</h2>
            <div className="form-group">
                <label htmlFor="tts-provider">TTS Provider</label>
                <select 
                    id="tts-provider" 
                    value={ttsProvider} 
                    onChange={(e) => setTtsProvider(e.target.value as any)}
                >
                    <option value="default">Default</option>
                    <option value="elevenlabs">ElevenLabs</option>
                    <option value="deepgram">Deepgram</option>
                </select>
            </div>

            {ttsProvider === 'elevenlabs' && (
                <div className="form-group">
                    <label htmlFor="elevenlabs-key">ElevenLabs API Key</label>
                    <input 
                        type="password" 
                        id="elevenlabs-key" 
                        value={elevenLabsKey}
                        onChange={(e) => setElevenLabsKey(e.target.value)}
                        placeholder="Enter your ElevenLabs API Key"
                    />
                </div>
            )}

            {ttsProvider === 'deepgram' && (
                 <div className="form-group">
                    <label htmlFor="deepgram-key">Deepgram API Key</label>
                    <input 
                        type="password" 
                        id="deepgram-key" 
                        value={deepgramKey}
                        onChange={(e) => setDeepgramKey(e.target.value)}
                        placeholder="Enter your Deepgram API Key"
                    />
                </div>
            )}

            <div className="voice-settings-footer">
                <button type="button" className="save-btn" onClick={handleSave}>Save Voice Settings</button>
                {saveStatus && <span className="save-status-message">{saveStatus}</span>}
            </div>
        </section>
    );
};


export const SettingsView = () => {
    const [profile, setProfile] = useState<UserProfile>(USER_PROFILE_DATA);
    const [hasChanges, setHasChanges] = useState(false);
    const [activeSection, setActiveSection] = useState('profile');

    useEffect(() => {
        const original = JSON.stringify(USER_PROFILE_DATA);
        const current = JSON.stringify(profile);
        setHasChanges(original !== current);
    }, [profile]);

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        const { name, value, type } = e.target;
        const keys = name.split('.');
        
        setProfile(prevProfile => {
            const newProfile = JSON.parse(JSON.stringify(prevProfile));
            let currentLevel: any = newProfile;
            
            for (let i = 0; i < keys.length - 1; i++) {
                currentLevel = currentLevel[keys[i]];
            }
            
            if (type === 'checkbox') {
                 currentLevel[keys[keys.length - 1]] = (e.target as HTMLInputElement).checked;
            } else {
                 currentLevel[keys[keys.length - 1]] = value;
            }

            return newProfile;
        });
    };
    
    const handleSaveChanges = (e: React.FormEvent) => {
        e.preventDefault();
        console.log("Saving changes:", profile);
        setHasChanges(false);
        alert("Settings saved!");
    };


    return (
        <div className="settings-view">
            <nav className="settings-nav">
                 <button className={`settings-nav-item ${activeSection === 'profile' ? 'active' : ''}`} onClick={() => setActiveSection('profile')}>
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-5.5-2.5a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0zM10 12a5.99 5.99 0 00-4.793 2.39A6.483 6.483 0 0010 16.5a6.483 6.483 0 004.793-2.11A5.99 5.99 0 0010 12z" clipRule="evenodd" /></svg>
                    Profile
                </button>
                <button className={`settings-nav-item ${activeSection === 'appearance' ? 'active' : ''}`} onClick={() => setActiveSection('appearance')}>
                     <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path d="M10 3.5a1.5 1.5 0 01.82 2.81l5.24 3.14a1.5 1.5 0 010 2.1l-5.24 3.14A1.5 1.5 0 119.18 12L13.5 9.5 9.18 7A1.5 1.5 0 1110 3.5zM3.5 6a1.5 1.5 0 113 0 1.5 1.5 0 01-3 0zM15 12.5a1.5 1.5 0 100 3 1.5 1.5 0 000-3z" /></svg>
                    Appearance
                </button>
                <button className={`settings-nav-item ${activeSection === 'voice' ? 'active' : ''}`} onClick={() => setActiveSection('voice')}>
                     <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path d="M7 4a3 3 0 016 0v6a3 3 0 11-6 0V4z" /><path d="M5.5 8.5a.5.5 0 01.5.5v1a4 4 0 008 0v-1a.5.5 0 011 0v1a5 5 0 01-4.5 4.975V17h3a.5.5 0 010 1h-7a.5.5 0 010-1h3v-2.025A5 5 0 014.5 10v-1a.5.5 0 01.5-.5z" /></svg>
                    Voice & AI
                </button>
                <button className={`settings-nav-item ${activeSection === 'notifications' ? 'active' : ''}`} onClick={() => setActiveSection('notifications')}>
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path d="M10 2a6 6 0 00-6 6v3.586l-.707.707A1 1 0 004 14h12a1 1 0 00.707-1.707L16 11.586V8a6 6 0 00-6-6zM10 18a3 3 0 01-3-3h6a3 3 0 01-3 3z" /></svg>
                    Notifications
                </button>
            </nav>
            <div className="settings-content">
                <form onSubmit={handleSaveChanges}>
                    <section className="settings-section">
                        <h2>Profile</h2>
                        <div className="profile-header">
                            <div className="avatar-container">
                                <div className="avatar">
                                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M24 20.993V24H0v-2.996A14.977 14.977 0 0112.004 15c4.904 0 9.26 2.354 11.996 5.993zM16.002 8.999a4 4 0 11-8 0 4 4 0 018 0z" /></svg>
                                </div>
                                <div className="avatar-upload-btn"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path d="M12 4.5a.75.75 0 01.75.75v3.5h3.5a.75.75 0 010 1.5h-3.5v3.5a.75.75 0 01-1.5 0v-3.5h-3.5a.75.75 0 010-1.5h3.5v-3.5a.75.75 0 01.75-.75z" /></svg></div>
                            </div>
                            <div>
                                <input type="text" id="name" name="name" value={profile.name} onChange={handleInputChange} />
                                <input type="email" id="email" name="email" value={profile.email} onChange={handleInputChange} />
                            </div>
                        </div>
                    </section>
                    
                    <VoiceSettings />

                    <section className="settings-section">
                        <h2>Notifications</h2>
                        <div className="form-group checkbox-group">
                            <input type="checkbox" id="email-notifications" name="preferences.notifications.email" checked={profile.preferences.notifications.email} onChange={handleInputChange} />
                            <label htmlFor="email-notifications">Email Notifications</label>
                        </div>
                         <div className="form-group checkbox-group">
                            <input type="checkbox" id="push-notifications" name="preferences.notifications.push" checked={profile.preferences.notifications.push} onChange={handleInputChange} />
                            <label htmlFor="push-notifications">Push Notifications</label>
                        </div>
                    </section>
                    
                    <div className="settings-footer">
                        <button type="submit" className="save-btn" disabled={!hasChanges}>Save Changes</button>
                    </div>
                </form>
            </div>
        </div>
    );
};
