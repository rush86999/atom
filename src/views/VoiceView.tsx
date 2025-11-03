
import React, { useState, useEffect } from 'react';
import { VoiceCommand } from '../types';
import { VOICE_COMMANDS_DATA } from '../data';

const VoiceCommandCard: React.FC<{ command: VoiceCommand }> = ({ command }) => (
    <div className={`voice-command-card ${!command.enabled ? 'disabled' : ''}`}>
        <div className="command-card-header">
            <h3>"{command.phrase}"</h3>
            <span className={`command-status ${command.enabled ? 'enabled' : 'disabled'}`}>{command.enabled ? 'Enabled' : 'Disabled'}</span>
        </div>
        <p className="command-description">{command.description}</p>
    </div>
);

export const VoiceView = () => {
    const [commands, setCommands] = useState<VoiceCommand[]>([]);
    const [isListening, setIsListening] = useState(false);
    const [voiceStatus, setVoiceStatus] = useState('Idle. Press the mic to start.');
    useEffect(() => { setCommands(VOICE_COMMANDS_DATA); }, []);

    const handleToggleListening = () => {
        const newListeningState = !isListening;
        setIsListening(newListeningState);
        setVoiceStatus(newListeningState ? 'Listening for wake word "Atom"...' : 'Idle. Press the mic to start.');
    };

    return (
        <div className="voice-view">
            <header className="view-header"><h1>Voice Commands</h1><p>Interact with Atom hands-free using voice commands.</p></header>
            <div className="commands-list">{commands.map(cmd => <VoiceCommandCard key={cmd.id} command={cmd} />)}</div>
            <footer className="voice-activation-panel">
                <p className="voice-status">{voiceStatus}</p>
                <button className={`mic-button ${isListening ? 'active' : ''}`} onClick={handleToggleListening} aria-label={isListening ? 'Stop listening' : 'Start listening'}>
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M8.25 4.5a3.75 3.75 0 117.5 0v8.25a3.75 3.75 0 11-7.5 0V4.5z" /><path d="M6 10.5a.75.75 0 01.75.75v1.5a5.25 5.25 0 1010.5 0v-1.5a.75.75 0 011.5 0v1.5a6.75 6.75 0 11-13.5 0v-1.5A.75.75 0 016 10.5z" /></svg>
                </button>
            </footer>
        </div>
    );
};
