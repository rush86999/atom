import React, { useState, useEffect } from 'react';
import { VoiceCommand } from '../types';
import { VOICE_COMMANDS_DATA } from '../data';
import { useAppStore } from '../store';
import { useToast } from '../components/NotificationSystem';
import { useWebSocket } from '../hooks/useWebSocket';

export const VoiceView = () => {
    const { voiceCommands, setVoiceCommands } = useAppStore();
    const { toast } = useToast();
    const [commands, setCommands] = useState<VoiceCommand[]>(voiceCommands);
    const [isListening, setIsListening] = useState(false);
    const { emit } = useWebSocket({ enabled: true });

    useEffect(() => {
        if (voiceCommands.length === 0) {
            setVoiceCommands(VOICE_COMMANDS_DATA);
            setCommands(VOICE_COMMANDS_DATA);
        } else {
            setCommands(voiceCommands);
        }
    }, [voiceCommands, setVoiceCommands]);

    const toggleListening = () => {
        setIsListening(!isListening);
        toast.info('Voice Control', isListening ? 'Voice listening stopped' : 'Voice listening started');
        if (!isListening) {
            try { emit && emit('voice:activation', { active: true }); } catch (e) {}
        } else {
            try { emit && emit('voice:activation', { active: false }); } catch (e) {}
        }
    };

    return (
        <div className="voice-view">
            <header className="view-header">
                <h1>Voice Commands</h1>
                <p>Control Atom with your voice.</p>
            </header>
            <div className="commands-list">
                {commands.map(command => (
                    <div key={command.id} className={`voice-command-card ${command.enabled ? '' : 'disabled'}`}>
                        <div className="command-card-header">
                            <div className="command-info">
                                <h3>{command.phrase}</h3>
                                <p className="command-description">{command.description}</p>
                            </div>
                            <span className={`command-status ${command.enabled ? 'enabled' : 'disabled'}`}>
                                {command.enabled ? 'Enabled' : 'Disabled'}
                            </span>
                        </div>
                    </div>
                ))}
            </div>
            <div className="voice-activation-panel">
                <p className="voice-status">
                    {isListening ? 'Listening for commands...' : 'Voice activation is off.'}
                </p>
                <button className={`mic-button ${isListening ? 'active' : ''}`} onClick={toggleListening}>
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
                        <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
                    </svg>
                </button>
            </div>
        </div>
    );
};
